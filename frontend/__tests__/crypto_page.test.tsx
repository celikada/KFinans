import { describe, expect, it, beforeEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const routerStub = { replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routerStub }));

const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/app/_components/TLValue", () => ({
  TLValue: ({ tl }: { tl: number }) => <span>{String(tl)}</span>,
}));

const getIntegrations = vi.fn();
const getCryptoPositions = vi.fn();
const removeIntegration = vi.fn();
const exportIntegrationsFull = vi.fn();
const importIntegrations = vi.fn();
const addIntegration = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getIntegrations: (...a: unknown[]) => getIntegrations(...a),
    getCryptoPositions: (...a: unknown[]) => getCryptoPositions(...a),
    removeIntegration: (...a: unknown[]) => removeIntegration(...a),
    exportIntegrationsFull: (...a: unknown[]) => exportIntegrationsFull(...a),
    importIntegrations: (...a: unknown[]) => importIntegrations(...a),
    addIntegration: (...a: unknown[]) => addIntegration(...a),
  },
}));

import CryptoPage from "@/app/dashboard/crypto/page";

beforeEach(() => {
  vi.clearAllMocks();
  getIntegrations.mockResolvedValue([{ id: "i-1", provider: "binance", is_active: true, last_synced_at: null }]);
  getCryptoPositions.mockResolvedValue({ positions: [], errors: {} });
});

describe("CryptoPage — şifre korumalı API key export", () => {
  async function openModal() {
    render(<CryptoPage />);
    const btn = await screen.findByRole("button", { name: "content.crypto.exportKeys" });
    await waitFor(() => expect(btn).toBeEnabled()); // entegrasyon yüklensin
    fireEvent.click(btn);
    expect(await screen.findByText("content.crypto.exportPasswordTitle")).toBeInTheDocument();
  }

  it("doğru şifre → exportIntegrationsFull(password) çağrılır", async () => {
    exportIntegrationsFull.mockResolvedValue(undefined);
    await openModal();
    fireEvent.change(screen.getByPlaceholderText("content.crypto.passwordPlaceholder"), {
      target: { value: "gizli" },
    });
    fireEvent.click(screen.getByRole("button", { name: "content.crypto.exportFullBtn" }));
    await waitFor(() => expect(exportIntegrationsFull).toHaveBeenCalledWith("gizli"));
  });

  it("boş şifre → çağrılmaz, hata gösterilir", async () => {
    await openModal();
    fireEvent.click(screen.getByRole("button", { name: "content.crypto.exportFullBtn" }));
    expect(await screen.findByText("content.crypto.exportPasswordRequired")).toBeInTheDocument();
    expect(exportIntegrationsFull).not.toHaveBeenCalled();
  });

  it("yanlış şifre (403) → backend hata mesajı gösterilir", async () => {
    exportIntegrationsFull.mockRejectedValue(new Error("Şifre hatalı — API anahtarları verilmedi."));
    await openModal();
    fireEvent.change(screen.getByPlaceholderText("content.crypto.passwordPlaceholder"), {
      target: { value: "yanlis" },
    });
    fireEvent.click(screen.getByRole("button", { name: "content.crypto.exportFullBtn" }));
    expect(await screen.findByText("Şifre hatalı — API anahtarları verilmedi.")).toBeInTheDocument();
  });
});
