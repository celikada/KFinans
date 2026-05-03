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

export interface UserMeDTO {
  email: string;
  risk_profile: "conservative" | "balanced" | "aggressive";
  created_at: string;
  email_verified: boolean;
  credit_balance: number;
}

export const RISK_PROFILE_LABELS: Record<"conservative" | "balanced" | "aggressive", string> = {
  conservative: "Muhafazakâr",
  balanced: "Dengeli",
  aggressive: "Agresif",
};

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
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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
  avg_cost_tl?: number | null;
  distributor?: string | null;
}

export interface StockPositionDTO {
  ticker: string;
  name: string;
  quantity: string;
  currency: string;
  unit_price_original: string;
  unit_price_tl: string;
  total_value_tl: string;
  avg_cost_tl: string | null;
  cost_basis_tl: string | null;
  gain_loss_tl: string | null;
  gain_loss_pct: number | null;
  distributor: string | null;
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
  avg_cost_tl?: number | null;
  distributor?: string | null;
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
  avg_cost_tl: string | null;
  cost_basis_tl: string | null;
  gain_loss_tl: string | null;
  gain_loss_pct: number | null;
  distributor: string | null;
}

export type IncomeCategory =
  | "salary" | "freelance" | "rental" | "dividend" | "bonus" | "sale" | "other";

export const INCOME_CATEGORIES: IncomeCategory[] = [
  "salary", "freelance", "rental", "dividend", "bonus", "sale", "other",
];

export const INCOME_CATEGORY_LABELS: Record<IncomeCategory, string> = {
  salary:    "Maaş",
  freelance: "Serbest Meslek",
  rental:    "Kira Geliri",
  dividend:  "Temettü / Faiz",
  bonus:     "İkramiye / Prim",
  sale:      "Varlık Satışı",
  other:     "Diğer",
};

export interface IncomeInput {
  amount: number;
  category: IncomeCategory;
  date: string;
  description?: string | null;
}

export interface IncomeDTO {
  id: number;
  amount: string;
  category: IncomeCategory;
  date: string;
  description: string | null;
}

export interface IncomeCategoryBreakdownDTO {
  category: IncomeCategory;
  total: string;
  count: number;
}

export interface IncomeSummaryDTO {
  year: number;
  month: number;
  total: string;
  count: number;
  by_category: IncomeCategoryBreakdownDTO[];
}

export type GoalCurrency = "TRY" | "USD" | "EUR" | "GBP";

export const GOAL_CURRENCY_SYMBOLS: Record<GoalCurrency, string> = {
  TRY: "₺", USD: "$", EUR: "€", GBP: "£",
};

export interface GoalDTO {
  goal_amount: string | null;
  goal_currency: GoalCurrency;
  rate_to_tl: string | null;
  monthly_tl: string | null;
  freedom_target_tl: string | null;
  portfolio_value: string | null;
  passive_income_tl: string | null;
  passive_income_foreign: string | null;
  progress_pct: number | null;
  months_covered: number | null;
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

// Kıymetli madenler
export type CommodityUnitType = "gram" | "biga" | "coin";
export type CommodityMetal = "gold" | "silver";
export type CoinType = "ceyrek" | "yarim" | "tam" | "cumhuriyet" | "resat" | "ata";

export const BIGA_GOLD_CODES = ["A01","A02","A03","A04","A05","A06","A07","A08"] as const;
export const BIGA_SILVER_CODES = ["G01","G02","G03","G04","G05","G06","G07"] as const;
export const BIGA_GRAM_WEIGHTS: Record<string, number> = {
  A01: 1, A02: 5, A03: 10, A04: 50, A05: 100, A06: 250, A07: 500, A08: 1000,
  G01: 1, G02: 5, G03: 10, G04: 50, G05: 100, G06: 500, G07: 1000,
};
export const COIN_LABELS: Record<CoinType, string> = {
  ceyrek:     "Çeyrek Altın (~1.75g)",
  yarim:      "Yarım Altın (~3.50g)",
  tam:        "Tam Altın (~7.02g)",
  cumhuriyet: "Cumhuriyet Altını (~7.22g)",
  resat:      "Reşat Altını (~7.22g)",
  ata:        "Ata Altını (~7.22g)",
};
export const COIN_TYPES: CoinType[] = ["ceyrek","yarim","tam","cumhuriyet","resat","ata"];

export interface CommodityInput {
  unit_type: CommodityUnitType;
  metal?: CommodityMetal;
  biga_code?: string;
  coin_type?: CoinType;
  quantity: number;
  notes?: string | null;
}

export interface CommodityDTO {
  id: number;
  unit_type: CommodityUnitType;
  metal: CommodityMetal;
  biga_code: string | null;
  coin_type: CoinType | null;
  quantity: string;
  notes: string | null;
  created_at: string;
}

export interface CommodityPositionDTO extends CommodityDTO {
  gram_equivalent: string;
  total_value_tl: string;
  gold_price_tl: string;
  silver_price_tl: string;
}

export interface CommoditySummaryDTO {
  positions: CommodityPositionDTO[];
  total_gold_gram: string;
  total_silver_gram: string;
  total_value_tl: string;
  gold_price_tl: string;
  silver_price_tl: string;
  silver_price_available: boolean;
}

export interface BudgetDTO {
  id: number;
  category: string;
  amount: string;
  updated_at: string;
}

export interface BudgetComparisonDTO {
  category: string;
  budget_amount: string | null;
  actual_amount: string;
  remaining: string | null;
  pct_used: number | null;
  over_budget: boolean;
}
