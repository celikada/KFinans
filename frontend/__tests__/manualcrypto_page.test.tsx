import { describe, expect, it, beforeEach, vi } from "vitest";

// v8 coverage instrumentasyonu altinda etkilesimler yavaslayabilir; timeout yukselt.
vi.setConfig({ testTimeout: 30000 });
import { render, screen, waitFor, within } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────
// STABIL router — refresh() useCallback([router, t]) deps; her render'da yeni
// referans donerse effect tekrar tetiklenir.
const replaceMock = vi.fn();
const routerStub = { push: vi.fn(), replace: replaceMock, prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

// i18n — t(key) => key. {symbol}/{positions} gibi placeholder'lar page'de
// .replace() ile islendigi icin key string'in icinde aynen kalir.
// NOT: t STABIL referans olmali — useCallback([router, t]) bagimliligindan
// dolayi her render'da yeni t referansi refresh()'i tekrar tetikler.
vi.mock("@/app/_i18n/I18nProvider", () => {
  const t = (k: string) => k;
  const setLocale = vi.fn();
  return {
    useTranslation: () => ({ t, locale: "tr", setLocale }),
  };
});

// PageHeader — sade baslik.
vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

// TLValue — getUsdRate effect'inden kacin; sade deger goster.
vi.mock("@/app/_components/TLValue", () => ({
  TLValue: ({ tl, className }: { tl: number | string; className?: string }) => (
    <span className={className}>{String(tl)}</span>
  ),
}));

// useConfirm — async confirm. Test bazinda donus degeri ezilebilir.
const confirmResult = { value: true };
vi.mock("@/app/_components/ConfirmDialog", () => ({
  useConfirm: () => (_msg: string) => Promise.resolve(confirmResult.value),
}));

// lib/api — manuel kripto + asset katalog metodlari.
const listManualCrypto = vi.fn();
const createManualCrypto = vi.fn();
const deleteManualCrypto = vi.fn();
const exportManualCrypto = vi.fn();
const importManualCrypto = vi.fn();
const searchAssetCatalog = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    listManualCrypto: (...a: unknown[]) => listManualCrypto(...a),
    createManualCrypto: (...a: unknown[]) => createManualCrypto(...a),
    deleteManualCrypto: (...a: unknown[]) => deleteManualCrypto(...a),
    exportManualCrypto: (...a: unknown[]) => exportManualCrypto(...a),
    importManualCrypto: (...a: unknown[]) => importManualCrypto(...a),
    searchAssetCatalog: (...a: unknown[]) => searchAssetCatalog(...a),
  },
}));

import ManualCryptoPage from "@/app/dashboard/manual-crypto/page";

// ─── Fixtures ────────────────────────────────────────────────────────────────
function pos(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    exchange: "binancetr",
    label: null,
    symbol: "BTC",
    quantity: "0.5",
    avg_cost_tl: null,
    price_source: "auto",
    manual_unit_price_tl: null,
    linked_source: null,
    linked_id: null,
    unit_price_usd: "60000",
    unit_price_tl: "2000000",
    total_value_tl: "1000000",
    cost_basis_tl: null,
    gain_loss_tl: null,
    gain_loss_pct: null,
    notes: null,
    ...overrides,
  };
}

function summary(overrides: Record<string, unknown> = {}) {
  return {
    positions: [],
    total_value_tl: "0",
    unknown_symbols: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  confirmResult.value = true;
  listManualCrypto.mockResolvedValue(summary());
});

// ─── Render + yukleme ─────────────────────────────────────────────────────
describe("ManualCryptoPage — yukleme ve liste", () => {
  it("ilk render: banner + form + bos liste mesaji gosterilir", async () => {
    render(<ManualCryptoPage />);
    await waitFor(() =>
      expect(listManualCrypto).toHaveBeenCalledTimes(1),
    );
    expect(
      await screen.findByText("empty.noManualCrypto"),
    ).toBeInTheDocument();
    expect(screen.getByText("content.manualCrypto.bannerTitle")).toBeInTheDocument();
    expect(screen.getByText("content.manualCrypto.newPositionTitle")).toBeInTheDocument();
    // Bilinmeyen sembol uyarisi yok.
    expect(
      screen.queryByText("content.manualCrypto.unknownSymbolTitle"),
    ).not.toBeInTheDocument();
  });

  it("pozisyonlar tablo olarak render edilir (auto/manual/linked rozetleri + kar/zarar)", async () => {
    listManualCrypto.mockResolvedValue(
      summary({
        total_value_tl: "1500000",
        positions: [
          pos({ id: 1, symbol: "BTC", price_source: "auto", label: "ana cuzdan" }),
          pos({
            id: 2,
            symbol: "ETH",
            exchange: "icrypex",
            price_source: "manual",
            unit_price_tl: "100000",
            gain_loss_tl: "5000",
            gain_loss_pct: 12.5,
            notes: "not metni",
          }),
          pos({
            id: 3,
            symbol: "USDT",
            exchange: "other",
            price_source: "linked",
            linked_source: "coingecko",
            linked_id: "tether",
            gain_loss_tl: "-200",
            gain_loss_pct: -3.4,
            unit_price_tl: "0",
          }),
        ],
      }),
    );
    render(<ManualCryptoPage />);

    expect(await screen.findByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("ETH")).toBeInTheDocument();
    expect(screen.getByText("USDT")).toBeInTheDocument();
    // manual rozeti label kullanir.
    expect(screen.getByText("content.manualCrypto.sourceLabelManual")).toBeInTheDocument();
    // linked rozeti → "→ CoinGecko:tether"
    expect(screen.getByText("→ CoinGecko:tether")).toBeInTheDocument();
    // label + notes gosterilir.
    expect(screen.getByText("ana cuzdan")).toBeInTheDocument();
    expect(screen.getByText("not metni")).toBeInTheDocument();
    // unit_price_tl=0 olan USDT icin "—" (amber) gosterilir.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("bilinmeyen semboller uyarisi gosterilir", async () => {
    listManualCrypto.mockResolvedValue(
      summary({ unknown_symbols: ["FOO", "BAR"] }),
    );
    render(<ManualCryptoPage />);
    expect(
      await screen.findByText("content.manualCrypto.unknownSymbolTitle"),
    ).toBeInTheDocument();
    expect(screen.getByText("FOO, BAR")).toBeInTheDocument();
  });

  it("401 hatasi → /login'e yonlendirir", async () => {
    listManualCrypto.mockRejectedValue(new Error("Request failed 401"));
    render(<ManualCryptoPage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("401 disi hata → hata mesaji gosterilir, yonlendirme yok", async () => {
    listManualCrypto.mockRejectedValue(new Error("sunucu hatasi 500"));
    render(<ManualCryptoPage />);
    expect(await screen.findByText("sunucu hatasi 500")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("Error olmayan hata → loadFailed fallback", async () => {
    listManualCrypto.mockRejectedValue("string hata");
    render(<ManualCryptoPage />);
    expect(
      await screen.findByText("content.manualCrypto.loadFailed"),
    ).toBeInTheDocument();
  });
});

// ─── Form: zorunlu alan validasyonu + auto mod ───────────────────────────
describe("ManualCryptoPage — kayit ekleme (auto mod)", () => {
  it("zorunlu alanlar bos → createManualCrypto cagrilmaz, requiredFields hatasi", async () => {
    const user = userEvent.setup();
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    await user.click(screen.getByRole("button", { name: "form.add" }));
    expect(createManualCrypto).not.toHaveBeenCalled();
    expect(
      await screen.findByText("content.manualCrypto.requiredFields"),
    ).toBeInTheDocument();
  });

  it("gecerli auto kayit → createManualCrypto cagrilir + liste yenilenir + form temizlenir", async () => {
    const user = userEvent.setup();
    createManualCrypto.mockResolvedValue({ id: 9 });
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.symbolPlaceholder"),
      "btc",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.quantityPlaceholder"),
      "1.5",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.avgCostPlaceholder"),
      "100",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.labelPlaceholder"),
      "etiket",
    );
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() => expect(createManualCrypto).toHaveBeenCalledTimes(1));
    expect(createManualCrypto).toHaveBeenCalledWith(
      expect.objectContaining({
        exchange: "binancetr",
        symbol: "BTC", // uppercase
        quantity: 1.5,
        avg_cost_tl: 100,
        label: "etiket",
        price_source: "auto",
        manual_unit_price_tl: null,
        linked_source: null,
        linked_id: null,
      }),
    );
    // refresh ikinci kez cagrilir (ilk yukleme + submit sonrasi).
    await waitFor(() => expect(listManualCrypto).toHaveBeenCalledTimes(2));
    // Form temizlendi.
    expect(
      (screen.getByPlaceholderText(
        "content.manualCrypto.symbolPlaceholder",
      ) as HTMLInputElement).value,
    ).toBe("");
  });

  it("create hatasi → saveFailed/hata mesaji gosterilir", async () => {
    const user = userEvent.setup();
    createManualCrypto.mockRejectedValue(new Error("kayit basarisiz"));
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.symbolPlaceholder"),
      "eth",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.quantityPlaceholder"),
      "2",
    );
    await user.click(screen.getByRole("button", { name: "form.add" }));

    expect(await screen.findByText("kayit basarisiz")).toBeInTheDocument();
  });

  it("exchange secimi degistirilebilir (other)", async () => {
    const user = userEvent.setup();
    createManualCrypto.mockResolvedValue({ id: 1 });
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    const select = screen.getAllByRole("combobox")[0] as HTMLSelectElement;
    await user.selectOptions(select, "other");
    expect(select.value).toBe("other");
  });
});

// ─── Form: manual mod ─────────────────────────────────────────────────────
describe("ManualCryptoPage — manual fiyat modu", () => {
  async function selectManual(user: ReturnType<typeof userEvent.setup>) {
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");
    await user.click(screen.getByText("content.manualCrypto.sourceManual"));
  }

  it("manual secilince birim fiyat input'u gorunur", async () => {
    const user = userEvent.setup();
    await selectManual(user);
    expect(
      screen.getByPlaceholderText("content.manualCrypto.unitPriceTlPlaceholder"),
    ).toBeInTheDocument();
  });

  it("manual modda fiyat bos/0 → manualPriceRequired hatasi, create yok", async () => {
    const user = userEvent.setup();
    await selectManual(user);

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.symbolPlaceholder"),
      "sol",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.quantityPlaceholder"),
      "3",
    );
    // Fiyat 0 gir → <= 0 branch.
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.unitPriceTlPlaceholder"),
      "0",
    );
    await user.click(screen.getByRole("button", { name: "form.add" }));

    expect(
      await screen.findByText("content.manualCrypto.manualPriceRequired"),
    ).toBeInTheDocument();
    expect(createManualCrypto).not.toHaveBeenCalled();
  });

  it("manual modda gecerli fiyat → manual_unit_price_tl ile create", async () => {
    const user = userEvent.setup();
    createManualCrypto.mockResolvedValue({ id: 1 });
    await selectManual(user);

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.symbolPlaceholder"),
      "sol",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.quantityPlaceholder"),
      "3",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.unitPriceTlPlaceholder"),
      "150.5",
    );
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() =>
      expect(createManualCrypto).toHaveBeenCalledWith(
        expect.objectContaining({
          price_source: "manual",
          manual_unit_price_tl: 150.5,
        }),
      ),
    );
  });
});

// ─── Form: linked mod + asset catalog autocomplete ───────────────────────
describe("ManualCryptoPage — linked mod + autocomplete", () => {
  const CATALOG = [
    { source: "commodity", id: "XAG", symbol: "XAG", name: "Gumus" },
    { source: "binance", id: "ETH", symbol: "ETH", name: "Ethereum" },
    { source: "coingecko", id: "tether-gold", symbol: "XAUT", name: "Tether Gold" },
    { source: "tefas", id: "AFA", symbol: "AFA", name: "Ak Portfoy" },
  ];

  async function selectLinked(user: ReturnType<typeof userEvent.setup>) {
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");
    await user.click(screen.getByText("content.manualCrypto.sourceLinked"));
  }

  it("linked secilince arama kutusu gorunur + debounced arama yapilir", async () => {
    const user = userEvent.setup();
    searchAssetCatalog.mockResolvedValue(CATALOG);
    await selectLinked(user);

    const searchInput = screen.getByPlaceholderText(
      "content.manualCrypto.linkedSearchPlaceholder",
    );
    await user.type(searchInput, "eth");

    // debounce (250ms) sonrasi arama + sonuc render.
    await waitFor(() => expect(searchAssetCatalog).toHaveBeenCalled());
    expect(await screen.findByText("Ethereum")).toBeInTheDocument();
    // 4 kaynak rozeti de gorunur.
    expect(screen.getByText("Tether Gold")).toBeInTheDocument();
    expect(screen.getByText("Ak Portfoy")).toBeInTheDocument();
  });

  it("arama hatasi yutulur → dropdown sonucu cikmaz (catch → setLinkedResults([]))", async () => {
    const user = userEvent.setup();
    searchAssetCatalog.mockRejectedValue(new Error("arama hatasi"));
    await selectLinked(user);

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.linkedSearchPlaceholder"),
      "zzz",
    );
    await waitFor(() => expect(searchAssetCatalog).toHaveBeenCalled());
    // Hata yutuldugu icin sonuc render edilmez (uygulama cokmedi).
    expect(screen.queryByText("Ethereum")).not.toBeInTheDocument();
  });

  it("arama suruyorken (pending) searching gostergesi gorunur", async () => {
    const user = userEvent.setup();
    // Hic resolve etmeyen promise → searching=true kalir → searching dalı render.
    searchAssetCatalog.mockReturnValue(new Promise(() => {}));
    await selectLinked(user);

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.linkedSearchPlaceholder"),
      "btc",
    );
    expect(
      await screen.findByText("content.manualCrypto.searching"),
    ).toBeInTheDocument();
  });

  it("dolu sonuctan sonra bos arama → dropdown kapanir (sonuc kaybolur)", async () => {
    const user = userEvent.setup();
    // 1. arama CATALOG → dropdown acilir; 2. arama [] → searching biter +
    // linkedResults bos olunca dropdown container'i (searching||length>0) kapanir.
    searchAssetCatalog
      .mockResolvedValueOnce(CATALOG)
      .mockResolvedValue([]);
    await selectLinked(user);

    const input = screen.getByPlaceholderText(
      "content.manualCrypto.linkedSearchPlaceholder",
    );
    await user.type(input, "e");
    await screen.findByText("Ethereum");
    expect(searchAssetCatalog).toHaveBeenCalledTimes(1);

    await user.type(input, "x");
    await waitFor(() =>
      expect(searchAssetCatalog).toHaveBeenCalledTimes(2),
    );
    // Bos sonuc gelince eski sonuc kaybolur.
    await waitFor(() =>
      expect(screen.queryByText("Ethereum")).not.toBeInTheDocument(),
    );
  });

  it("linked secimi yapilmadan submit → linkedRequired hatasi", async () => {
    const user = userEvent.setup();
    searchAssetCatalog.mockResolvedValue([]);
    await selectLinked(user);

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.symbolPlaceholder"),
      "xag",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.quantityPlaceholder"),
      "10",
    );
    await user.click(screen.getByRole("button", { name: "form.add" }));

    expect(
      await screen.findByText("content.manualCrypto.linkedRequired"),
    ).toBeInTheDocument();
    expect(createManualCrypto).not.toHaveBeenCalled();
  });

  it("sonuctan secim → secili kutu + change ile geri al + gecerli create", async () => {
    const user = userEvent.setup();
    searchAssetCatalog.mockResolvedValue(CATALOG);
    createManualCrypto.mockResolvedValue({ id: 1 });
    await selectLinked(user);

    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.linkedSearchPlaceholder"),
      "xag",
    );
    const result = await screen.findByText("Gumus");
    await user.click(result);

    // Secili kutu: "✓ <commodity label>: XAG".
    expect(screen.getByText(/XAG/)).toBeInTheDocument();
    // change butonu secimi geri alir.
    await user.click(screen.getByText("content.manualCrypto.change"));
    expect(
      screen.getByPlaceholderText("content.manualCrypto.linkedSearchPlaceholder"),
    ).toBeInTheDocument();

    // Tekrar sec, sembol/miktar gir, kaydet.
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.linkedSearchPlaceholder"),
      "eth",
    );
    await user.click(await screen.findByText("Ethereum"));
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.symbolPlaceholder"),
      "eth",
    );
    await user.type(
      screen.getByPlaceholderText("content.manualCrypto.quantityPlaceholder"),
      "2",
    );
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() =>
      expect(createManualCrypto).toHaveBeenCalledWith(
        expect.objectContaining({
          price_source: "linked",
          linked_source: "binance",
          linked_id: "ETH",
        }),
      ),
    );
  });
});

// ─── Silme ────────────────────────────────────────────────────────────────
describe("ManualCryptoPage — silme", () => {
  beforeEach(() => {
    listManualCrypto.mockResolvedValue(
      summary({ total_value_tl: "1000000", positions: [pos({ id: 7, symbol: "BTC" })] }),
    );
  });

  it("onaylanirsa deleteManualCrypto cagrilir + liste yenilenir", async () => {
    const user = userEvent.setup();
    confirmResult.value = true;
    deleteManualCrypto.mockResolvedValue(undefined);
    render(<ManualCryptoPage />);
    await screen.findByText("BTC");

    await user.click(
      screen.getByRole("button", {
        name: "content.manualCrypto.deleteAria",
      }),
    );
    await waitFor(() => expect(deleteManualCrypto).toHaveBeenCalledWith(7));
    await waitFor(() => expect(listManualCrypto).toHaveBeenCalledTimes(2));
  });

  it("onaylanmazsa deleteManualCrypto cagrilmaz", async () => {
    const user = userEvent.setup();
    confirmResult.value = false;
    render(<ManualCryptoPage />);
    await screen.findByText("BTC");

    await user.click(
      screen.getByRole("button", { name: "content.manualCrypto.deleteAria" }),
    );
    await waitFor(() => expect(listManualCrypto).toHaveBeenCalledTimes(1));
    expect(deleteManualCrypto).not.toHaveBeenCalled();
  });

  it("delete hatasi → deleteFailed/hata mesaji gosterilir", async () => {
    const user = userEvent.setup();
    confirmResult.value = true;
    deleteManualCrypto.mockRejectedValue(new Error("silme hatasi"));
    render(<ManualCryptoPage />);
    await screen.findByText("BTC");

    await user.click(
      screen.getByRole("button", { name: "content.manualCrypto.deleteAria" }),
    );
    expect(await screen.findByText("silme hatasi")).toBeInTheDocument();
  });
});

// ─── Export / Import ──────────────────────────────────────────────────────
describe("ManualCryptoPage — export / import", () => {
  it("export butonu → exportManualCrypto cagrilir", async () => {
    const user = userEvent.setup();
    exportManualCrypto.mockResolvedValue(undefined);
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    await waitFor(() => expect(exportManualCrypto).toHaveBeenCalledTimes(1));
  });

  it("export hatasi → exportFailed mesaji", async () => {
    const user = userEvent.setup();
    exportManualCrypto.mockRejectedValue(new Error("export hatasi"));
    render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    expect(await screen.findByText("export hatasi")).toBeInTheDocument();
  });

  it("import basarili (hatasiz) → liste yenilenir", async () => {
    importManualCrypto.mockResolvedValue({ imported: 3, errors: [] });
    const { container } = render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["x"], "veri.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const user = userEvent.setup();
    await user.upload(fileInput, file);

    await waitFor(() => expect(importManualCrypto).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(listManualCrypto).toHaveBeenCalledTimes(2));
  });

  it("import kismi hatali → importResult dali calisir + liste yenilenir", async () => {
    // NOT: handler once setError(importResult) cagirir, sonra await refresh()
    // refresh basinda setError("") ile temizler. Yani mesaj DOM'da kalici degil;
    // burada importResult dalinin (errors.length>0) calistigini + refresh'i
    // dogruluyoruz (branch coverage).
    importManualCrypto.mockResolvedValue({
      imported: 1,
      errors: ["satir 2 hata", "satir 5 hata"],
    });
    const { container } = render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const user = userEvent.setup();
    await user.upload(
      fileInput,
      new File(["x"], "veri.xlsx", { type: "application/octet-stream" }),
    );

    await waitFor(() => expect(importManualCrypto).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(listManualCrypto).toHaveBeenCalledTimes(2));
  });

  it("import hatasi → importFailed/hata mesaji", async () => {
    importManualCrypto.mockRejectedValue(new Error("import patladi"));
    const { container } = render(<ManualCryptoPage />);
    await screen.findByText("empty.noManualCrypto");

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const user = userEvent.setup();
    await user.upload(
      fileInput,
      new File(["x"], "veri.xlsx", { type: "application/octet-stream" }),
    );

    expect(await screen.findByText("import patladi")).toBeInTheDocument();
  });
});
