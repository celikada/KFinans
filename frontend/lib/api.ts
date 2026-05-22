const BASE = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

function getAccessToken() {
  return typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
}

function getRefreshToken() {
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
function formatErrorDetail(detail: unknown): string {
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

async function request<T>(
  path: string,
  options: RequestInit = {},
  _isRetry = false,
): Promise<T> {
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
  if (
    res.status === 401 &&
    typeof window !== "undefined" &&
    !_isRetry &&
    path !== "/auth/refresh"
  ) {
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

import type {
  AssetCatalogItem,
  BesHoldingDTO,
  BudgetComparisonDTO,
  BudgetDTO,
  CashCreateInput,
  CashFlowYearDTO,
  CashSummaryDTO,
  CommodityDTO,
  CommodityInput,
  CommoditySummaryDTO,
  CreditCardDetailDTO,
  CreditCardInput,
  CreditCardSummaryDTO,
  CryptoPositionDTO,
  ExpenseDTO,
  ExpenseInput,
  ExpenseSummaryDTO,
  ForecastResultDTO,
  GoalCurrency,
  GoalDTO,
  IncomeDTO,
  IncomeDashboardDTO,
  IncomeInput,
  IncomeSummaryDTO,
  InstallmentInput,
  IntegrationDTO,
  LinkedSource,
  LoginResponseDTO,
  ManualCryptoCreateInput,
  ManualCryptoSummaryDTO,
  MfaEnableResponse,
  MfaSetupResponse,
  MfaStatusResponse,
  MfaVerifyResponse,
  PlannedExpenseDTO,
  PlannedExpenseInput,
  RealizeResultDTO,
  RecurringIncomeDTO,
  RecurringIncomeInput,
  RegisterResponseDTO,
  StatementInput,
  StockHoldingDTO,
  TefasHoldingDTO,
  UserMeDTO,
  WalletDTO,
  WalletPositionDTO,
} from "./api/types";

// Type/DTO/const tanımları `./api/types.ts`'e taşındı (1511 → ~837 satır refactor).
// Public yüzey aynı: consumer'lar `import { ExpenseDTO } from "@/lib/api"` yazabilir.
export * from "./api/types";

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponseDTO>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }
    ),

  // MFA (TOTP) — Audit #5
  mfaStatus: () => request<MfaStatusResponse>("/mfa/status"),

  mfaSetup: () =>
    request<MfaSetupResponse>("/mfa/setup", { method: "POST" }),

  mfaEnable: (totp_code: string) =>
    request<MfaEnableResponse>("/mfa/enable", {
      method: "POST",
      body: JSON.stringify({ totp_code }),
    }),

  mfaDisable: (totp_code: string) =>
    request<{ detail: string }>("/mfa/disable", {
      method: "POST",
      body: JSON.stringify({ totp_code }),
    }),

  // pre_mfa_token Authorization header'inda yollanir — request() helper'i
  // localStorage'daki access_token'i kullanacagindan dogrudan fetch ile yapariz.
  mfaVerify: async (preMfaToken: string, payload: { totp_code?: string; recovery_code?: string }) => {
    const res = await fetch(`${BASE}/mfa/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${preMfaToken}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(formatErrorDetail(err.detail) || res.statusText);
    }
    return (await res.json()) as MfaVerifyResponse;
  },

  logout: (refreshToken?: string) => {
    // Saklı refresh token'ı blacklist'e gönder (FAZ C4 rotation + logout
    // birlikte → tüm token'lar iptal). Çağıran parametre verirse o öncelikli.
    const refresh = refreshToken ?? getRefreshToken();
    return request<{ detail: string }>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refresh }),
    });
  },

  register: (email: string, password: string, risk_profile: string, age_confirmed: boolean) =>
    request<RegisterResponseDTO>("/auth/register", {
      method: "POST",
      // COMP-010 (FAZ H): age_confirmed zorunlu — backend False ise 422 doner
      body: JSON.stringify({ email, password, risk_profile, age_confirmed }),
    }),

  verifyEmail: (token: string) =>
    request<{ detail: string }>(`/auth/verify-email?token=${encodeURIComponent(token)}`),

  resendVerification: (email: string) =>
    request<{ detail: string }>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  getIntegrations: () => request<IntegrationDTO[]>("/integrations"),

  addIntegration: (provider: string, api_key: string, api_secret?: string, extra_token?: string) =>
    request<IntegrationDTO>("/integrations", {
      method: "POST",
      body: JSON.stringify({ provider, api_key, api_secret, extra_token }),
    }),

  removeIntegration: (provider: string) =>
    request<void>(`/integrations/${provider}`, { method: "DELETE" }),

  getCryptoPositions: () => request<{ positions: CryptoPositionDTO[]; errors: Record<string, string> }>("/portfolio/crypto"),

  previewSnapshot: () =>
    request<{
      total_value_tl: string;
      asset_count: number;
      issues: SnapshotHealthIssue[];
      usd_try_rate: string | null;
      saved: boolean;
    }>("/portfolio/snapshot/preview", { method: "POST" }),

  createSnapshot: (force = false) =>
    request<{
      id: string;
      snapshot_date: string;
      total_value_tl: string;
      usd_try_rate?: string | null;
      health_issues?: SnapshotHealthIssue[] | null;
      asset_positions: unknown[];
    }>(
      `/portfolio/snapshot${force ? "?force=true" : ""}`,
      { method: "POST" }
    ),

  getPortfolioHistory: (params: { limit?: number; year?: number } = {}) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(params.limit ?? 100));
    if (params.year !== undefined) qs.set("year", String(params.year));
    return request<SnapshotHistoryDTO[]>(`/portfolio/history?${qs}`);
  },
  getPortfolioHistoryYears: () => request<number[]>("/portfolio/history/years"),

  deleteSnapshot: (snapshotDate: string) =>
    request<void>(`/portfolio/snapshot/${snapshotDate}`, { method: "DELETE" }),

  // Harcama (Faz 3 MVP — manuel giris)
  listExpenses: (params: { year?: number; month?: number; category?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.year !== undefined) q.set("year", String(params.year));
    if (params.month !== undefined) q.set("month", String(params.month));
    if (params.category) q.set("category", params.category);
    const qs = q.toString();
    return request<ExpenseDTO[]>(`/expenses${qs ? `?${qs}` : ""}`);
  },

  createExpense: (payload: ExpenseInput) =>
    request<ExpenseDTO>("/expenses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateExpense: (id: number, payload: Partial<ExpenseInput>) =>
    request<ExpenseDTO>(`/expenses/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deleteExpense: (id: number) =>
    request<void>(`/expenses/${id}`, { method: "DELETE" }),

  getExpenseSummary: (year: number, month: number) =>
    request<ExpenseSummaryDTO>(`/expenses/summary?year=${year}&month=${month}`),

  getWallets: () => request<WalletDTO[]>("/wallets"),
  addWallet: (chain: string, address: string, label?: string) =>
    request<WalletDTO>("/wallets", {
      method: "POST",
      body: JSON.stringify({ chain, address, label }),
    }),
  removeWallet: (walletId: string) =>
    request<void>(`/wallets/${walletId}`, { method: "DELETE" }),
  getWalletPositions: () =>
    request<{ positions: WalletPositionDTO[]; errors: Record<string, string> }>("/portfolio/wallets"),

  getStockHoldings: () => request<StockHoldingDTO[]>("/portfolio/stocks/holdings"),
  saveStockHoldings: (holdings: StockHoldingDTO[]) =>
    request<StockHoldingDTO[]>("/portfolio/stocks/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),
  stockPreview: (holdings: StockHoldingDTO[]) =>
    request<StockPositionDTO[]>("/portfolio/stocks/preview", {
      method: "POST",
      body: JSON.stringify(holdings),
    }),
  exportStockHoldings: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/stocks/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hisse-senedi.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importStockMkk: async (file: File): Promise<StockHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/stocks/import-mkk`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  importStockHoldings: async (file: File): Promise<StockHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/stocks/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  exportWallets: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/wallets/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "blockchain-cüzdanları.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  importWallets: async (file: File): Promise<WalletDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/wallets/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  getTefasHoldings: () =>
    request<TefasHoldingDTO[]>("/portfolio/tefas/holdings"),

  saveTefasHoldings: (holdings: TefasHoldingDTO[]) =>
    request<TefasHoldingDTO[]>("/portfolio/tefas/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),

  tefasPreview: (holdings: TefasHoldingDTO[]) =>
    request<TefasPosition[]>("/portfolio/tefas/preview", {
      method: "POST",
      body: JSON.stringify(holdings),
    }),

  exportTefasHoldings: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/tefas/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tefas-holdingleri.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  importTefasHoldings: async (file: File): Promise<TefasHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/tefas/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  importTefasMkk: async (file: File): Promise<TefasHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/tefas/import-mkk`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  // Gelir takibi
  listIncomes: (params: { year?: number; month?: number; category?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.year !== undefined) q.set("year", String(params.year));
    if (params.month !== undefined) q.set("month", String(params.month));
    if (params.category) q.set("category", params.category);
    const qs = q.toString();
    return request<IncomeDTO[]>(`/income${qs ? `?${qs}` : ""}`);
  },
  createIncome: (payload: IncomeInput) =>
    request<IncomeDTO>("/income", { method: "POST", body: JSON.stringify(payload) }),
  updateIncome: (id: number, payload: Partial<IncomeInput>) =>
    request<IncomeDTO>(`/income/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteIncome: (id: number) =>
    request<void>(`/income/${id}`, { method: "DELETE" }),
  getIncomeSummary: (year: number, month: number) =>
    request<IncomeSummaryDTO>(`/income/summary?year=${year}&month=${month}`),

  // Periyodik gelir (recurring_incomes)
  getIncomeDashboard: (year: number, month: number) =>
    request<IncomeDashboardDTO>(`/income/dashboard?year=${year}&month=${month}`),
  listRecurringIncomes: () => request<RecurringIncomeDTO[]>("/income/recurring"),
  createRecurringIncome: (payload: RecurringIncomeInput) =>
    request<RecurringIncomeDTO>("/income/recurring", { method: "POST", body: JSON.stringify(payload) }),
  updateRecurringIncome: (id: number, payload: Partial<RecurringIncomeInput>) =>
    request<RecurringIncomeDTO>(`/income/recurring/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteRecurringIncome: (id: number) =>
    request<void>(`/income/recurring/${id}`, { method: "DELETE" }),
  realizeRecurringPeriod: (id: number, year: number, month: number) =>
    request<RealizeResultDTO>(`/income/recurring/${id}/realize`, {
      method: "POST",
      body: JSON.stringify({ year, month }),
    }),
  realizeRecurringPast: (id: number) =>
    request<RealizeResultDTO>(`/income/recurring/${id}/realize-past`, { method: "POST" }),
  realizeAllRecurringPast: () =>
    request<RealizeResultDTO>(`/income/recurring/realize-all-past`, { method: "POST" }),

  // Yıllık nakit akış (geçmiş + gelecek)
  getCashFlow: (year: number) => request<CashFlowYearDTO>(`/cash-flow?year=${year}`),

  // Rapor indirme yardımcısı (hem Excel hem PDF için)
  downloadReport: async (path: string, filename: string) => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Rapor indirilemedi");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Finansal hedef
  getGoal: () => request<GoalDTO>("/user/goal"),
  setGoal: (amount: number, currency: GoalCurrency) =>
    request<GoalDTO>("/user/goal", {
      method: "PUT",
      body: JSON.stringify({ amount, currency }),
    }),

  // Planlı ödemeler (Faz 3)
  listPlannedExpenses: () => request<PlannedExpenseDTO[]>("/planned-expenses"),

  createPlannedExpense: (payload: PlannedExpenseInput) =>
    request<PlannedExpenseDTO>("/planned-expenses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updatePlannedExpense: (id: number, payload: Partial<PlannedExpenseInput>) =>
    request<PlannedExpenseDTO>(`/planned-expenses/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deletePlannedExpense: (id: number) =>
    request<void>(`/planned-expenses/${id}`, { method: "DELETE" }),

  getForecast: (year: number) =>
    request<ForecastResultDTO>(`/planned-expenses/forecast?year=${year}`),

  // Kıymetli madenler
  getCommodities: () => request<CommoditySummaryDTO>("/portfolio/commodities"),
  createCommodity: (payload: CommodityInput) =>
    request<CommodityDTO>("/portfolio/commodities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCommodity: (id: number, payload: { quantity?: number; notes?: string | null }) =>
    request<CommodityDTO>(`/portfolio/commodities/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteCommodity: (id: number) =>
    request<void>(`/portfolio/commodities/${id}`, { method: "DELETE" }),
  exportCommodities: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/commodities/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "altin-gumus.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importCommodities: async (file: File): Promise<CommodityDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/commodities/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  // Harcama Excel export/import
  exportExpenses: async (year?: number, month?: number) => {
    const token = getAccessToken();
    const q = new URLSearchParams();
    if (year !== undefined) q.set("year", String(year));
    if (month !== undefined) q.set("month", String(month));
    const qs = q.toString();
    const res = await fetch(`${BASE}/expenses/export${qs ? `?${qs}` : ""}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "harcamalar.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importExpenses: async (file: File): Promise<ExpenseDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/expenses/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  // Gelir Excel export/import
  exportIncomes: async (year?: number, month?: number) => {
    const token = getAccessToken();
    const q = new URLSearchParams();
    if (year !== undefined) q.set("year", String(year));
    if (month !== undefined) q.set("month", String(month));
    const qs = q.toString();
    const res = await fetch(`${BASE}/income/export${qs ? `?${qs}` : ""}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "gelirler.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  importIncomes: async (file: File): Promise<IncomeDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/income/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },

  // Bütçe vs. Gerçekleşen
  listBudgets: () => request<BudgetDTO[]>("/budgets"),
  upsertBudget: (category: string, amount: number) =>
    request<BudgetDTO>(`/budgets/${category}`, {
      method: "PUT",
      body: JSON.stringify({ amount }),
    }),
  deleteBudget: (category: string) =>
    request<void>(`/budgets/${category}`, { method: "DELETE" }),
  getBudgetComparison: (year: number, month: number) =>
    request<BudgetComparisonDTO[]>(`/budgets/comparison?year=${year}&month=${month}`),

  // Kullanıcı profili & ayarlar
  getMe: () => request<UserMeDTO>("/user/me"),

  getUsdRate: () => request<{ usd_try: string }>("/portfolio/usd-rate"),

  // Nakit (Faz 3 — manuel giriş)
  listCash: () => request<CashSummaryDTO>("/cash"),
  createCash: (payload: CashCreateInput) =>
    request<CashDTO>("/cash", { method: "POST", body: JSON.stringify(payload) }),
  updateCash: (id: number, payload: Partial<CashCreateInput>) =>
    request<CashDTO>(`/cash/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCash: (id: number) =>
    request<void>(`/cash/${id}`, { method: "DELETE" }),

  // Manuel kripto (API'siz borsalar — BinanceTR / iCrypex vs.)
  listManualCrypto: () => request<ManualCryptoSummaryDTO>("/manual-crypto"),
  createManualCrypto: (payload: ManualCryptoCreateInput) =>
    request<ManualCryptoDTO>("/manual-crypto", { method: "POST", body: JSON.stringify(payload) }),
  updateManualCrypto: (id: number, payload: Partial<ManualCryptoCreateInput>) =>
    request<ManualCryptoDTO>(`/manual-crypto/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteManualCrypto: (id: number) =>
    request<void>(`/manual-crypto/${id}`, { method: "DELETE" }),
  exportManualCrypto: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/manual-crypto/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "manuel-kripto.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },
  searchAssetCatalog: (params: { q?: string; source?: LinkedSource; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q !== undefined) qs.set("q", params.q);
    if (params.source) qs.set("source", params.source);
    if (params.limit) qs.set("limit", String(params.limit));
    return request<AssetCatalogItem[]>(`/asset-catalog${qs.toString() ? `?${qs}` : ""}`);
  },

  // Kredi kartları (Faz 3 — manuel giriş)
  listCreditCards: () => request<CreditCardSummaryDTO>("/credit-cards"),
  createCreditCard: (payload: CreditCardInput) =>
    request<CreditCardDTO>("/credit-cards", { method: "POST", body: JSON.stringify(payload) }),
  updateCreditCard: (id: number, payload: Partial<CreditCardInput>) =>
    request<CreditCardDTO>(`/credit-cards/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCreditCard: (id: number) =>
    request<void>(`/credit-cards/${id}`, { method: "DELETE" }),
  getCreditCardDetail: (id: number) =>
    request<CreditCardDetailDTO>(`/credit-cards/${id}`),
  // Ekstreler
  createStatement: (cardId: number, payload: StatementInput) =>
    request<StatementDTO>(`/credit-cards/${cardId}/statements`, {
      method: "POST", body: JSON.stringify(payload),
    }),
  updateStatement: (cardId: number, statementId: number, payload: Partial<StatementInput>) =>
    request<StatementDTO>(`/credit-cards/${cardId}/statements/${statementId}`, {
      method: "PUT", body: JSON.stringify(payload),
    }),
  deleteStatement: (cardId: number, statementId: number) =>
    request<void>(`/credit-cards/${cardId}/statements/${statementId}`, { method: "DELETE" }),
  // Taksitler
  createInstallment: (cardId: number, payload: InstallmentInput) =>
    request<InstallmentDTO>(`/credit-cards/${cardId}/installments`, {
      method: "POST", body: JSON.stringify(payload),
    }),
  updateInstallment: (cardId: number, installmentId: number, payload: Partial<InstallmentInput>) =>
    request<InstallmentDTO>(`/credit-cards/${cardId}/installments/${installmentId}`, {
      method: "PUT", body: JSON.stringify(payload),
    }),
  deleteInstallment: (cardId: number, installmentId: number) =>
    request<void>(`/credit-cards/${cardId}/installments/${installmentId}`, { method: "DELETE" }),

  importManualCrypto: async (file: File): Promise<{ imported: number; errors: string[] }> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/manual-crypto/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : res.statusText);
    }
    return res.json();
  },
  updateProfile: (risk_profile: string) =>
    request<UserMeDTO>("/user/profile", {
      method: "PUT",
      body: JSON.stringify({ risk_profile }),
    }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("/user/password", {
      method: "PUT",
      body: JSON.stringify({ current_password, new_password }),
    }),
  deleteAccount: () =>
    request<{ detail: string }>("/user/me", { method: "DELETE" }),

  getBesHoldings: () => request<BesHoldingDTO[]>("/portfolio/bes/holdings"),

  saveBesHoldings: (holdings: BesHoldingDTO[]) =>
    request<BesHoldingDTO[]>("/portfolio/bes/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),

  exportBesHoldings: async () => {
    const token = getAccessToken();
    const res = await fetch(`${BASE}/portfolio/bes/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Export başarısız");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "bes-holdingleri.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  },

  importBesHoldings: async (file: File): Promise<BesHoldingDTO[]> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/portfolio/bes/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    return res.json();
  },
};

