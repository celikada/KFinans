import { describe, expect, it, beforeEach, vi } from "vitest";

// v8 coverage instrumentasyonu altinda etkilesimler yavaslayabilir; timeout yukselt.
vi.setConfig({ testTimeout: 30000 });
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────
const replaceMock = vi.fn();
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock, prefetch: vi.fn() }),
}));

vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => ({ t: (k: string) => k, locale: "tr", setLocale: vi.fn() }),
}));

// TLValue → deterministik basit gosterim (USD rate fetch'i tetiklemesin).
vi.mock("@/app/_components/TLValue", () => ({
  TLValue: ({ tl, className }: { tl: number; className?: string }) => (
    <span data-testid="tl-value" className={className}>{String(tl)}</span>
  ),
}));

const getBesHoldings = vi.fn();
const saveBesHoldings = vi.fn();
const exportBesHoldings = vi.fn();
const importBesHoldings = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getBesHoldings: (...a: unknown[]) => getBesHoldings(...a),
    saveBesHoldings: (...a: unknown[]) => saveBesHoldings(...a),
    exportBesHoldings: (...a: unknown[]) => exportBesHoldings(...a),
    importBesHoldings: (...a: unknown[]) => importBesHoldings(...a),
  },
}));

import BesPage from "@/app/dashboard/bes/page";

const SAMPLE = [
  {
    plan_name: "Allianz Plan",
    contract_number: "C-100",
    paid_principal: 1000,
    paid_returns: 200,
    govt_contribution: 250,
    govt_returns: 50,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  getBesHoldings.mockResolvedValue([]);
  saveBesHoldings.mockResolvedValue([]);
  exportBesHoldings.mockResolvedValue(undefined);
  importBesHoldings.mockResolvedValue([]);
});

describe("BesPage — yukleme + ilk render", () => {
  it("yuklenirken loading metni, sonra bos satir formu gosterir", async () => {
    let resolve!: (v: unknown[]) => void;
    getBesHoldings.mockImplementation(() => new Promise((r) => { resolve = r; }));
    render(<BesPage />);

    expect(screen.getByText("common.loading")).toBeInTheDocument();
    resolve([]);

    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    // Bos satir → plan adi input gorunur.
    expect(screen.getByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    expect(getBesHoldings).toHaveBeenCalledTimes(1);
  });

  it("mevcut holding'ler doldurulur (degerler input'lara yansir)", async () => {
    getBesHoldings.mockResolvedValue(SAMPLE);
    render(<BesPage />);

    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    const planInput = screen.getByPlaceholderText("content.bes.planNamePlaceholder") as HTMLInputElement;
    expect(planInput.value).toBe("Allianz Plan");
    // Toplam (1000+200+250+50 = 1500) grand total bloku gorunur.
    expect(screen.getByText("content.bes.totalBesValue")).toBeInTheDocument();
    expect(screen.getByTestId("tl-value")).toHaveTextContent("1500");
  });

  it("getBesHoldings 401 → login'e yonlendirir", async () => {
    getBesHoldings.mockRejectedValue(new Error("Request failed 401"));
    render(<BesPage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("getBesHoldings 401 disi hata → yonlendirme yok, form yine acilir", async () => {
    getBesHoldings.mockRejectedValue(new Error("500 server error"));
    render(<BesPage />);
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    expect(replaceMock).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
  });

  it("geri butonu /dashboard'a push eder", async () => {
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "common.back" }));
    expect(pushMock).toHaveBeenCalledWith("/dashboard");
  });
});

describe("BesPage — satir CRUD + toplam hesabi", () => {
  it("plan ekle → ikinci satir gelir, sil → tekrar tek satir", async () => {
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    // Tek satirda sil butonu yok (holdings.length === 1).
    expect(screen.queryByRole("button", { name: "content.bes.removeRowAria" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "content.bes.addPlan" }));
    expect(screen.getAllByPlaceholderText("content.bes.planNamePlaceholder")).toHaveLength(2);

    // Artik sil butonu gorunur.
    const removeBtns = screen.getAllByRole("button", { name: "content.bes.removeRowAria" });
    expect(removeBtns).toHaveLength(2);
    await user.click(removeBtns[0]);
    expect(screen.getAllByPlaceholderText("content.bes.planNamePlaceholder")).toHaveLength(1);
  });

  it("alan girisi satir toplamini ve grand total'i gunceller", async () => {
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("content.bes.planNamePlaceholder"), "Test Plan");
    const numInputs = screen.getAllByPlaceholderText(/0,00/);
    // 4 sayisal alan (paid_principal, paid_returns, govt_contribution, govt_returns)
    expect(numInputs).toHaveLength(4);
    fireEvent.change(numInputs[0], { target: { value: "500" } });
    fireEvent.change(numInputs[1], { target: { value: "100" } });

    // Grand total > 0 → TLValue bloku gorunur (500+100 = 600).
    await waitFor(() => expect(screen.getByTestId("tl-value")).toHaveTextContent("600"));
  });
});

describe("BesPage — kaydetme akisi", () => {
  it("gecerli kayit → saveBesHoldings cagrilir + saved label kisa sure gorunur", async () => {
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("content.bes.planNamePlaceholder"), "Plan A");
    const numInputs = screen.getAllByPlaceholderText(/0,00/);
    fireEvent.change(numInputs[0], { target: { value: "1000" } });

    await user.click(screen.getByRole("button", { name: "common.save" }));

    await waitFor(() => expect(saveBesHoldings).toHaveBeenCalledTimes(1));
    // toDTO filtresi: plan_name + total > 0 olan satir gonderilir.
    const payload = saveBesHoldings.mock.calls[0][0];
    expect(payload).toHaveLength(1);
    expect(payload[0]).toMatchObject({ plan_name: "Plan A", paid_principal: 1000 });
    // Basari → saved label.
    expect(await screen.findByText("content.bes.saved")).toBeInTheDocument();
  });

  it("tutar 'A+B+C' girilince toplami kaydedilir (100+150+200 → 450)", async () => {
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("content.bes.planNamePlaceholder"), "Toplam Plan");
    const numInputs = screen.getAllByPlaceholderText(/0,00/);
    fireEvent.change(numInputs[0], { target: { value: "100+150+200" } });

    // Canli toplam ipucu gorunur.
    await waitFor(() => expect(screen.getByText(/= 450/)).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "common.save" }));
    await waitFor(() => expect(saveBesHoldings).toHaveBeenCalledTimes(1));
    const payload = saveBesHoldings.mock.calls[0][0];
    expect(payload[0]).toMatchObject({ plan_name: "Toplam Plan", paid_principal: 450 });
  });

  it("save 401 → login'e yonlendirir, hata gosterilmez", async () => {
    saveBesHoldings.mockRejectedValue(new Error("got 401 here"));
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("content.bes.planNamePlaceholder"), "Plan B");
    fireEvent.change(screen.getAllByPlaceholderText(/0,00/)[0], { target: { value: "5" } });
    await user.click(screen.getByRole("button", { name: "common.save" }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("save 401 disi hata → hata mesaji gosterilir", async () => {
    saveBesHoldings.mockRejectedValue(new Error("kaydetme reddedildi"));
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("content.bes.planNamePlaceholder"), "Plan C");
    fireEvent.change(screen.getAllByPlaceholderText(/0,00/)[0], { target: { value: "5" } });
    await user.click(screen.getByRole("button", { name: "common.save" }));

    expect(await screen.findByText("kaydetme reddedildi")).toBeInTheDocument();
  });

  it("save Error olmayan deger firlatirsa fallback ceviri mesaji", async () => {
    saveBesHoldings.mockRejectedValue("string hata");
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    fireEvent.change(screen.getAllByPlaceholderText(/0,00/)[0], { target: { value: "5" } });
    await user.type(screen.getByPlaceholderText("content.bes.planNamePlaceholder"), "Plan D");
    await user.click(screen.getByRole("button", { name: "common.save" }));

    expect(await screen.findByText("content.bes.saveFailed")).toBeInTheDocument();
  });
});

describe("BesPage — Excel export/import", () => {
  it("export → exportBesHoldings cagrilir", async () => {
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    await waitFor(() => expect(exportBesHoldings).toHaveBeenCalledTimes(1));
  });

  it("export hata → hata mesaji gosterilir", async () => {
    exportBesHoldings.mockRejectedValue(new Error("export patladi"));
    render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "form.excelDownload" }));
    expect(await screen.findByText("export patladi")).toBeInTheDocument();
  });

  it("import → importBesHoldings cagrilir + holdings doldurulur", async () => {
    importBesHoldings.mockResolvedValue(SAMPLE);
    const { container } = render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "bes.xlsx", { type: "application/vnd.ms-excel" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(importBesHoldings).toHaveBeenCalledTimes(1));
    const planInput = await screen.findByDisplayValue("Allianz Plan");
    expect(planInput).toBeInTheDocument();
  });

  it("import dosya secilmezse hicbir sey yapilmaz", async () => {
    const { container } = render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [] } });
    expect(importBesHoldings).not.toHaveBeenCalled();
  });

  it("import 401 → login'e yonlendirir", async () => {
    importBesHoldings.mockRejectedValue(new Error("401 unauthorized"));
    const { container } = render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "bes.xlsx");
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("import 401 disi hata → hata mesaji", async () => {
    importBesHoldings.mockRejectedValue(new Error("gecersiz dosya"));
    const { container } = render(<BesPage />);
    expect(await screen.findByPlaceholderText("content.bes.planNamePlaceholder")).toBeInTheDocument();

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "bes.xlsx");
    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(await screen.findByText("gecersiz dosya")).toBeInTheDocument();
  });
});
