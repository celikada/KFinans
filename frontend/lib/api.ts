const BASE = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;

function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
}

export function setAuth(token: string) {
  localStorage.setItem("access_token", token);
  document.cookie = `access_token=${token}; path=/; SameSite=Strict`;
}

export function clearAuth() {
  localStorage.removeItem("access_token");
  document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
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
    if (res.status === 401 && typeof window !== "undefined") {
      clearAuth();
      window.location.replace("/login");
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; token_type: string }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }
    ),

  logout: (refreshToken?: string) =>
    request<{ detail: string }>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken ?? null }),
    }),

  register: (email: string, password: string, risk_profile: string) =>
    request<RegisterResponseDTO>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, risk_profile }),
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

  createSnapshot: () =>
    request<{ id: string; snapshot_date: string; total_value_tl: string; asset_positions: unknown[] }>(
      "/portfolio/snapshot",
      { method: "POST" }
    ),

  getPortfolioHistory: (limit = 12) =>
    request<SnapshotHistoryDTO[]>(`/portfolio/history?limit=${limit}`),

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
    const token = getToken();
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
  importStockHoldings: async (file: File): Promise<StockHoldingDTO[]> => {
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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

  getBesHoldings: () => request<BesHoldingDTO[]>("/portfolio/bes/holdings"),

  saveBesHoldings: (holdings: BesHoldingDTO[]) =>
    request<BesHoldingDTO[]>("/portfolio/bes/holdings", {
      method: "PUT",
      body: JSON.stringify(holdings),
    }),

  exportBesHoldings: async () => {
    const token = getToken();
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
    const token = getToken();
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

export interface SnapshotHistoryDTO {
  id: string;
  snapshot_date: string;
  total_value_tl: string;
  asset_positions: Array<{
    id: string;
    asset_type: string;
    provider: string;
    symbol: string;
    name: string;
    total_value_tl: string;
    weight_pct: string;
  }>;
}

export type ExpenseCategory =
  | "food" | "groceries" | "transport" | "bills" | "health"
  | "entertainment" | "clothing" | "home" | "tax" | "other";

export const EXPENSE_CATEGORIES: ExpenseCategory[] = [
  "food", "groceries", "transport", "bills", "health",
  "entertainment", "clothing", "home", "tax", "other",
];

export const EXPENSE_CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  food: "Yiyecek",
  groceries: "Market",
  transport: "Ulaşım",
  bills: "Faturalar",
  health: "Sağlık",
  entertainment: "Eğlence",
  clothing: "Giyim",
  home: "Ev",
  tax: "Vergi",
  other: "Diğer",
};

export interface ExpenseInput {
  amount: number;
  category: ExpenseCategory;
  date: string;        // YYYY-MM-DD
  description?: string | null;
}

export interface ExpenseDTO {
  id: number;
  amount: string;
  category: ExpenseCategory;
  date: string;
  description: string | null;
}

export interface CategoryBreakdownDTO {
  category: ExpenseCategory;
  total: string;
  count: number;
}

export interface ExpenseSummaryDTO {
  year: number;
  month: number;
  total: string;
  count: number;
  by_category: CategoryBreakdownDTO[];
}

export interface RegisterResponseDTO {
  id: string;
  email: string;
  risk_profile: string;
  email_verified: boolean;
  verification_email_sent: boolean;
}

export interface IntegrationDTO {
  id: string;
  provider: string;
  is_active: boolean;
  last_synced_at: string | null;
}

export interface CryptoPositionDTO {
  provider: string;
  symbol: string;
  liquid_quantity: string;
  staked_quantity: string;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
}

export interface StockHoldingDTO {
  ticker: string;
  quantity: number;
  name: string;
}

export interface StockPositionDTO {
  ticker: string;
  name: string;
  quantity: string;
  currency: string;
  unit_price_original: string;
  unit_price_tl: string;
  total_value_tl: string;
}

export interface WalletDTO {
  id: string;
  chain: string;
  address: string;
  label: string | null;
  is_active: boolean;
}

export interface WalletPositionDTO {
  wallet_id: string;
  chain: string;
  address: string;
  label: string | null;
  symbol: string;
  liquid_quantity: string;
  staked_quantity: string;
  pending_rewards: string;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
}

export interface TefasHoldingDTO {
  code: string;
  quantity: number;
  name: string;
}

export interface BesHoldingDTO {
  plan_name: string;
  contract_number?: string | null;
  paid_principal: number | string;
  paid_returns: number | string;
  govt_contribution: number | string;
  govt_returns: number | string;
}

export interface TefasPosition {
  code: string;
  name: string;
  quantity: string;
  unit_price_tl: string;
  total_value_tl: string;
}

export type PlannedCategory = "loan" | "tax" | "insurance" | "subscription" | "rent" | "utility" | "other";
export type PlannedRecurrence = "one_time" | "monthly" | "quarterly" | "biannual" | "yearly" | "custom";

export const PLANNED_CATEGORY_LABELS: Record<PlannedCategory, string> = {
  loan: "Kredi / Borç",
  tax: "Vergi",
  insurance: "Sigorta",
  subscription: "Abonelik",
  rent: "Kira",
  utility: "Fatura",
  other: "Diğer",
};

export const PLANNED_RECURRENCE_LABELS: Record<PlannedRecurrence, string> = {
  one_time: "Tek seferlik",
  monthly: "Aylık",
  quarterly: "3 aylık",
  biannual: "6 aylık",
  yearly: "Yıllık",
  custom: "Özel aylar",
};

export const PLANNED_CATEGORIES: PlannedCategory[] = [
  "loan", "tax", "insurance", "subscription", "rent", "utility", "other",
];

export const PLANNED_RECURRENCES: PlannedRecurrence[] = [
  "one_time", "monthly", "quarterly", "biannual", "yearly", "custom",
];

export const MONTH_NAMES = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

export interface PlannedExpenseInput {
  title: string;
  amount: number;
  is_estimated?: boolean;
  category: PlannedCategory;
  recurrence: PlannedRecurrence;
  months?: number[] | null;
  day_of_month?: number;
  start_date: string;        // YYYY-MM-DD
  end_date?: string | null;
  remaining_count?: number | null;
  notes?: string | null;
}

export interface PlannedExpenseDTO {
  id: number;
  title: string;
  amount: string;
  is_estimated: boolean;
  category: PlannedCategory;
  recurrence: PlannedRecurrence;
  months: number[] | null;
  day_of_month: number;
  start_date: string;
  end_date: string | null;
  remaining_count: number | null;
  notes: string | null;
}

export interface ForecastItemDTO {
  id: number;
  title: string;
  amount: string;
  category: PlannedCategory;
  is_estimated: boolean;
}

export interface ForecastMonthDTO {
  month: number;
  total: string;
  items: ForecastItemDTO[];
}

export interface ForecastResultDTO {
  year: number;
  months: ForecastMonthDTO[];
  year_total: string;
}
