import type { WalletDTO, WalletPositionDTO } from "./types";
import { BASE, getAccessToken, request } from "./_client";

export const walletsApi = {
  getWallets: () => request<WalletDTO[]>("/wallets"),
  addWallet: (chain: string, address: string, label?: string) =>
    request<WalletDTO>("/wallets", {
      method: "POST",
      body: JSON.stringify({ chain, address, label }),
    }),
  removeWallet: (walletId: string) => request<void>(`/wallets/${walletId}`, { method: "DELETE" }),
  getWalletPositions: () => request<{ positions: WalletPositionDTO[]; errors: Record<string, string> }>("/portfolio/wallets"),

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
};
