/**
 * Dashboard ilk-acilis cache'i (UX-iyilestirme).
 *
 * Problem: `app/dashboard/page.tsx` ilk acilista ~14 paralel API fetch yapar
 * (kripto/blockchain saniyeler surer). Tum degerler gelene kadar kartlar bos
 * gosterir -> ilk acilis yavas hissettirir.
 *
 * Cozum: her basarili degeri localStorage'a cache'le; sonraki acilista once
 * cache'lenmis degerleri ANINDA goster + "guncelleniyor" gostergesi; fresh
 * fetch bitince degerleri tazele.
 *
 * Cache KULLANICIYA OZEL: key'e scope (access token'dan turetilen) dahil
 * edilir. Baska kullanici login olursa eski cache gorunmez. Logout'ta
 * `clearDashboardCache()` tum cache'leri temizler.
 *
 * Saklanan: numeric total'lar + count'lar + kompakt topX listeleri. Hassas
 * ham veri (adres, miktar detayi) saklanmaz.
 */

const CACHE_PREFIX = "kfinans-dash-v1-";
const TTL_MS = 24 * 60 * 60 * 1000; // 24 saat

export interface CachedTopItem {
  readonly label: string;
  readonly value: number;
}

/**
 * Dashboard kart degerlerinin serialize edilebilir anlik goruntusu.
 * Tum alanlar opsiyonel — fetch henuz gelmemis/bos kartlar atlanir.
 */
export interface DashboardSnapshot {
  tefasTotal: number | null;
  tefasFundCount: number;
  tefasTop: CachedTopItem[];

  cryptoTotal: number | null;
  cryptoTop: CachedTopItem[];

  stockTotal: number | null;
  stockHoldingCount: number;
  stockTop: CachedTopItem[];

  walletTotal: number | null;
  walletTop: CachedTopItem[];

  besTotal: number | null;
  besPlanCount: number;
  besTop: CachedTopItem[];

  expenseTotal: number | null;
  expenseCount: number;
  expenseTop: CachedTopItem[];

  plannedTotal: number | null;

  incomeTotal: number | null;
  incomeCount: number;
  incomeTop: CachedTopItem[];
  incomeYearEstimate: number | null;

  creditCardTotal: number | null;
  creditCardPeriod: number | null;
  creditCardCount: number;

  commodityTotal: number | null;
  commodityCount: number;

  cashTotal: number | null;
  cashCount: number;

  manualCryptoTotal: number | null;
  manualCryptoCount: number;
  manualCryptoTop: CachedTopItem[];

  budgetOverCount: number | null;

  currentMonthNet: number | null;
  nextMonthNet: number | null;

  goalPct: number | null;
  goalPassive: number | null;
}

interface CacheEnvelope {
  savedAt: number;
  data: Partial<DashboardSnapshot>;
}

/**
 * Access token (JWT) payload'indan `sub` claim'ini cikar — kullanici scope'u.
 * Cozulemezse "anon" doner (yine de calisir, sadece kullanicilar arasi
 * izolasyon olmaz; logout temizligi backstop saglar).
 */
export function deriveScope(accessToken: string | null): string {
  if (!accessToken) return "anon";
  const parts = accessToken.split(".");
  if (parts.length !== 3) return "anon";
  try {
    // JWT base64url payload — atob base64 ister; url-safe karakterleri donustur.
    const payload = parts[1].replaceAll("-", "+").replaceAll("_", "/");
    const json = atob(payload);
    const claims = JSON.parse(json) as { sub?: string | number };
    const sub = claims.sub;
    if (sub === undefined || sub === null) return "anon";
    // sub PII (email) olabilir; ham saklamak yerine basit deterministik hash.
    return hashString(String(sub));
  } catch {
    return "anon";
  }
}

/** Kucuk, deterministik, non-cryptographic hash (FNV-1a benzeri). Scope key icin yeterli. */
function hashString(s: string): string {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.codePointAt(i) ?? 0;
    h = Math.imul(h, 16777619);
  }
  // unsigned hex
  return (h >>> 0).toString(36);
}

function cacheKey(scope: string): string {
  return `${CACHE_PREFIX}${scope}`;
}

/**
 * Verilen scope icin cache'lenmis dashboard degerlerini yukle.
 * Cache yoksa / bozuksa / TTL gectiyse null doner (mevcut loading davranisi).
 */
export function loadCache(scope: string): Partial<DashboardSnapshot> | null {
  if (globalThis.window === undefined) return null;
  try {
    const raw = localStorage.getItem(cacheKey(scope));
    if (!raw) return null;
    const env = JSON.parse(raw) as CacheEnvelope;
    if (!env || typeof env.savedAt !== "number" || typeof env.data !== "object" || env.data === null) {
      return null;
    }
    if (Date.now() - env.savedAt > TTL_MS) {
      localStorage.removeItem(cacheKey(scope));
      return null;
    }
    return env.data;
  } catch {
    return null;
  }
}

/**
 * Scope icin dashboard degerlerini kaydet. Mevcut cache ile MERGE eder —
 * her fetch geldikce kismi guncelleme yapilabilir (eski degerler korunur).
 */
export function saveCache(scope: string, partial: Partial<DashboardSnapshot>): void {
  if (globalThis.window === undefined) return;
  try {
    const existing = loadCache(scope) ?? {};
    const env: CacheEnvelope = {
      savedAt: Date.now(),
      data: { ...existing, ...partial },
    };
    localStorage.setItem(cacheKey(scope), JSON.stringify(env));
  } catch {
    // localStorage dolu/devre disi — cache best-effort, sessizce yut.
  }
}

/**
 * Tum dashboard cache'lerini temizle (logout). Scope bilinmedigi icin
 * prefix'le baslayan tum key'leri sil.
 */
export function clearDashboardCache(): void {
  if (globalThis.window === undefined) return;
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(CACHE_PREFIX)) toRemove.push(key);
    }
    for (const key of toRemove) localStorage.removeItem(key);
  } catch {
    // best-effort
  }
}
