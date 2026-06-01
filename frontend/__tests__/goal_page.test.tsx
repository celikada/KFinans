import { describe, expect, it, beforeEach, vi } from "vitest";

vi.setConfig({ testTimeout: 30000 });

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────

const getGoal = vi.fn();
const setGoal = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getGoal: (...a: unknown[]) => getGoal(...a),
    setGoal: (...a: unknown[]) => setGoal(...a),
  },
  GOAL_CURRENCY_SYMBOLS: { TRY: "₺", USD: "$", EUR: "€", GBP: "£" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

// STABIL referans: useTranslation her render'da yeni `t` dondururse, sayfanin
// useCallback([t]) + useEffect([load]) zinciri her render'da load()'u yeniden
// calistirir ve currency/inputVal state'ini EMPTY_GOAL'a ezer (sonsuz reset).
const i18nStub = {
  t: (key: string) => key,
  locale: "tr" as const,
  setLocale: vi.fn(),
};
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => i18nStub,
}));

// Import AFTER mocks
import GoalPage from "@/app/dashboard/goal/page";

// Bos hedef (kullanici henuz hedef girmemis).
const EMPTY_GOAL = {
  goal_amount: null,
  goal_currency: "USD" as const,
  rate_to_tl: null,
  monthly_tl: null,
  freedom_target_tl: null,
  portfolio_value: null,
  passive_income_tl: null,
  passive_income_foreign: null,
  progress_pct: null,
  months_covered: null,
};

// USD hedef + portfoy verisi dolu (yabanci para + ilerleme dallari).
const FULL_USD_GOAL = {
  goal_amount: "3000",
  goal_currency: "USD" as const,
  rate_to_tl: "40",
  monthly_tl: "120000",
  freedom_target_tl: "36000000",
  portfolio_value: "18000000",
  passive_income_tl: "60000",
  passive_income_foreign: "1500",
  progress_pct: 50,
  months_covered: 150,
};

beforeEach(() => {
  getGoal.mockReset();
  setGoal.mockReset();
  getGoal.mockResolvedValue(EMPTY_GOAL);
});

// ─── Yukleme + ilk render ───────────────────────────────────────────────────

describe("GoalPage — yukleme", () => {
  it("yuklenirken loading metni gosterir, sonra hedef formu gelir", async () => {
    let resolve!: (v: typeof EMPTY_GOAL) => void;
    getGoal.mockImplementation(() => new Promise((r) => (resolve = r)));

    render(<GoalPage />);
    expect(screen.getByText("common.loading")).toBeInTheDocument();

    resolve(EMPTY_GOAL);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();
    expect(getGoal).toHaveBeenCalledTimes(1);
  });

  it("getGoal hatasi → loadFailed hatasi gosterilir", async () => {
    getGoal.mockRejectedValue(new Error("503 unavailable"));
    render(<GoalPage />);
    expect(
      await screen.findByText("content.goal.loadFailed"),
    ).toBeInTheDocument();
  });

  it("mevcut hedef yuklenince input + para birimi doldurulur", async () => {
    getGoal.mockResolvedValue(FULL_USD_GOAL);
    render(<GoalPage />);

    const input = (await screen.findByPlaceholderText(
      "3000",
    )) as HTMLInputElement;
    expect(input.value).toBe("3000");
    // USD secili → USD butonu aktif renkte
    const usdBtn = screen.getByRole("button", { name: "$ USD" });
    expect(usdBtn.className).toContain("bg-violet-600");
  });
});

// ─── Para birimi secimi ──────────────────────────────────────────────────────

describe("GoalPage — para birimi secimi", () => {
  it("TRY secilince input placeholder + step degisir", async () => {
    const user = userEvent.setup();
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "₺ TRY" }));
    const input = (await screen.findByPlaceholderText("50000")) as HTMLInputElement;
    expect(input).toHaveAttribute("step", "1000");
  });

  it("yabanci para secilince step 100 olur", async () => {
    const user = userEvent.setup();
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "€ EUR" }));
    const input = (await screen.findByPlaceholderText("3000")) as HTMLInputElement;
    expect(input).toHaveAttribute("step", "100");
  });
});

// ─── Anlik ozet (girilen degere gore) ────────────────────────────────────────

describe("GoalPage — anlik ozet", () => {
  it("rate olmadan TRY girisinde sadece hedef tutar (multiplier) hesaplanir", async () => {
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "₺ TRY" }));
    fireEvent.change(screen.getByPlaceholderText("50000"), {
      target: { value: "50000" },
    });

    // freedomTarget metni gorunur (50000 * 300)
    expect(
      await screen.findByText("content.goal.freedomTarget", { exact: false }),
    ).toBeInTheDocument();
  });

  it("yabanci para + rate dolu → TL cevrim satiri gorunur", async () => {
    // rate dolu hedef yukle, sonra input zaten 3000 dolu.
    getGoal.mockResolvedValue(FULL_USD_GOAL);
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    // isForeign && rate dali → cevrim satirinda "× ... ₺ =" ifadesi gecer.
    expect(
      await screen.findByText(/×/, { exact: false }),
    ).toBeInTheDocument();
  });
});

// ─── Kaydetme akisi ──────────────────────────────────────────────────────────

describe("GoalPage — kaydetme", () => {
  it("gecersiz/sifir tutar → amountInvalid hatasi, setGoal cagrilmaz", async () => {
    const user = userEvent.setup();
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    // input bos → handleSave Number.parseFloat("") = NaN → invalid
    await user.click(screen.getByRole("button", { name: "common.save" }));

    expect(
      await screen.findByText("content.goal.amountInvalid"),
    ).toBeInTheDocument();
    expect(setGoal).not.toHaveBeenCalled();
  });

  it("gecerli tutar → setGoal cagrilir, 'saved' metni gosterilir", async () => {
    setGoal.mockResolvedValue(FULL_USD_GOAL);
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    const saveBtn = screen.getByRole("button", { name: "common.save" });
    fireEvent.change(screen.getByPlaceholderText("3000"), { target: { value: "3000" } });
    fireEvent.click(saveBtn);

    await waitFor(() => expect(setGoal).toHaveBeenCalledWith(3000, "USD"));
    expect(
      await screen.findByText("content.goal.saved"),
    ).toBeInTheDocument();
  });

  it("setGoal backend hatasi (Error) → mesaj gosterilir", async () => {
    setGoal.mockRejectedValue(new Error("kaydedilemedi"));
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    const saveBtn = screen.getByRole("button", { name: "common.save" });
    fireEvent.change(screen.getByPlaceholderText("3000"), { target: { value: "3000" } });
    fireEvent.click(saveBtn);

    expect(await screen.findByText("kaydedilemedi")).toBeInTheDocument();
  });

  it("setGoal hatasi (Error olmayan) → fallback saveFailed", async () => {
    setGoal.mockRejectedValue("string");
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    const saveBtn = screen.getByRole("button", { name: "common.save" });
    fireEvent.change(screen.getByPlaceholderText("3000"), { target: { value: "3000" } });
    fireEvent.click(saveBtn);

    expect(
      await screen.findByText("content.goal.saveFailed"),
    ).toBeInTheDocument();
  });

  it("kaydetme sirasinda buton saving metni gosterir", async () => {
    let resolve!: (v: typeof FULL_USD_GOAL) => void;
    setGoal.mockImplementation(() => new Promise((r) => (resolve = r)));
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();

    const saveBtn = screen.getByRole("button", { name: "common.save" });
    fireEvent.change(screen.getByPlaceholderText("3000"), { target: { value: "3000" } });
    fireEvent.click(saveBtn);

    expect(await screen.findByText("form.saving")).toBeInTheDocument();
    resolve(FULL_USD_GOAL);
    expect(await screen.findByText("content.goal.saved")).toBeInTheDocument();
  });
});

// ─── Ilerleme paneli ─────────────────────────────────────────────────────────

describe("GoalPage — ilerleme paneli", () => {
  it("portfoy dolu USD hedef → ilerleme + tum metrik kartlari render edilir", async () => {
    getGoal.mockResolvedValue(FULL_USD_GOAL);
    render(<GoalPage />);

    expect(
      await screen.findByText("content.goal.progressStatus"),
    ).toBeInTheDocument();
    // metrik kartlari
    expect(screen.getByText("content.goal.passiveIncomeTl")).toBeInTheDocument();
    expect(screen.getByText("content.goal.monthsCovered")).toBeInTheDocument();
    expect(
      screen.getByText("content.goal.remainingToTarget"),
    ).toBeInTheDocument();
    expect(screen.getByText("content.goal.passiveVsNeed")).toBeInTheDocument();
    // yabanci para pasif gelir karti (isForeign && passiveFgn dali)
    expect(
      screen.getByText("content.goal.passiveIncomeCurrency"),
    ).toBeInTheDocument();
    // currentPortfolio satiri (portfolio truthy dali)
    expect(
      screen.getByText("content.goal.currentPortfolio"),
    ).toBeInTheDocument();
  });

  it("hedef var ama portfoy yok → noPortfolioData mesaji", async () => {
    getGoal.mockResolvedValue({
      ...FULL_USD_GOAL,
      portfolio_value: null,
      passive_income_tl: null,
      passive_income_foreign: null,
      progress_pct: null,
      months_covered: null,
    });
    render(<GoalPage />);

    expect(
      await screen.findByText("content.goal.noPortfolioData"),
    ).toBeInTheDocument();
    // ilerleme baslik yine var, ama currentPortfolio satiri yok
    expect(
      screen.queryByText("content.goal.currentPortfolio"),
    ).not.toBeInTheDocument();
  });

  it("hedef hic yoksa (amount null) → ilerleme paneli render edilmez", async () => {
    getGoal.mockResolvedValue(EMPTY_GOAL);
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.monthlyNeedTitle")).toBeInTheDocument();
    expect(
      screen.queryByText("content.goal.progressStatus"),
    ).not.toBeInTheDocument();
  });

  it("TRY hedef → fgn kart yok, pasif TL >= aylik ise financiallyFree", async () => {
    getGoal.mockResolvedValue({
      goal_amount: "50000",
      goal_currency: "TRY",
      rate_to_tl: null,
      monthly_tl: "50000",
      freedom_target_tl: "15000000",
      portfolio_value: "20000000",
      passive_income_tl: "66666",
      passive_income_foreign: null,
      progress_pct: 133,
      months_covered: 400,
    });
    render(<GoalPage />);

    expect(await screen.findByText("content.goal.progressStatus")).toBeInTheDocument();
    // TRY → yabanci pasif gelir karti olmamali
    expect(
      screen.queryByText("content.goal.passiveIncomeCurrency"),
    ).not.toBeInTheDocument();
    // pct >= 100 → targetReached + financiallyFree
    expect(
      screen.getByText("content.goal.financiallyFree"),
    ).toBeInTheDocument();
  });
});

// ─── Formul bilgi kutusu ─────────────────────────────────────────────────────

describe("GoalPage — formul kutusu", () => {
  it("yabanci para + rate dolu → formulRate satiri gorunur", async () => {
    getGoal.mockResolvedValue(FULL_USD_GOAL);
    render(<GoalPage />);
    expect(
      await screen.findByText("content.goal.formulaRate"),
    ).toBeInTheDocument();
  });

  it("TRY hedef → formulRate satiri gorunmez", async () => {
    getGoal.mockResolvedValue({
      ...EMPTY_GOAL,
      goal_currency: "TRY",
      rate_to_tl: null,
    });
    render(<GoalPage />);
    expect(await screen.findByText("content.goal.formulaTitle")).toBeInTheDocument();
    expect(
      screen.queryByText("content.goal.formulaRate"),
    ).not.toBeInTheDocument();
  });
});
