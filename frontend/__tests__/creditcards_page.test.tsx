import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

// ─── Mocks ──────────────────────────────────────────────────────────────────

const listCreditCards = vi.fn();
const createCreditCard = vi.fn();
const updateCreditCard = vi.fn();
const deleteCreditCard = vi.fn();
const getUsdRate = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    listCreditCards: (...a: unknown[]) => listCreditCards(...a),
    createCreditCard: (...a: unknown[]) => createCreditCard(...a),
    updateCreditCard: (...a: unknown[]) => updateCreditCard(...a),
    deleteCreditCard: (...a: unknown[]) => deleteCreditCard(...a),
    getUsdRate: (...a: unknown[]) => getUsdRate(...a),
    getRates: () => Promise.resolve({ rates: { TRY: "1", USD: "35", EUR: "38", GBP: "44", CHF: "40", JPY: "0.23" } }),
  },
  CURRENCIES: ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"],
}));

const routerReplace = vi.fn();
const routerPush = vi.fn();
const routerStub = { replace: routerReplace, push: routerPush, prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

// STABIL t referansı — her render'da yeni arrow dönerse refresh useCallback([t])
// kimliği değişir, useEffect tekrar çalışır ve listCreditCards 2x çağrılır.
const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => i18nStub,
}));

const confirmMock = vi.fn();
vi.mock("@/app/_components/ConfirmDialog", () => ({
  useConfirm: () => confirmMock,
}));

// Import AFTER mocks
import CreditCardsPage from "@/app/dashboard/credit-cards/page";

// ─── Fixtures ────────────────────────────────────────────────────────────────

function makeCard(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    name: "Bonus Kart",
    bank_name: "Garanti",
    last_4: "4242",
    credit_limit: "50000",
    statement_day: 5,
    payment_due_day: 15,
    current_period_debt: "1000.00",
    notes: "kişisel",
    currency: "TRY",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    unpaid_statement_total: "2000.00",
    unpaid_statement_count: 1,
    future_installment_total: "500.00",
    period_debt: "1000.00",
    total_debt: "3500.00",
    // Faz B/C: *_display (TRY → raw ile birebir)
    display_currency: "TRY",
    period_debt_display: "3000.00",
    total_debt_display: "3500.00",
    ...over,
  };
}

function makeSummary(cards: ReturnType<typeof makeCard>[] = [makeCard()]) {
  return {
    cards,
    total_period_debt: "1000.00",
    total_debt: "3500.00",
    total_current_period_debt: "1000.00",
    display_currency: "TRY",
    total_period_debt_display: "3000.00",
    total_debt_display: "3500.00",
  };
}

beforeEach(() => {
  listCreditCards.mockReset();
  createCreditCard.mockReset();
  updateCreditCard.mockReset();
  deleteCreditCard.mockReset();
  getUsdRate.mockReset();
  routerReplace.mockReset();
  routerPush.mockReset();
  confirmMock.mockReset();
  confirmMock.mockResolvedValue(true);
  getUsdRate.mockResolvedValue({ usd_try: "33.0" });
  localStorage.clear();
});

// ─── Render + load ───────────────────────────────────────────────────────────

describe("CreditCardsPage — yükleme ve liste", () => {
  it("yüklenirken loading metni gösterir, sonra listeyi çeker", async () => {
    let resolve!: (v: unknown) => void;
    listCreditCards.mockImplementation(() => new Promise((res) => { resolve = res; }));

    render(<CreditCardsPage />);
    expect(screen.getByText("common.loading")).toBeInTheDocument();

    resolve(makeSummary());
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    expect(listCreditCards).toHaveBeenCalledTimes(1);
  });

  it("kart listesi satırlarını ve banka/last4/notes alanlarını gösterir", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    render(<CreditCardsPage />);

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    expect(screen.getByText("Garanti")).toBeInTheDocument();
    expect(screen.getByText("**** 4242")).toBeInTheDocument();
    expect(screen.getByText("kişisel")).toBeInTheDocument();
  });

  it("boş liste → noCards mesajı", async () => {
    listCreditCards.mockResolvedValue(makeSummary([]));
    render(<CreditCardsPage />);

    expect(await screen.findByText("content.creditCards.noCards")).toBeInTheDocument();
  });

  it("401 hatası → login'e replace", async () => {
    listCreditCards.mockRejectedValue(new Error("Request failed 401 Unauthorized"));
    render(<CreditCardsPage />);

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/login"));
  });

  it("401 dışı Error → hata mesajı gösterilir, yönlendirme yok", async () => {
    listCreditCards.mockRejectedValue(new Error("sunucu patladı"));
    render(<CreditCardsPage />);

    expect(await screen.findByText("sunucu patladı")).toBeInTheDocument();
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("Error olmayan hata → fallback loadFailed çevirisi", async () => {
    listCreditCards.mockRejectedValue("string hata");
    render(<CreditCardsPage />);

    expect(await screen.findByText("content.creditCards.loadFailed")).toBeInTheDocument();
  });
});

// ─── Çoklu ödenmemiş ekstre uyarısı ─────────────────────────────────────────

describe("CreditCardsPage — çoklu ödenmemiş ekstre uyarısı", () => {
  it("unpaid_statement_count >= 2 olan kart → amber uyarı + satır rozeti", async () => {
    listCreditCards.mockResolvedValue(
      makeSummary([makeCard({ unpaid_statement_count: 3 })]),
    );
    render(<CreditCardsPage />);

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    // başlık "⚠ " prefix'i ile geldiği için substring matcher kullan.
    expect(
      screen.getByText("content.creditCards.multiUnpaidTitle", { exact: false }),
    ).toBeInTheDocument();
    // satır rozeti recordCount (count>=2 olunca render edilir)
    expect(screen.getAllByText("content.creditCards.recordCount", { exact: false }).length).toBeGreaterThan(0);
  });

  it("hepsi < 2 ise uyarı gösterilmez", async () => {
    listCreditCards.mockResolvedValue(makeSummary([makeCard({ unpaid_statement_count: 1 })]));
    render(<CreditCardsPage />);

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    expect(screen.queryByText("content.creditCards.multiUnpaidTitle")).not.toBeInTheDocument();
  });
});

// ─── Ekleme (create) ─────────────────────────────────────────────────────────

describe("CreditCardsPage — yeni kart ekleme", () => {
  it("isim boşsa → nameRequired hatası, create çağrılmaz", async () => {
    listCreditCards.mockResolvedValue(makeSummary([]));
    render(<CreditCardsPage />);
    expect(await screen.findByText("content.creditCards.noCards")).toBeInTheDocument();

    // required attribute'u jsdom constraint validation'ı submit'i engeller;
    // JS guard'ını (name.trim()) test etmek için form submit'i doğrudan ateşle.
    const nameInput = screen.getByPlaceholderText("content.creditCards.cardNamePlaceholder");
    fireEvent.submit(nameInput.closest("form")!);

    expect(createCreditCard).not.toHaveBeenCalled();
    expect(await screen.findByText("content.creditCards.nameRequired")).toBeInTheDocument();
  });

  it("geçerli form → createCreditCard payload + refresh", async () => {
    listCreditCards
      .mockResolvedValueOnce(makeSummary([]))
      .mockResolvedValueOnce(makeSummary());
    createCreditCard.mockResolvedValue(makeCard());
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("content.creditCards.noCards")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("content.creditCards.cardNamePlaceholder"), "Yeni Kart");
    await user.type(screen.getByPlaceholderText("content.creditCards.bankNamePlaceholder"), "Akbank");
    await user.type(screen.getByPlaceholderText("content.creditCards.last4Placeholder"), "9999");
    await user.type(screen.getByPlaceholderText("content.creditCards.limitPlaceholder"), "12000");
    await user.type(screen.getByPlaceholderText("content.creditCards.currentDebtPlaceholder"), "300");
    await user.type(screen.getByPlaceholderText("content.creditCards.notesPlaceholder"), "not");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() => expect(createCreditCard).toHaveBeenCalledTimes(1));
    const payload = createCreditCard.mock.calls[0][0];
    expect(payload).toMatchObject({
      name: "Yeni Kart",
      bank_name: "Akbank",
      last_4: "9999",
      credit_limit: 12000,
      current_period_debt: 300,
      notes: "not",
    });
    // refresh sonrası ikinci listeleme
    await waitFor(() => expect(listCreditCards).toHaveBeenCalledTimes(2));
  });

  it("boş opsiyonel alanlar → null/0 default'larıyla create", async () => {
    listCreditCards
      .mockResolvedValueOnce(makeSummary([]))
      .mockResolvedValueOnce(makeSummary([]));
    createCreditCard.mockResolvedValue(makeCard());
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("content.creditCards.noCards")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("content.creditCards.cardNamePlaceholder"), "Sade Kart");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    await waitFor(() => expect(createCreditCard).toHaveBeenCalled());
    const payload = createCreditCard.mock.calls[0][0];
    expect(payload).toMatchObject({
      name: "Sade Kart",
      bank_name: null,
      last_4: null,
      credit_limit: null,
      statement_day: 1,
      payment_due_day: 10,
      current_period_debt: 0,
      notes: null,
    });
  });

  it("create backend hatası → saveFailed/error gösterilir", async () => {
    listCreditCards.mockResolvedValue(makeSummary([]));
    createCreditCard.mockRejectedValue(new Error("kayıt hatası"));
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("content.creditCards.noCards")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("content.creditCards.cardNamePlaceholder"), "X");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    expect(await screen.findByText("kayıt hatası")).toBeInTheDocument();
  });

  it("create hatası (Error olmayan) → saveFailed fallback", async () => {
    listCreditCards.mockResolvedValue(makeSummary([]));
    createCreditCard.mockRejectedValue("boom");
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("content.creditCards.noCards")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("content.creditCards.cardNamePlaceholder"), "X");
    await user.click(screen.getByRole("button", { name: "form.add" }));

    expect(await screen.findByText("content.creditCards.saveFailed")).toBeInTheDocument();
  });
});

// ─── Düzenleme (edit/update) ─────────────────────────────────────────────────

describe("CreditCardsPage — düzenleme", () => {
  it("düzen → form alanları dolar, update çağrılır, cancel ile sıfırlanır", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    updateCreditCard.mockResolvedValue(makeCard());
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "common.edit" }));

    const nameInput = screen.getByPlaceholderText(
      "content.creditCards.cardNamePlaceholder",
    ) as HTMLInputElement;
    expect(nameInput.value).toBe("Bonus Kart");
    // başlık editCard'a döner
    expect(screen.getByText("content.creditCards.editCard")).toBeInTheDocument();

    await user.clear(nameInput);
    await user.type(nameInput, "Güncel Kart");
    await user.click(screen.getByRole("button", { name: "form.update" }));

    await waitFor(() => expect(updateCreditCard).toHaveBeenCalledTimes(1));
    expect(updateCreditCard.mock.calls[0][0]).toBe(1);
    expect(updateCreditCard.mock.calls[0][1]).toMatchObject({ name: "Güncel Kart" });
  });

  it("cancel → editing temizlenir, form boşalır, newCard başlığı", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "common.edit" }));
    await user.click(screen.getByRole("button", { name: "common.cancel" }));

    const nameInput = screen.getByPlaceholderText(
      "content.creditCards.cardNamePlaceholder",
    ) as HTMLInputElement;
    expect(nameInput.value).toBe("");
    expect(screen.getByText("content.creditCards.newCard")).toBeInTheDocument();
  });

  it("null opsiyonel değerli kartı düzenleme → form boş stringlerle dolar", async () => {
    listCreditCards.mockResolvedValue(
      makeSummary([makeCard({ bank_name: null, last_4: null, credit_limit: null, notes: null })]),
    );
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "common.edit" }));
    const bankInput = screen.getByPlaceholderText(
      "content.creditCards.bankNamePlaceholder",
    ) as HTMLInputElement;
    expect(bankInput.value).toBe("");
  });
});

// ─── Silme (delete) ──────────────────────────────────────────────────────────

describe("CreditCardsPage — silme", () => {
  it("onaylanırsa → deleteCreditCard + refresh", async () => {
    listCreditCards
      .mockResolvedValueOnce(makeSummary())
      .mockResolvedValueOnce(makeSummary([]));
    deleteCreditCard.mockResolvedValue(undefined);
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteCardAria" }),
    );

    await waitFor(() => expect(deleteCreditCard).toHaveBeenCalledWith(1));
    await waitFor(() => expect(listCreditCards).toHaveBeenCalledTimes(2));
  });

  it("onaylanmazsa → deleteCreditCard çağrılmaz", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    confirmMock.mockResolvedValue(false);
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteCardAria" }),
    );

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    expect(deleteCreditCard).not.toHaveBeenCalled();
  });

  it("delete backend hatası → error mesajı", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    deleteCreditCard.mockRejectedValue(new Error("silinemedi"));
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteCardAria" }),
    );

    expect(await screen.findByText("silinemedi")).toBeInTheDocument();
  });

  it("delete hatası (Error olmayan) → deleteFailed fallback", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    deleteCreditCard.mockRejectedValue("x");
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteCardAria" }),
    );

    expect(await screen.findByText("content.creditCards.deleteFailed")).toBeInTheDocument();
  });
});

// ─── Navigasyon ──────────────────────────────────────────────────────────────

describe("CreditCardsPage — detay navigasyonu", () => {
  it("statement/installment butonu → router.push detay url", async () => {
    listCreditCards.mockResolvedValue(makeSummary([makeCard({ id: 7 })]));
    const user = userEvent.setup({ delay: null });
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.statementInstallment" }),
    );

    expect(routerPush).toHaveBeenCalledWith("/dashboard/credit-cards/7");
  });

  it("toplam borç ve dönem borcu özet metriklerini render eder", async () => {
    listCreditCards.mockResolvedValue(makeSummary());
    render(<CreditCardsPage />);
    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();

    // Özet panel başlıkları (table.totalDebt hem panelde hem tablo başlığında var)
    expect(screen.getAllByText("table.totalDebt").length).toBeGreaterThan(0);
    expect(screen.getByText("dashboard.currentPeriodDebt")).toBeInTheDocument();
    // totalDebtHint kart sayısını gösterir
    expect(screen.getByText("content.creditCards.totalDebtHint")).toBeInTheDocument();
  });
});
