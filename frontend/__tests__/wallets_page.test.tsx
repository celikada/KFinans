import { describe, expect, it, beforeEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// STABIL router/i18n stub (yeni referans → useEffect sonsuz refetch).
const routerStub = { replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routerStub }));

const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/TLValue", () => ({
  TLValue: ({ tl }: { tl: number }) => <span>{String(tl)}</span>,
}));

const getWallets = vi.fn();
const getWalletPositions = vi.fn();
const removeWallet = vi.fn();
const exportWalletsFull = vi.fn();
const exportWallets = vi.fn();
const importWallets = vi.fn();
const addWallet = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getWallets: (...a: unknown[]) => getWallets(...a),
    getWalletPositions: (...a: unknown[]) => getWalletPositions(...a),
    removeWallet: (...a: unknown[]) => removeWallet(...a),
    exportWalletsFull: (...a: unknown[]) => exportWalletsFull(...a),
    exportWallets: (...a: unknown[]) => exportWallets(...a),
    importWallets: (...a: unknown[]) => importWallets(...a),
    addWallet: (...a: unknown[]) => addWallet(...a),
  },
}));

import WalletsPage from "@/app/dashboard/wallets/page";

const WALLET = { id: "w-1", chain: "ethereum", address: "0x1234...7890", label: "Ana", is_active: true };

beforeEach(() => {
  vi.clearAllMocks();
  getWallets.mockResolvedValue([WALLET]);
  getWalletPositions.mockResolvedValue({ positions: [], errors: {} });
});

describe("WalletsPage — sifre korumali tam-adres export", () => {
  it("Excel indir → sifre modali acilir, dogru sifre → exportWalletsFull cagrilir", async () => {
    exportWalletsFull.mockResolvedValue(undefined);
    render(<WalletsPage />);
    // Liste yuklensin (export butonu hasWallets ile aktif olur)
    fireEvent.click(await screen.findByRole("button", { name: "form.excelDownload" }));
    // Modal acildi
    expect(await screen.findByText("content.wallets.exportPasswordTitle")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("content.wallets.passwordPlaceholder"), {
      target: { value: "gizli-sifre" },
    });
    fireEvent.click(screen.getByRole("button", { name: "content.wallets.exportFullBtn" }));
    await waitFor(() => expect(exportWalletsFull).toHaveBeenCalledWith("gizli-sifre"));
  });

  it("bos sifre → exportWalletsFull cagrilmaz, hata gosterilir", async () => {
    render(<WalletsPage />);
    // Wallet yuklensin → export butonu (disabled={!hasWallets}) aktiflesir.
    await screen.findByRole("button", { name: "content.wallets.remove" });
    fireEvent.click(screen.getByRole("button", { name: "form.excelDownload" }));
    // Modal acilsin (title) — sonra bos sifreyle submit
    expect(await screen.findByText("content.wallets.exportPasswordTitle")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "content.wallets.exportFullBtn" }));
    expect(await screen.findByText("content.wallets.exportPasswordRequired")).toBeInTheDocument();
    expect(exportWalletsFull).not.toHaveBeenCalled();
  });

  it("yanlis sifre (403) → backend hata mesaji gosterilir", async () => {
    exportWalletsFull.mockRejectedValue(new Error("Şifre hatalı — tam adres verilmedi."));
    render(<WalletsPage />);
    // Wallet yuklensin → export butonu (disabled={!hasWallets}) aktiflesir.
    await screen.findByRole("button", { name: "content.wallets.remove" });
    fireEvent.click(screen.getByRole("button", { name: "form.excelDownload" }));
    fireEvent.change(await screen.findByPlaceholderText("content.wallets.passwordPlaceholder"), {
      target: { value: "yanlis" },
    });
    fireEvent.click(screen.getByRole("button", { name: "content.wallets.exportFullBtn" }));
    expect(await screen.findByText("Şifre hatalı — tam adres verilmedi.")).toBeInTheDocument();
  });
});

describe("WalletsPage — silme hatasi sessiz yutulmaz", () => {
  it("removeWallet hata atarsa posError gosterilir", async () => {
    removeWallet.mockRejectedValue(new Error("backend cokme"));
    render(<WalletsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "content.wallets.remove" }));
    expect(await screen.findByText("backend cokme")).toBeInTheDocument();
  });
});
