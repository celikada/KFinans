import type { WalletDTO, WalletPositionDTO } from "./types";
import { downloadBlob, request, uploadForm } from "./_client";

export const walletsApi = {
  getWallets: () => request<WalletDTO[]>("/wallets"),
  addWallet: (chain: string, address: string, label?: string) =>
    request<WalletDTO>("/wallets", {
      method: "POST",
      body: JSON.stringify({ chain, address, label }),
    }),
  removeWallet: (walletId: string) => request<void>(`/wallets/${walletId}`, { method: "DELETE" }),
  getWalletPositions: () => request<{ positions: WalletPositionDTO[]; errors: Record<string, string> }>("/portfolio/wallets"),

  exportWallets: () => downloadBlob("/wallets/export", "blockchain-cüzdanları.xlsx"),
  importWallets: (file: File) => uploadForm<WalletDTO[]>("/wallets/import", file),
};
