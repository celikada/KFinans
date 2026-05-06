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
    throw new Error(formatErrorDetail(err.detail) || res.statusText);
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

  getPortfolioHistory: (limit = 12) =>
    request<SnapshotHistoryDTO[]>(`/portfolio/history?limit=${limit}`),

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
  importStockMkk: async (file: File): Promise<StockHoldingDTO[]> => {
    const token = getToken();
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

  importTefasMkk: async (file: File): Promise<TefasHoldingDTO[]> => {
    const token = getToken();
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
    const token = getToken();
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
    const token = getToken();
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

export interface SnapshotHealthIssue {
  source: string;
  code: string;
  msg: string;
  level?: "warn" | "info";  // varsayılan 'warn' — eski kayıtlarda olmayabilir
  chain?: string | null;
  address?: string | null;
  provider?: string | null;
  label?: string | null;
  exchange?: string | null;
  symbol?: string | null;
}

export interface SnapshotHistoryDTO {
  id: string;
  snapshot_date: string;
  total_value_tl: string;
  usd_try_rate?: string | null;
  health_issues?: SnapshotHealthIssue[] | null;
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
  recurring_income_id?: number | null;
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

// Periyodik gelir (recurring_incomes)
export type RecurringIncomeCategory = "salary" | "rental" | "dividend" | "bonus" | "freelance" | "other";
export type RecurringRecurrence = "one_time" | "monthly" | "quarterly" | "biannual" | "yearly" | "custom";

export const RECURRING_INCOME_CATEGORY_LABELS: Record<RecurringIncomeCategory, string> = {
  salary:    "Maaş",
  rental:    "Kira Geliri",
  dividend:  "Temettü / Faiz",
  bonus:     "İkramiye / Prim",
  freelance: "Serbest Meslek",
  other:     "Diğer",
};

export const RECURRING_RECURRENCE_LABELS: Record<RecurringRecurrence, string> = {
  one_time:  "Tek seferlik",
  monthly:   "Aylık",
  quarterly: "3 aylık",
  biannual:  "6 aylık",
  yearly:    "Yıllık",
  custom:    "Özel aylar",
};

export interface RecurringIncomeInput {
  title: string;
  amount: number;
  category: RecurringIncomeCategory;
  recurrence: RecurringRecurrence;
  months?: number[] | null;
  day_of_month: number;
  start_date: string;     // YYYY-MM-DD
  end_date?: string | null;
  notes?: string | null;
}

export interface RecurringIncomeDTO {
  id: number;
  title: string;
  amount: string;
  category: RecurringIncomeCategory;
  recurrence: RecurringRecurrence;
  months: number[] | null;
  day_of_month: number;
  start_date: string;
  end_date: string | null;
  notes: string | null;
}

export interface IncomeDashboardDTO {
  year: number;
  month: number;
  this_month_actual: string;
  ytd_actual: string;
  this_month_recurring: string;
  ytd_recurring: string;
  remaining_year_recurring: string;
  year_total_estimate: string;
}

export interface RealizeResultDTO {
  realized: number;
  skipped: number;
  income_ids: number[];
}

// Kredi kartları (Faz 3 — manuel giriş)
export interface CreditCardInput {
  name: string;
  bank_name?: string | null;
  last_4?: string | null;
  credit_limit?: number | string | null;
  statement_day: number;
  payment_due_day: number;
  current_period_debt?: number | string;
  notes?: string | null;
}

export interface CreditCardDTO {
  id: number;
  name: string;
  bank_name: string | null;
  last_4: string | null;
  credit_limit: string | null;
  statement_day: number;
  payment_due_day: number;
  current_period_debt: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  // Hesaplanmış (server-side)
  unpaid_statement_total: string;
  unpaid_statement_count: number;
  future_installment_total: string;
  period_debt: string;
  total_debt: string;
}

export interface CreditCardSummaryDTO {
  cards: CreditCardDTO[];
  total_period_debt: string;
  total_debt: string;
  total_current_period_debt: string;  // legacy
}

// Ekstre
export interface StatementInput {
  period_year: number;
  period_month: number;
  statement_amount: number | string;
  statement_date: string;     // YYYY-MM-DD
  due_date: string;
  paid_at?: string | null;    // ISO datetime
  notes?: string | null;
}

export interface StatementDTO {
  id: number;
  card_id: number;
  period_year: number;
  period_month: number;
  statement_amount: string;
  statement_date: string;
  due_date: string;
  paid_at: string | null;
  notes: string | null;
  created_at: string;
}

// Taksit
// total_amount + installments_remaining backend'de otomatik hesaplanır
// (monthly × count = total; first_due_date'ten bugüne kalan = remaining).
export interface InstallmentInput {
  description: string;
  monthly_amount: number | string;
  installments_total: number;
  first_due_date: string;
  notes?: string | null;
}

export interface InstallmentDTO {
  id: number;
  card_id: number;
  description: string;
  total_amount: string;
  monthly_amount: string;
  installments_total: number;
  installments_remaining: number;
  first_due_date: string;
  notes: string | null;
  created_at: string;
}

export interface CreditCardDetailDTO {
  card: CreditCardDTO;
  statements: StatementDTO[];
  installments: InstallmentDTO[];
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

export type CashCurrency = "TRY" | "USD" | "EUR" | "GBP";

export interface CashCreateInput {
  label: string;
  amount: number;
  currency: CashCurrency;
  notes?: string | null;
}

export interface CashDTO {
  id: number;
  label: string;
  amount: string;
  currency: string;
  notes: string | null;
  updated_at: string;
  amount_tl: string;
}

export interface CashSummaryDTO {
  holdings: CashDTO[];
  total_tl: string;
}

// Manuel kripto (API'siz borsalar — BinanceTR, iCrypex vs.)
export type ManualCryptoPriceSource = "auto" | "manual" | "linked";
export type LinkedSource = "binance" | "coingecko" | "tefas" | "commodity";

export interface AssetCatalogItem {
  source: LinkedSource;
  id: string;
  symbol: string | null;
  name: string;
}

export interface ManualCryptoCreateInput {
  exchange: string;
  label?: string | null;
  symbol: string;
  quantity: number | string;
  avg_cost_tl?: number | string | null;
  price_source?: ManualCryptoPriceSource;
  manual_unit_price_tl?: number | string | null;
  linked_source?: LinkedSource | null;
  linked_id?: string | null;
  notes?: string | null;
}

export interface ManualCryptoDTO {
  id: number;
  exchange: string;
  label: string | null;
  symbol: string;
  quantity: string;
  avg_cost_tl: string | null;
  price_source: ManualCryptoPriceSource;
  manual_unit_price_tl: string | null;
  linked_source: LinkedSource | null;
  linked_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManualCryptoPositionDTO {
  id: number;
  exchange: string;
  label: string | null;
  symbol: string;
  quantity: string;
  avg_cost_tl: string | null;
  price_source: ManualCryptoPriceSource;
  manual_unit_price_tl: string | null;
  linked_source: LinkedSource | null;
  linked_id: string | null;
  unit_price_usd: string;
  unit_price_tl: string;
  total_value_tl: string;
  cost_basis_tl: string | null;
  gain_loss_tl: string | null;
  gain_loss_pct: number | null;
  notes: string | null;
}

export interface ManualCryptoSummaryDTO {
  positions: ManualCryptoPositionDTO[];
  total_value_tl: string;
  unknown_symbols: string[];
}

export interface CommoditySummaryDTO {
  positions: CommodityPositionDTO[];
  total_gold_gram: string;
  total_silver_gram: string;
  total_value_tl: string;
  gold_price_tl: string;
  silver_price_tl: string;
  gold_price_available: boolean;
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
