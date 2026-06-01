import { describe, expect, it, beforeEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });
import { render, screen, waitFor, within } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────
// STABIL router — refresh() useCallback([router, t]) deps tekrar tetiklenmesin.
const replaceMock = vi.fn();
const routerStub = { push: vi.fn(), replace: replaceMock, prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

// t STABIL referans — useCallback([router, t]) bagimliligi tekrar tetiklenmesin.
vi.mock("@/app/_i18n/I18nProvider", () => {
  const t = (k: string) => k;
  const setLocale = vi.fn();
  return {
    useTranslation: () => ({ t, locale: "tr", setLocale }),
  };
});

vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

vi.mock("@/app/_components/TLValue", () => ({
  TLValue: ({ tl, className }: { tl: number | string; className?: string }) => (
    <span className={className}>{String(tl)}</span>
  ),
}));

// lib/api — sadece `api` objesini stub'la; const'lari (BIGA_*, COIN_*) gercek
// modulden koru (CommodityForm bunlara baglidir).
const getCommodities = vi.fn();
const createCommodity = vi.fn();
const deleteCommodity = vi.fn();
const exportCommodities = vi.fn();
const importCommodities = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      getCommodities: (...a: unknown[]) => getCommodities(...a),
      createCommodity: (...a: unknown[]) => createCommodity(...a),
      deleteCommodity: (...a: unknown[]) => deleteCommodity(...a),
      exportCommodities: (...a: unknown[]) => exportCommodities(...a),
      importCommodities: (...a: unknown[]) => importCommodities(...a),
    },
  };
});

import CommoditiesPage from "@/app/dashboard/commodities/page";

// ─── Fixtures ────────────────────────────────────────────────────────────────
function commPos(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    unit_type: "coin",
    metal: "gold",
    biga_code: null,
    coin_type: "tam",
    quantity: "2",
    notes: null,
    gram_equivalent: "14.04",
    total_value_tl: "50000",
    gold_price_tl: "2500",
    silver_price_tl: "30",
    ...overrides,
  };
}

function commSummary(overrides: Record<string, unknown> = {}) {
  return {
    positions: [],
    total_gold_gram: "0",
    total_silver_gram: "0",
    total_value_tl: "0",
    gold_price_tl: "2500",
    silver_price_tl: "30",
    gold_price_available: true,
    silver_price_available: true,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getCommodities.mockResolvedValue(commSummary());
});

// ─── Yukleme + ozet ─────────────────────────────────────────────────────
describe("CommoditiesPage — yukleme ve ozet", () => {
  it("ilk render: ozet + form + bos liste mesaji", async () => {
    render(<CommoditiesPage />);
    await waitFor(() => expect(getCommodities).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText("empty.noCommodity"),
    ).toBeInTheDocument();
    expect(screen.getByText("content.commodities.totalValue")).toBeInTheDocument();
    // CommodityForm render edildi.
    expect(screen.getByText("form.addAsset")).toBeInTheDocument();
  });

  it("altin + gumus pozisyonlari → altin/gumus toplamlari + anlik kurlar", async () => {
    getCommodities.mockResolvedValue(
      commSummary({
        total_value_tl: "80000",
        total_gold_gram: "14.04",
        total_silver_gram: "100",
        positions: [
          commPos({ id: 1, metal: "gold", total_value_tl: "50000" }),
          commPos({
            id: 2,
            unit_type: "gram",
            metal: "silver",
            coin_type: null,
            quantity: "100",
            gram_equivalent: "100",
            total_value_tl: "30000",
            notes: "gumus notu",
          }),
        ],
      }),
    );
    render(<CommoditiesPage />);

    // Altin + Gumus baslik kartlari gorunur.
    expect(await screen.findByText("content.commodities.gold")).toBeInTheDocument();
    expect(screen.getByText("content.commodities.silver")).toBeInTheDocument();
    // Anlik kur satiri (goldPrice !== null) gorunur.
    expect(screen.getByText("content.commodities.goldRate")).toBeInTheDocument();
    expect(screen.getByText("content.commodities.silverRate")).toBeInTheDocument();
    // Liste satirlari (CommodityList) render edildi.
    expect(screen.getByText("gumus notu")).toBeInTheDocument();
  });

  it("401 hatasi → /login'e yonlendirir", async () => {
    getCommodities.mockRejectedValue(new Error("Request failed 401"));
    render(<CommoditiesPage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("401 disi hata → hata mesaji, yonlendirme yok", async () => {
    getCommodities.mockRejectedValue(new Error("sunucu hatasi 500"));
    render(<CommoditiesPage />);
    expect(await screen.findByText("sunucu hatasi 500")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("Error olmayan hata → loadFailed fallback", async () => {
    getCommodities.mockRejectedValue("string hata");
    render(<CommoditiesPage />);
    expect(
      await screen.findByText("content.commodities.loadFailed"),
    ).toBeInTheDocument();
  });
});

// ─── Fiyat fallback (uyari banner'lari) ──────────────────────────────────
describe("CommoditiesPage — fiyat fallback uyarilari", () => {
  it("altin fiyati cekilemiyor → goldUnavailable uyarisi", async () => {
    getCommodities.mockResolvedValue(
      commSummary({
        gold_price_available: false,
        positions: [commPos({ id: 1, metal: "gold" })],
      }),
    );
    render(<CommoditiesPage />);
    expect(
      await screen.findByText("content.commodities.goldUnavailable"),
    ).toBeInTheDocument();
  });

  it("gumus fiyati cekilemiyor (gumus pozisyonu varken) → silverUnavailable", async () => {
    getCommodities.mockResolvedValue(
      commSummary({
        silver_price_available: false,
        positions: [
          commPos({ id: 2, unit_type: "gram", metal: "silver", coin_type: null }),
        ],
      }),
    );
    render(<CommoditiesPage />);
    expect(
      await screen.findByText("content.commodities.silverUnavailable"),
    ).toBeInTheDocument();
  });

  it("hem altin hem gumus cekilemiyor → bothUnavailable", async () => {
    getCommodities.mockResolvedValue(
      commSummary({
        gold_price_available: false,
        silver_price_available: false,
        positions: [
          commPos({ id: 1, metal: "gold" }),
          commPos({ id: 2, unit_type: "gram", metal: "silver", coin_type: null }),
        ],
      }),
    );
    render(<CommoditiesPage />);
    expect(
      await screen.findByText("content.commodities.bothUnavailable"),
    ).toBeInTheDocument();
  });

  it("tum fiyatlar mevcut → uyari banner'i yok", async () => {
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();
    expect(
      screen.queryByText("content.commodities.goldUnavailable"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("content.commodities.bothUnavailable"),
    ).not.toBeInTheDocument();
  });
});

// ─── Export / Import ──────────────────────────────────────────────────────
describe("CommoditiesPage — export / import", () => {
  it("export → exportCommodities cagrilir", async () => {
    const user = userEvent.setup();
    exportCommodities.mockResolvedValue(undefined);
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    await waitFor(() => expect(exportCommodities).toHaveBeenCalledTimes(1));
  });

  it("export hatasi → exportFailed mesaji", async () => {
    const user = userEvent.setup();
    exportCommodities.mockRejectedValue(new Error("export hatasi"));
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    expect(await screen.findByText("export hatasi")).toBeInTheDocument();
  });

  it("import basarili → liste yenilenir", async () => {
    importCommodities.mockResolvedValue([]);
    const { container } = render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const user = userEvent.setup();
    await user.upload(
      fileInput,
      new File(["x"], "metal.xlsx", { type: "application/octet-stream" }),
    );

    await waitFor(() => expect(importCommodities).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getCommodities).toHaveBeenCalledTimes(2));
  });

  it("import hatasi → importFailed mesaji", async () => {
    importCommodities.mockRejectedValue(new Error("import patladi"));
    const { container } = render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const user = userEvent.setup();
    await user.upload(
      fileInput,
      new File(["x"], "metal.xlsx", { type: "application/octet-stream" }),
    );

    expect(await screen.findByText("import patladi")).toBeInTheDocument();
  });
});

// ─── CommodityForm (alt component) ────────────────────────────────────────
describe("CommodityForm — varlik ekleme", () => {
  it("coin modunda gecerli miktar → createCommodity (coin_type) + form temizlenir", async () => {
    const user = userEvent.setup();
    createCommodity.mockResolvedValue({ id: 1 });
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    // Miktar input'u (number) — placeholder coin modunda table.count.
    const qty = screen.getByPlaceholderText("table.count") as HTMLInputElement;
    await user.type(qty, "3");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() =>
      expect(createCommodity).toHaveBeenCalledWith(
        expect.objectContaining({
          unit_type: "coin",
          coin_type: "tam",
          quantity: 3,
        }),
      ),
    );
    await waitFor(() => expect(qty.value).toBe(""));
  });

  it("miktar 0/gecersiz → createCommodity cagrilmaz, amountInvalidQty hatasi", async () => {
    const user = userEvent.setup();
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    // Hic miktar girmeden ekle.
    await user.click(screen.getByRole("button", { name: "form.add" }));
    expect(createCommodity).not.toHaveBeenCalled();
    expect(
      await screen.findByText("form.amountInvalidQty"),
    ).toBeInTheDocument();
  });

  it("gram moduna gecis → metal secimi + gram payload", async () => {
    const user = userEvent.setup();
    createCommodity.mockResolvedValue({ id: 1 });
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "form.gram" }));
    // Gram modunda metal select (gold/silver) gorunur.
    const metalSelect = screen.getByRole("combobox") as HTMLSelectElement;
    await user.selectOptions(metalSelect, "silver");

    const qty = screen.getByPlaceholderText("form.gram") as HTMLInputElement;
    await user.type(qty, "25.5");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() =>
      expect(createCommodity).toHaveBeenCalledWith(
        expect.objectContaining({
          unit_type: "gram",
          metal: "silver",
          quantity: 25.5,
        }),
      ),
    );
  });

  it("biga moduna gecis → metal degisimi biga kodunu gunceller + biga payload", async () => {
    const user = userEvent.setup();
    createCommodity.mockResolvedValue({ id: 1 });
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "form.biga" }));
    // Biga modunda 2 select: metal + kod.
    const selects = screen.getAllByRole("combobox");
    // Metal silver'a gecince biga kodu G01'e set olur.
    await user.selectOptions(selects[0], "silver");

    const qty = screen.getByPlaceholderText("table.count") as HTMLInputElement;
    await user.type(qty, "1");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() =>
      expect(createCommodity).toHaveBeenCalledWith(
        expect.objectContaining({
          unit_type: "biga",
          biga_code: "G01",
          quantity: 1,
        }),
      ),
    );
  });

  it("create hatasi → form hata mesaji (saveFailed/mesaj)", async () => {
    const user = userEvent.setup();
    createCommodity.mockRejectedValue(new Error("kayit hatasi"));
    render(<CommoditiesPage />);
    expect(await screen.findByText("empty.noCommodity")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("table.count"), "2");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    expect(await screen.findByText("kayit hatasi")).toBeInTheDocument();
  });
});

// ─── CommodityList silme ──────────────────────────────────────────────────
describe("CommodityList — silme", () => {
  beforeEach(() => {
    getCommodities.mockResolvedValue(
      commSummary({
        total_value_tl: "50000",
        positions: [commPos({ id: 42, coin_type: "ceyrek", notes: "not" })],
      }),
    );
  });

  it("silme butonu → deleteCommodity cagrilir + liste yenilenir", async () => {
    const user = userEvent.setup();
    deleteCommodity.mockResolvedValue(undefined);
    render(<CommoditiesPage />);
    // Coin etiketi (COIN_LABELS.ceyrek) render edilir.
    expect(await screen.findByText("not")).toBeInTheDocument();

    const delBtn = screen.getByRole("button", {
      name: "content.commodities.deleteAria",
    });
    await user.click(delBtn);

    await waitFor(() => expect(deleteCommodity).toHaveBeenCalledWith(42));
    await waitFor(() => expect(getCommodities).toHaveBeenCalledTimes(2));
  });
});
