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
