import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const i18nStub = { t: (k: string) => k, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

vi.mock("@/lib/format", () => ({ shortAddr: (a: string) => a }));

import { WalletList } from "@/app/dashboard/wallets/_components/WalletList";

const WALLETS = [
  { id: "w-1", chain: "ethereum", address: "0x1234...7890", label: "Ana", is_active: true },
  { id: "w-2", chain: "bitcoin", address: "bc1q...0001", label: "Soğuk", is_active: true },
];

describe("WalletList — per-cüzdan ⚠ uyarısı", () => {
  it("walletErrors[id] olan cüzdan satırında ⚠ gösterir, olmayan göstermez", () => {
    render(
      <WalletList
        wallets={WALLETS}
        removing={null}
        onRemove={() => {}}
        walletErrors={{ "w-2": "Zaman aşımı (ağ/RPC yavaş)" }}
      />,
    );
    // ⚠ ikonu (aria-label) yalnız 1 kez (sorunlu w-2 için) görünür.
    const warnings = screen.getAllByLabelText("content.wallets.walletProblem");
    expect(warnings).toHaveLength(1);
    // Hata mesajı tooltip (title) olarak taşınır.
    expect(warnings[0].title).toBe("Zaman aşımı (ağ/RPC yavaş)");
  });

  it("walletErrors yoksa hiç ⚠ gösterilmez", () => {
    render(<WalletList wallets={WALLETS} removing={null} onRemove={() => {}} />);
    expect(screen.queryByLabelText("content.wallets.walletProblem")).toBeNull();
  });
});

describe("WalletList — per-cüzdan yenile ikonu", () => {
  it("yenile ikonuna tıklayınca onRefreshWallet o cüzdanın id'siyle çağrılır", () => {
    const onRefreshWallet = vi.fn();
    render(
      <WalletList
        wallets={WALLETS}
        removing={null}
        onRemove={() => {}}
        onRefreshWallet={onRefreshWallet}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: "content.wallets.refreshWallet" });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[1]); // w-2
    expect(onRefreshWallet).toHaveBeenCalledWith("w-2");
  });

  it("refreshingWalletId eşleşen cüzdanın yenile butonu disabled", () => {
    render(
      <WalletList
        wallets={WALLETS}
        removing={null}
        onRemove={() => {}}
        onRefreshWallet={() => {}}
        refreshingWalletId="w-1"
      />,
    );
    const buttons = screen.getAllByRole("button", { name: "content.wallets.refreshWallet" });
    expect(buttons[0]).toBeDisabled(); // w-1 yenileniyor
    expect(buttons[1]).not.toBeDisabled();
  });

  it("onRefreshWallet verilmezse yenile ikonu render edilmez", () => {
    render(<WalletList wallets={WALLETS} removing={null} onRemove={() => {}} />);
    expect(screen.queryByRole("button", { name: "content.wallets.refreshWallet" })).toBeNull();
  });
});
