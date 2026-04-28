const BASE = "http://localhost:8000/api/v1";

function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }
    ),

  tefasPreview: (holdings: { code: string; quantity: number; name: string }[]) =>
    request<TefasPosition[]>("/portfolio/tefas/preview", {
      method: "POST",
      body: JSON.stringify(holdings),
    }),
};

export interface TefasPosition {
  code: string;
  name: string;
  quantity: string;
  unit_price_tl: string;
  total_value_tl: string;
}
