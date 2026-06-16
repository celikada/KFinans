import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.setConfig({ testTimeout: 30000 });

const previewBillImport = vi.fn();
const commitBillImport = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    previewBillImport: (...a: unknown[]) => previewBillImport(...a),
    commitBillImport: (...a: unknown[]) => commitBillImport(...a),
  },
  CURRENCIES: ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"],
}));

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import { SubscriptionBillImport } from "@/app/dashboard/expenses/_components/SubscriptionBillImport";

const PARSED_NEW = {
  provider_code: "esgaz",
  provider_name: "ESGAZ",
  category: "gas",
  subscriber_no: "12345",
  bill_amount: "450.75",
  currency: "TRY",
  bill_date: "2026-06-01",
  due_date: "2026-06-15",
  period_year: 2026,
  period_month: 6,
  next_bill_date: null,
  next_due_date: null,
  bill_no: "B-99",
  matched_subscription_id: null,
  matched_label: null,
  warnings: [],
};

function pdfFile() {
  return new File(["%PDF-1.4 fake"], "bill.pdf", { type: "application/pdf" });
}

describe("SubscriptionBillImport", () => {
  beforeEach(() => {
    previewBillImport.mockReset();
    commitBillImport.mockReset();
  });

  it("PDF yükleyince önizleme alanlarını doldurur (yeni abonelik göstergesi)", async () => {
    previewBillImport.mockResolvedValue(PARSED_NEW);
    render(<SubscriptionBillImport onImported={vi.fn()} />);
    const user = userEvent.setup({ delay: null });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, pdfFile());

    await waitFor(() => expect(previewBillImport).toHaveBeenCalled());
    // Önizleme tutarı düzenlenebilir alana yansıdı.
    expect((screen.getByLabelText("content.subscriptions.import.amount") as HTMLInputElement).value).toBe("450.75");
    // Eşleşme yok → yeni abonelik göstergesi.
    expect(screen.getByText(/content.subscriptions.import.newSubscription/)).toBeInTheDocument();
  });

  it("önizleme sonrası onaylayınca commitBillImport doğru payload ile çağrılır", async () => {
    previewBillImport.mockResolvedValue(PARSED_NEW);
    commitBillImport.mockResolvedValue({ id: 11 });
    const onImported = vi.fn();
    render(<SubscriptionBillImport onImported={onImported} />);
    const user = userEvent.setup({ delay: null });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, pdfFile());
    await waitFor(() => expect(previewBillImport).toHaveBeenCalled());

    await user.click(screen.getByText("content.subscriptions.import.save"));

    await waitFor(() => expect(commitBillImport).toHaveBeenCalled());
    const payload = commitBillImport.mock.calls[0][0];
    expect(payload.provider_code).toBe("esgaz");
    expect(payload.subscriber_no).toBe("12345");
    expect(payload.bill_amount).toBe(450.75);
    expect(payload.period_year).toBe(2026);
    expect(payload.period_month).toBe(6);
    expect(payload.subscription_id).toBeNull();
    expect(payload.bill_no).toBe("B-99");
    expect(onImported).toHaveBeenCalled();
  });

  it("eşleşen abonelik varsa 'mevcut aboneliğe eklenecek' gösterir + subscription_id taşır", async () => {
    previewBillImport.mockResolvedValue({
      ...PARSED_NEW,
      matched_subscription_id: 7,
      matched_label: "Ev",
    });
    commitBillImport.mockResolvedValue({ id: 12 });
    render(<SubscriptionBillImport onImported={vi.fn()} />);
    const user = userEvent.setup({ delay: null });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, pdfFile());
    await waitFor(() => expect(previewBillImport).toHaveBeenCalled());
    expect(screen.getByText(/content.subscriptions.import.matchedSubscription/)).toBeInTheDocument();

    await user.click(screen.getByText("content.subscriptions.import.save"));
    await waitFor(() => expect(commitBillImport).toHaveBeenCalled());
    expect(commitBillImport.mock.calls[0][0].subscription_id).toBe(7);
  });

  it("preview 422 hatasında mesajı gösterir (görüntü-PDF → elle girin)", async () => {
    previewBillImport.mockRejectedValue(new Error("PDF metin katmanı yok — elle girin"));
    render(<SubscriptionBillImport onImported={vi.fn()} />);
    const user = userEvent.setup({ delay: null });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, pdfFile());

    await waitFor(() => expect(screen.getByText(/elle girin/)).toBeInTheDocument());
    // Hata durumunda önizleme alanları açılmaz.
    expect(screen.queryByText("content.subscriptions.import.save")).not.toBeInTheDocument();
  });
});
