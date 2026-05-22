// KFinans Frontend — Shared HTTP client + auth token helpers.
//
// `lib/api.ts`'ten ayrıldı (Sprint 3 #12 endpoint split). Tüm domain
// modülleri (auth.ts, expense.ts, ...) `request`'i buradan import eder.
// Public API: setAuth, clearAuth (consumer'lar login/logout flow'da kullanır).

export const BASE = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export function getAccessToken() {
  return typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
}

export function getRefreshToken() {
  return typeof window !== "undefined" ? localStorage.getItem(REFRESH_TOKEN_KEY) : null;
}

export function setAuth(accessToken: string, refreshToken?: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  document.cookie = `access_token=${accessToken}; path=/; SameSite=Strict`;
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
}

export function clearAuth() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

// Single-flight: aynı anda birden çok 401 → tek refresh request paylaş.
// FAZ C4 backend rotation aktif: ilk refresh eski token'ı blacklist'e atar,
// paralel istekler aynı yeni token ile retry eder.
let _refreshInflight: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  if (_refreshInflight) return _refreshInflight;

  _refreshInflight = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return null;
      const data = (await res.json()) as { access_token: string; refresh_token: string };
      setAuth(data.access_token, data.refresh_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      _refreshInflight = null;
    }
  })();

  return _refreshInflight;
}

/**
 * FastAPI hata yanıtlarındaki "detail" alanı string, obje veya
 * Pydantic validation listesi olabilir. Hepsini insan-okunaklı string'e çevir.
 */
export function formatErrorDetail(detail: unknown): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const it = item as { msg?: string; loc?: unknown[] };
          const loc = Array.isArray(it.loc) ? it.loc.join(".") : "";
          return loc ? `${loc}: ${it.msg}` : String(it.msg);
        }
        return JSON.stringify(item);
      })
      .join(" · ");
  }
  if (typeof detail === "object") return JSON.stringify(detail);
  return String(detail);
}

export async function request<T>(path: string, options: RequestInit = {}, _isRetry = false): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  // Access expired → bir kez refresh dene + retry (FAZ C4 rotation uyumlu).
  // /auth/refresh endpoint'inin kendisinde retry yapma (sonsuz döngü riski).
  if (res.status === 401 && typeof window !== "undefined" && !_isRetry && path !== "/auth/refresh") {
    const newToken = await tryRefresh();
    if (newToken) {
      return request<T>(path, options, true);
    }
    clearAuth();
    window.location.replace("/login");
    throw new Error("Oturum süresi doldu");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(formatErrorDetail(err.detail) || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/**
 * Auth header'ı ile raw fetch — Content-Type/JSON kararı çağırana ait.
 * Blob/FormData download/upload için kullanılır.
 */
export async function authedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  return fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
}

/**
 * Excel/PDF dosyası indir + tarayıcı download'u tetikle.
 * 13+ export* method'unda kopya-yapıştır pattern'i kapsüller.
 */
export async function downloadBlob(path: string, filename: string): Promise<void> {
  const res = await authedFetch(path);
  if (!res.ok) throw new Error("İndirme başarısız");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Excel import — multipart/form-data upload.
 * import* method'larında kopya-yapıştır pattern'i kapsüller.
 * Hata: server detail dict varsa formatErrorDetail ile insan-okunaklı stringe çevir.
 */
export async function uploadForm<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await authedFetch(path, { method: "POST", body: form });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({ detail: res.statusText }))) as { detail?: unknown };
    throw new Error(formatErrorDetail(err.detail) || res.statusText);
  }
  return (await res.json()) as T;
}
