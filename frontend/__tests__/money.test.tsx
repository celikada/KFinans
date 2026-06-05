import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const getRates = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { getRates: (...a: unknown[]) => getRates(...a) },
  CURRENCIES: ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"],
}));

import { Money, formatTlAs, CURRENCY_SYMBOLS } from "@/app/_components/Money";
import { DISPLAY_CURRENCY_CHANGED } from "@/lib/defaultCurrency";

describe("formatTlAs (saf dönüşüm)", () => {
  it("TRY → ham TL + ₺ (kur sorgusu yok)", () => {
    const s = formatTlAs(1000, "TRY", null);
    expect(s).toContain("₺");
    expect(s).toContain("1.000");
  });

  it("USD + kur → tl/kur + $ ", () => {
    const s = formatTlAs(4000, "USD", { USD: 40 });
    expect(s).toContain(CURRENCY_SYMBOLS.USD);
    expect(s).toContain("100"); // 4000 / 40
  });

  it("EUR + kur → tl/kur + €", () => {
    const s = formatTlAs(8800, "EUR", { EUR: 44 });
    expect(s).toContain("€");
    expect(s).toContain("200"); // 8800 / 44
  });

  it("kur yoksa (eksik/0) → güvenli TL fallback (₺)", () => {
    expect(formatTlAs(1000, "USD", {})).toContain("₺");
    expect(formatTlAs(1000, "USD", { USD: 0 })).toContain("₺");
    expect(formatTlAs(1000, "USD", null)).toContain("₺");
  });
});

describe("Money bileşeni", () => {
  beforeEach(() => {
    localStorage.clear();
    getRates.mockReset().mockResolvedValue({ rates: { TRY: "1", USD: "40", EUR: "44" } });
  });

  it("varsayılan (TRY) → TL gösterir", async () => {
    render(<Money tl={1234.5} />);
    await waitFor(() => expect(screen.getByText(/₺/)).toBeInTheDocument());
  });

  it("görüntüleme para birimi USD → $ gösterir ve kura böler", async () => {
    localStorage.setItem("kfinans_default_currency", "USD");
    render(<Money tl={4000} />);
    await waitFor(() => expect(screen.getByText(/\$/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/100/)).toBeInTheDocument());
  });

  it("string tl değerini parse eder", async () => {
    render(<Money tl="2500" />);
    await waitFor(() => expect(screen.getByText(/2\.500/)).toBeInTheDocument());
  });

  it("geçersiz tl → 0 gösterir", async () => {
    render(<Money tl={null} />);
    await waitFor(() => expect(screen.getByText(/0,00 ₺/)).toBeInTheDocument());
  });

  it("para birimi değişim olayında günceller", async () => {
    localStorage.setItem("kfinans_default_currency", "TRY");
    render(<Money tl={4000} />);
    await waitFor(() => expect(screen.getByText(/₺/)).toBeInTheDocument());
    // Ayarlar'dan USD'ye geçiş simülasyonu
    localStorage.setItem("kfinans_default_currency", "USD");
    globalThis.dispatchEvent(new CustomEvent(DISPLAY_CURRENCY_CHANGED));
    await waitFor(() => expect(screen.getByText(/\$/)).toBeInTheDocument());
  });
});
