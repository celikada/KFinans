import { Suspense } from "react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

// ─── Mocks ──────────────────────────────────────────────────────────────────

const getCreditCardDetail = vi.fn();
const createStatement = vi.fn();
const updateStatement = vi.fn();
const deleteStatement = vi.fn();
const createInstallment = vi.fn();
const updateInstallment = vi.fn();
const deleteInstallment = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getCreditCardDetail: (...a: unknown[]) => getCreditCardDetail(...a),
    createStatement: (...a: unknown[]) => createStatement(...a),
    updateStatement: (...a: unknown[]) => updateStatement(...a),
    deleteStatement: (...a: unknown[]) => deleteStatement(...a),
    createInstallment: (...a: unknown[]) => createInstallment(...a),
    updateInstallment: (...a: unknown[]) => updateInstallment(...a),
    deleteInstallment: (...a: unknown[]) => deleteInstallment(...a),
    getRates: () => Promise.resolve({ rates: { TRY: "1", USD: "35", EUR: "38", GBP: "44", CHF: "40", JPY: "0.23" } }),
  },
  CURRENCIES: ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"],
}));

const routerReplace = vi.fn();
const routerStub = { replace: routerReplace, push: vi.fn(), prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

// STABIL t referansı — refresh useCallback([cardId, router, t]) kimliği
// değişmesin diye (aksi halde getCreditCardDetail birden çok kez çağrılır).
const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => i18nStub,
}));

const confirmMock = vi.fn();
vi.mock("@/app/_components/ConfirmDialog", () => ({
  useConfirm: () => confirmMock,
}));

// Import AFTER mocks
import CreditCardDetailPage from "@/app/dashboard/credit-cards/[id]/page";

// Sayfa React 19 `use(params)` ile Promise'i okur. jsdom+vitest'te düz bir
// Promise.resolve() React'in suspended fiber'ı güvenilir biçimde retry
// etmesini sağlamıyor (flaky → bazen suspense.fallback'te asılı kalıyor).
// Çözüm: React'in eşzamanlı okuduğu "fulfilled" işaretli thenable ver
// (use() promise.status === "fulfilled" ise value'yu suspend etmeden döner).
function fulfilledThenable<T>(value: T): Promise<T> {
  const p = Promise.resolve(value) as Promise<T> & { status: string; value: T };
  p.status = "fulfilled";
  p.value = value;
  return p;
}

function renderDetail() {
  const params = fulfilledThenable({ id: "1" });
  return render(
    <Suspense fallback={<div>suspense.fallback</div>}>
      <CreditCardDetailPage params={params} />
    </Suspense>,
  );
}

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
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    unpaid_statement_total: "2000.00",
    unpaid_statement_count: 1,
    future_installment_total: "500.00",
    period_debt: "1500.00",
    total_debt: "3500.00",
    ...over,
  };
}

function makeStatement(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 10,
    card_id: 1,
    period_year: 2026,
    period_month: 3,
    statement_amount: "1200.50",
    statement_date: "2026-03-05",
    due_date: "2026-03-15",
    paid_at: null,
    notes: null,
    created_at: "2026-03-05T00:00:00Z",
    ...over,
  };
}

function makeInstallment(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 20,
    card_id: 1,
    description: "Buzdolabı",
    total_amount: "12000.00",
    monthly_amount: "1000.00",
    installments_total: 12,
    installments_remaining: 8,
    first_due_date: "2026-02-01",
    notes: null,
    created_at: "2026-02-01T00:00:00Z",
    ...over,
  };
}

function makeDetail(over: {
  card?: Partial<Record<string, unknown>>;
  statements?: ReturnType<typeof makeStatement>[];
  installments?: ReturnType<typeof makeInstallment>[];
} = {}) {
  return {
    card: makeCard(over.card),
    statements: over.statements ?? [],
    installments: over.installments ?? [],
  };
}

beforeEach(() => {
  getCreditCardDetail.mockReset();
  createStatement.mockReset();
  updateStatement.mockReset();
  deleteStatement.mockReset();
  createInstallment.mockReset();
  updateInstallment.mockReset();
  deleteInstallment.mockReset();
  routerReplace.mockReset();
  confirmMock.mockReset();
  confirmMock.mockResolvedValue(true);
  vi.spyOn(window, "alert").mockImplementation(() => {});
});

// ─── Yükleme + hata + üst panel ──────────────────────────────────────────────

describe("CreditCardDetailPage — yükleme ve üst panel", () => {
  it("detay resolve sonrası kartı gösterir + doğru id ile çağrılır", async () => {
    // NOT: Sayfa `use(params)` ile suspend olur; bu test ortamında React
    // suspended fiber'ı yalnızca getCreditCardDetail resolve olunca retry eder,
    // bu yüzden geçici `loading` frame'i ayrıca gözlemlenemez (resolved path
    // refresh + render'ı zaten kapsar).
    getCreditCardDetail.mockResolvedValue(makeDetail());

    renderDetail();

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    expect(getCreditCardDetail).toHaveBeenCalledWith(1);
  });

  it("kart bilgisi + 4 borç metriği + limit + utilization gösterir", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    renderDetail();

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    expect(screen.getByText("Garanti")).toBeInTheDocument();
    expect(screen.getByText("**** 4242")).toBeInTheDocument();
    // utilization branch (limit > 0)
    expect(screen.getByText("content.creditCards.utilization")).toBeInTheDocument();
    expect(screen.getByText("content.creditCards.limitLabel:", { exact: false })).toBeInTheDocument();
  });

  it("limit null → utilization gizli, banka null → tire", async () => {
    getCreditCardDetail.mockResolvedValue(
      makeDetail({ card: { credit_limit: null, bank_name: null } }),
    );
    renderDetail();

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    expect(screen.queryByText("content.creditCards.utilization")).not.toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("unpaid_statement_count >= 2 → amber rozet gösterir", async () => {
    getCreditCardDetail.mockResolvedValue(
      makeDetail({ card: { unpaid_statement_count: 4 } }),
    );
    renderDetail();

    expect(await screen.findByText("Bonus Kart")).toBeInTheDocument();
    // recordCount iki bölüm başlığında (ekstre+taksit) ve count>=2 rozetinde var;
    // rozette "⚠ " prefix olduğu için substring matcher gerekir → toplam >2.
    expect(
      screen.getAllByText("content.creditCards.recordCount", { exact: false }).length,
    ).toBeGreaterThan(2);
  });

  it("401 hatası → login'e replace", async () => {
    getCreditCardDetail.mockRejectedValue(new Error("boom 401 yetkisiz"));
    renderDetail();

    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/login"));
  });

  it("401 dışı Error → hata bloğu gösterilir", async () => {
    getCreditCardDetail.mockRejectedValue(new Error("detay hatası"));
    renderDetail();

    expect(await screen.findByText("detay hatası")).toBeInTheDocument();
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("Error olmayan hata → loadFailed fallback", async () => {
    getCreditCardDetail.mockRejectedValue("x");
    renderDetail();

    expect(await screen.findByText("content.creditCards.loadFailed")).toBeInTheDocument();
  });
});

// ─── Ekstreler bölümü ────────────────────────────────────────────────────────

describe("CreditCardDetailPage — ekstreler", () => {
  it("ekstre yoksa → noStatement mesajı", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    renderDetail();

    expect(await screen.findByText("empty.noStatement")).toBeInTheDocument();
  });

  it("ekstre listesi + paid_at rozeti render eder", async () => {
    getCreditCardDetail.mockResolvedValue(
      makeDetail({
        statements: [makeStatement({ paid_at: "2026-03-20T00:00:00Z", notes: "tamam" })],
      }),
    );
    renderDetail();

    expect(await screen.findByText("content.creditCards.paidBadge")).toBeInTheDocument();
    expect(screen.getByText("tamam")).toBeInTheDocument();
  });

  it("tutar boşsa → amountRequired, createStatement çağrılmaz", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noStatement")).toBeInTheDocument();

    const addButtons = screen.getAllByRole("button", { name: "form.add" });
    await user.click(addButtons[0]); // ekstre formu ilk

    expect(createStatement).not.toHaveBeenCalled();
    expect(await screen.findByText("content.creditCards.amountRequired")).toBeInTheDocument();
  });

  it("geçerli tutar → createStatement payload + onChange refresh", async () => {
    getCreditCardDetail
      .mockResolvedValueOnce(makeDetail())
      .mockResolvedValueOnce(makeDetail({ statements: [makeStatement()] }));
    createStatement.mockResolvedValue(makeStatement());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noStatement")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("content.creditCards.amountTlPlaceholder"),
      "1500",
    );
    const addButtons = screen.getAllByRole("button", { name: "form.add" });
    await user.click(addButtons[0]);

    await waitFor(() => expect(createStatement).toHaveBeenCalledTimes(1));
    expect(createStatement.mock.calls[0][0]).toBe(1);
    expect(createStatement.mock.calls[0][1]).toMatchObject({ statement_amount: 1500 });
    await waitFor(() => expect(getCreditCardDetail).toHaveBeenCalledTimes(2));
  });

  it("paid checkbox işaretli → payload.paid_at dolu", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    createStatement.mockResolvedValue(makeStatement());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noStatement")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("content.creditCards.amountTlPlaceholder"),
      "900",
    );
    await user.click(screen.getByRole("checkbox"));
    const addButtons = screen.getAllByRole("button", { name: "form.add" });
    await user.click(addButtons[0]);

    await waitFor(() => expect(createStatement).toHaveBeenCalled());
    expect(createStatement.mock.calls[0][1].paid_at).not.toBeNull();
  });

  it("ekstre düzenleme → form dolar + updateStatement + cancel", async () => {
    getCreditCardDetail.mockResolvedValue(
      makeDetail({ statements: [makeStatement()] }),
    );
    updateStatement.mockResolvedValue(makeStatement());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("2026 · content.creditCards.monthMar")).toBeInTheDocument();

    // ilk edit butonu (ekstre) — common.edit birden çok olabilir; ilki ekstre
    const editButtons = screen.getAllByRole("button", { name: "common.edit" });
    await user.click(editButtons[0]);

    const amount = screen.getByPlaceholderText(
      "content.creditCards.amountTlPlaceholder",
    ) as HTMLInputElement;
    expect(amount.value).toBe("1200.50");

    await user.clear(amount);
    await user.type(amount, "1300");
    await user.click(screen.getByRole("button", { name: "form.update" }));

    await waitFor(() => expect(updateStatement).toHaveBeenCalledTimes(1));
    expect(updateStatement.mock.calls[0][0]).toBe(1);
    expect(updateStatement.mock.calls[0][1]).toBe(10);
  });

  it("ekstre düzenleme cancel → form sıfırlanır (form.add geri döner)", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail({ statements: [makeStatement()] }));
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("2026 · content.creditCards.monthMar")).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "common.edit" })[0]);
    // cancel butonu (ekstre formu)
    await user.click(screen.getAllByRole("button", { name: "common.cancel" })[0]);

    const amount = screen.getByPlaceholderText(
      "content.creditCards.amountTlPlaceholder",
    ) as HTMLInputElement;
    expect(amount.value).toBe("");
  });

  it("ekstre create hatası → err mesajı (saveFailed/error)", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    createStatement.mockRejectedValue(new Error("ekstre hatası"));
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noStatement")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("content.creditCards.amountTlPlaceholder"),
      "100",
    );
    await user.click(screen.getAllByRole("button", { name: "form.add" })[0]);

    expect(await screen.findByText("ekstre hatası")).toBeInTheDocument();
  });

  it("ekstre silme onaylı → deleteStatement + onChange", async () => {
    getCreditCardDetail
      .mockResolvedValueOnce(makeDetail({ statements: [makeStatement()] }))
      .mockResolvedValueOnce(makeDetail());
    deleteStatement.mockResolvedValue(undefined);
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("2026 · content.creditCards.monthMar")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteStatementAria" }),
    );

    await waitFor(() => expect(deleteStatement).toHaveBeenCalledWith(1, 10));
    await waitFor(() => expect(getCreditCardDetail).toHaveBeenCalledTimes(2));
  });

  it("ekstre silme onaysız → deleteStatement çağrılmaz", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail({ statements: [makeStatement()] }));
    confirmMock.mockResolvedValue(false);
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("2026 · content.creditCards.monthMar")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteStatementAria" }),
    );

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    expect(deleteStatement).not.toHaveBeenCalled();
  });

  it("ekstre silme hatası → alert çağrılır", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail({ statements: [makeStatement()] }));
    deleteStatement.mockRejectedValue(new Error("silme hatası"));
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("2026 · content.creditCards.monthMar")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteStatementAria" }),
    );

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith("silme hatası"));
  });
});

// ─── Taksitler bölümü ────────────────────────────────────────────────────────

describe("CreditCardDetailPage — taksitler", () => {
  it("taksit yoksa → noInstallment mesajı", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    renderDetail();

    expect(await screen.findByText("empty.noInstallment")).toBeInTheDocument();
  });

  it("taksit listesi + kalan/toplam + notlar render eder", async () => {
    getCreditCardDetail.mockResolvedValue(
      makeDetail({ installments: [makeInstallment({ notes: "beyaz eşya" })] }),
    );
    renderDetail();

    expect(await screen.findByText("Buzdolabı")).toBeInTheDocument();
    expect(screen.getByText("beyaz eşya")).toBeInTheDocument();
    // installmentsRemaining metni firstDueLabel ile aynı <p> içinde parçalı.
    expect(
      screen.getByText("content.creditCards.installmentsRemaining", { exact: false }),
    ).toBeInTheDocument();
  });

  it("açıklama boşsa → descriptionRequired, createInstallment çağrılmaz", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    renderDetail();
    expect(await screen.findByText("empty.noInstallment")).toBeInTheDocument();

    // description input required; jsdom constraint validation submit'i engeller.
    // JS guard'ını test etmek için taksit formunu doğrudan submit et.
    const descInput = screen.getByPlaceholderText(
      "content.creditCards.installmentDescPlaceholder",
    );
    fireEvent.submit(descInput.closest("form")!);

    expect(createInstallment).not.toHaveBeenCalled();
    expect(await screen.findByText("content.creditCards.descriptionRequired")).toBeInTheDocument();
  });

  it("aylık tutar + adet → canlı toplam önizleme gösterir", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noInstallment")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("content.creditCards.monthlyInstallmentPlaceholder"),
      "500",
    );
    // total varsayılan 12 → preview = 6.000,00 (fmtCurrency ile biçimli)
    expect(await screen.findByText("6.000,00", { exact: false })).toBeInTheDocument();
  });

  it("geçerli taksit → createInstallment payload + refresh", async () => {
    getCreditCardDetail
      .mockResolvedValueOnce(makeDetail())
      .mockResolvedValueOnce(makeDetail({ installments: [makeInstallment()] }));
    createInstallment.mockResolvedValue(makeInstallment());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noInstallment")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("content.creditCards.installmentDescPlaceholder"),
      "Telefon",
    );
    await user.type(
      screen.getByPlaceholderText("content.creditCards.monthlyInstallmentPlaceholder"),
      "750",
    );
    await user.click(screen.getAllByRole("button", { name: "form.add" })[1]);

    await waitFor(() => expect(createInstallment).toHaveBeenCalledTimes(1));
    expect(createInstallment.mock.calls[0][0]).toBe(1);
    expect(createInstallment.mock.calls[0][1]).toMatchObject({
      description: "Telefon",
      monthly_amount: 750,
      installments_total: 12,
    });
    await waitFor(() => expect(getCreditCardDetail).toHaveBeenCalledTimes(2));
  });

  it("taksit düzenleme → form dolar + updateInstallment + cancel sıfırlar", async () => {
    getCreditCardDetail.mockResolvedValue(
      makeDetail({ installments: [makeInstallment()] }),
    );
    updateInstallment.mockResolvedValue(makeInstallment());
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("Buzdolabı")).toBeInTheDocument();

    // taksit edit = ilk (ve tek) common.edit (ekstre yok)
    await user.click(screen.getByRole("button", { name: "common.edit" }));
    const desc = screen.getByPlaceholderText(
      "content.creditCards.installmentDescPlaceholder",
    ) as HTMLInputElement;
    expect(desc.value).toBe("Buzdolabı");

    await user.clear(desc);
    await user.type(desc, "Çamaşır Makinesi");
    await user.click(screen.getByRole("button", { name: "form.update" }));

    await waitFor(() => expect(updateInstallment).toHaveBeenCalledTimes(1));
    expect(updateInstallment.mock.calls[0][0]).toBe(1);
    expect(updateInstallment.mock.calls[0][1]).toBe(20);
  });

  it("taksit create hatası → err mesajı", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail());
    createInstallment.mockRejectedValue(new Error("taksit hatası"));
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("empty.noInstallment")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("content.creditCards.installmentDescPlaceholder"),
      "X",
    );
    await user.type(
      screen.getByPlaceholderText("content.creditCards.monthlyInstallmentPlaceholder"),
      "10",
    );
    await user.click(screen.getAllByRole("button", { name: "form.add" })[1]);

    expect(await screen.findByText("taksit hatası")).toBeInTheDocument();
  });

  it("taksit silme onaylı → deleteInstallment + onChange", async () => {
    getCreditCardDetail
      .mockResolvedValueOnce(makeDetail({ installments: [makeInstallment()] }))
      .mockResolvedValueOnce(makeDetail());
    deleteInstallment.mockResolvedValue(undefined);
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("Buzdolabı")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteInstallmentAria" }),
    );

    await waitFor(() => expect(deleteInstallment).toHaveBeenCalledWith(1, 20));
    await waitFor(() => expect(getCreditCardDetail).toHaveBeenCalledTimes(2));
  });

  it("taksit silme hatası → alert", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail({ installments: [makeInstallment()] }));
    deleteInstallment.mockRejectedValue(new Error("taksit silinemedi"));
    confirmMock.mockResolvedValue(true);
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("Buzdolabı")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteInstallmentAria" }),
    );

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith("taksit silinemedi"));
  });

  it("taksit silme onaysız → deleteInstallment çağrılmaz", async () => {
    getCreditCardDetail.mockResolvedValue(makeDetail({ installments: [makeInstallment()] }));
    confirmMock.mockResolvedValue(false);
    const user = userEvent.setup({ delay: null });
    renderDetail();
    expect(await screen.findByText("Buzdolabı")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "content.creditCards.deleteInstallmentAria" }),
    );

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    expect(deleteInstallment).not.toHaveBeenCalled();
  });
});
