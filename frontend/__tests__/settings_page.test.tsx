import type { ReactNode } from "react";
import { describe, expect, it, beforeEach, vi } from "vitest";

// v8 coverage instrumentasyonu altinda etkilesimler yavaslayabiliyor; timeout yukselt.
vi.setConfig({ testTimeout: 30000 });

import { render, screen, waitFor } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────

const getMe = vi.fn();
const updateProfile = vi.fn();
const changePassword = vi.fn();
const deleteAccount = vi.fn();
const clearAuth = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getMe: (...a: unknown[]) => getMe(...a),
    updateProfile: (...a: unknown[]) => updateProfile(...a),
    changePassword: (...a: unknown[]) => changePassword(...a),
    deleteAccount: (...a: unknown[]) => deleteAccount(...a),
  },
  clearAuth: (...a: unknown[]) => clearAuth(...a),
  // Sayfa RISK_PROFILE_LABELS + UserMeDTO import ediyor; label sabitleri lazim.
  RISK_PROFILE_LABELS: {
    conservative: "Muhafazakâr",
    balanced: "Dengeli",
    aggressive: "Agresif",
  },
  CURRENCIES: ["TRY", "USD", "EUR", "GBP", "CHF", "JPY"],
}));

const routerReplace = vi.fn();
const routerStub = { replace: routerReplace, push: vi.fn(), prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "tr",
    setLocale: vi.fn(),
  }),
}));

// useConfirm — hesap silme onay dialog'u. Varsayilan: onaylar (true).
const confirmFn = vi.fn();
vi.mock("@/app/_components/ConfirmDialog", () => ({
  useConfirm: () => confirmFn,
}));

// getShowUsd / setShowUsd — USD karsiligi toggle persistans.
const getShowUsd = vi.fn();
const setShowUsd = vi.fn();
vi.mock("@/app/_components/TLValue", () => ({
  getShowUsd: (...a: unknown[]) => getShowUsd(...a),
  setShowUsd: (...a: unknown[]) => setShowUsd(...a),
}));

// Import AFTER mocks
import SettingsPage from "@/app/dashboard/settings/page";

const USER = {
  email: "demo@kfinans.app",
  risk_profile: "balanced" as const,
  created_at: "2026-01-15T10:00:00Z",
  email_verified: true,
  credit_balance: 3,
};

beforeEach(() => {
  getMe.mockReset();
  updateProfile.mockReset();
  changePassword.mockReset();
  deleteAccount.mockReset();
  clearAuth.mockReset();
  routerReplace.mockReset();
  confirmFn.mockReset();
  getShowUsd.mockReset();
  setShowUsd.mockReset();

  getMe.mockResolvedValue(USER);
  confirmFn.mockResolvedValue(true);
  getShowUsd.mockReturnValue(false);
  localStorage.clear();
});

// ─── Yukleme + ilk render ───────────────────────────────────────────────────

describe("SettingsPage — yukleme", () => {
  it("yuklenirken loading metni gosterir, sonra kullaniciyi ceker", async () => {
    let resolve!: (v: typeof USER) => void;
    getMe.mockImplementation(() => new Promise((r) => (resolve = r)));

    render(<SettingsPage />);
    expect(screen.getByText("common.loading")).toBeInTheDocument();

    resolve(USER);
    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    expect(getMe).toHaveBeenCalledTimes(1);
  });

  it("kullanici yuklenince e-posta + uyelik tarihi readonly dolar", async () => {
    render(<SettingsPage />);
    const email = (await screen.findByLabelText("auth.email")) as HTMLInputElement;
    expect(email.value).toBe(USER.email);
    expect(email.readOnly).toBe(true);

    const joined = screen.getByLabelText(
      "content.settings.membershipDate",
    ) as HTMLInputElement;
    // fmtDate ile bicimlenmis tarih bos olmamali.
    expect(joined.value).not.toBe("");
  });

  it("getMe 401 → login'e yonlendirir", async () => {
    getMe.mockRejectedValue(new Error("Request failed 401 Unauthorized"));
    render(<SettingsPage />);
    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/login"));
  });

  it("getMe 401 disi hata → yonlendirme yok, loading biter", async () => {
    getMe.mockRejectedValue(new Error("500 server error"));
    render(<SettingsPage />);
    // loading biter, hesap bilgileri bolumu gorunur
    expect(await screen.findByText("content.settings.accountInfo")).toBeInTheDocument();
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("created_at yoksa uyelik tarihi alani bos kalir", async () => {
    getMe.mockResolvedValue({ ...USER, created_at: "" });
    render(<SettingsPage />);
    const joined = (await screen.findByLabelText(
      "content.settings.membershipDate",
    )) as HTMLInputElement;
    expect(joined.value).toBe("");
  });
});

// ─── Risk profili ───────────────────────────────────────────────────────────

describe("SettingsPage — yatirim profili", () => {
  it("baslangic risk profili kullanicidan secili gelir", async () => {
    render(<SettingsPage />);
    const balanced = await screen.findByRole("button", { name: "Dengeli" });
    expect(balanced.className).toContain("bg-blue-600");
  });

  it("risk secimi degisir ve kaydet → updateProfile + basari mesaji", async () => {
    updateProfile.mockResolvedValue({ ...USER, risk_profile: "aggressive" });
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(await screen.findByRole("button", { name: "Agresif" }));
    await user.click(screen.getByRole("button", { name: "common.save" }));

    await waitFor(() =>
      // v0.3.0: updateProfile artik (risk, default_currency) ile cagrilir
      expect(updateProfile).toHaveBeenCalledWith("aggressive", expect.any(String)),
    );
    expect(
      await screen.findByText("content.settings.profileUpdated"),
    ).toBeInTheDocument();
  });

  it("e-posta odeme hatirlatmasi toggle → updateProfile(risk, undefined, true)", async () => {
    getMe.mockResolvedValue({ ...USER, payment_reminder_email: false });
    updateProfile.mockResolvedValue({ ...USER, payment_reminder_email: true });
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(getMe).toHaveBeenCalled());

    await user.click(await screen.findByLabelText("content.settings.emailReminder.toggleOn"));
    await waitFor(() =>
      expect(updateProfile).toHaveBeenCalledWith("balanced", undefined, true),
    );
  });

  it("profil kaydetme hatasi (Error) → mesaj gosterilir", async () => {
    updateProfile.mockRejectedValue(new Error("profil patladi"));
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(await screen.findByRole("button", { name: "common.save" }));
    expect(await screen.findByText("profil patladi")).toBeInTheDocument();
  });

  it("profil kaydetme hatasi (Error olmayan) → fallback ceviri", async () => {
    updateProfile.mockRejectedValue("string hata");
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(await screen.findByRole("button", { name: "common.save" }));
    expect(
      await screen.findByText("content.settings.profileSaveFailed"),
    ).toBeInTheDocument();
  });

  it("kaydetme sirasinda buton disabled + saving metni", async () => {
    let resolve!: (v: typeof USER) => void;
    updateProfile.mockImplementation(() => new Promise((r) => (resolve = r)));
    const user = userEvent.setup();
    render(<SettingsPage />);

    const saveBtn = await screen.findByRole("button", { name: "common.save" });
    await user.click(saveBtn);
    expect(
      await screen.findByRole("button", { name: "common.saving" }),
    ).toBeDisabled();

    resolve(USER);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "common.save" })).toBeEnabled(),
    );
  });
});

// ─── Sifre degistirme ────────────────────────────────────────────────────────

describe("SettingsPage — sifre degistirme", () => {
  async function fillPwd(
    user: ReturnType<typeof userEvent.setup>,
    cur: string,
    np: string,
    np2: string,
  ) {
    await user.type(screen.getByLabelText("content.settings.currentPassword"), cur);
    await user.type(
      screen.getByLabelText("content.settings.newPasswordWithHint"),
      np,
    );
    await user.type(
      screen.getByLabelText("content.settings.repeatNewPassword"),
      np2,
    );
    await user.click(
      screen.getByRole("button", {
        name: "content.settings.updatePasswordBtn",
      }),
    );
  }

  it("yeni sifreler uyusmuyorsa → mismatch hatasi, changePassword cagrilmaz", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.changePassword")).toBeInTheDocument();

    await fillPwd(user, "Eski123!", "Yeni12345", "Farkli12345");
    expect(
      await screen.findByText("content.settings.newPasswordMismatch"),
    ).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("yeni sifre 8 karakterden kisa → min hatasi", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.changePassword")).toBeInTheDocument();

    await fillPwd(user, "Eski123!", "kisa", "kisa");
    expect(
      await screen.findByText("content.settings.newPasswordMin"),
    ).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("gecerli sifre → changePassword cagrilir, alanlar temizlenir + basari", async () => {
    changePassword.mockResolvedValue({});
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.changePassword")).toBeInTheDocument();

    await fillPwd(user, "Eski123!", "YeniSifre1", "YeniSifre1");

    await waitFor(() =>
      expect(changePassword).toHaveBeenCalledWith("Eski123!", "YeniSifre1"),
    );
    expect(
      await screen.findByText("content.settings.passwordUpdated"),
    ).toBeInTheDocument();
    // alanlar temizlendi
    expect(
      (screen.getByLabelText("content.settings.currentPassword") as HTMLInputElement)
        .value,
    ).toBe("");
  });

  it("changePassword backend hatasi (Error) → mesaj gosterilir", async () => {
    changePassword.mockRejectedValue(new Error("mevcut sifre yanlis"));
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.changePassword")).toBeInTheDocument();

    await fillPwd(user, "Eski123!", "YeniSifre1", "YeniSifre1");
    expect(await screen.findByText("mevcut sifre yanlis")).toBeInTheDocument();
  });

  it("changePassword hatasi (Error olmayan) → fallback ceviri", async () => {
    changePassword.mockRejectedValue({ x: 1 });
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.changePassword")).toBeInTheDocument();

    await fillPwd(user, "Eski123!", "YeniSifre1", "YeniSifre1");
    expect(
      await screen.findByText("content.settings.passwordUpdateFailed"),
    ).toBeInTheDocument();
  });
});

// ─── Genel tercihler: USD toggle ─────────────────────────────────────────────

describe("SettingsPage — USD karsiligi toggle", () => {
  it("toggle tiklanir → setShowUsd(true) cagrilir, aria-label degisir", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    const toggle = await screen.findByRole("button", {
      name: "content.settings.showUsdToggleOn",
    });
    await user.click(toggle);

    expect(setShowUsd).toHaveBeenCalledWith(true);
    // aria-label artik "off" varyanti
    expect(
      screen.getByRole("button", { name: "content.settings.showUsdToggleOff" }),
    ).toBeInTheDocument();
  });

  it("baslangic showUsd=true ise toggle off aria-label gosterir", async () => {
    getShowUsd.mockReturnValue(true);
    render(<SettingsPage />);
    expect(
      await screen.findByRole("button", {
        name: "content.settings.showUsdToggleOff",
      }),
    ).toBeInTheDocument();
  });
});

// ─── Dashboard kart gorunurlugu ──────────────────────────────────────────────

describe("SettingsPage — dashboard kart gizleme", () => {
  it("kart toggle → hidden listeye eklenir + localStorage'a yazilir", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.dashboardView")).toBeInTheDocument();

    // "Kripto" kartinin gizle/goster toggle'i (gorunur → hideCardAria)
    const hideBtn = screen.getByRole("button", {
      name: "Kripto content.settings.hideCardAria",
    });
    await user.click(hideBtn);

    // localStorage'a kripto id yazildi
    const stored = JSON.parse(
      localStorage.getItem("kfinans_hidden_cards") ?? "[]",
    );
    expect(stored).toContain("crypto");

    // toggle artik "goster" varyanti (gizli)
    expect(
      screen.getByRole("button", {
        name: "Kripto content.settings.showCardAria",
      }),
    ).toBeInTheDocument();
  });

  it("zaten gizli kart tekrar toggle → listeden cikar", async () => {
    localStorage.setItem("kfinans_hidden_cards", JSON.stringify(["crypto"]));
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("content.settings.dashboardView")).toBeInTheDocument();

    const showBtn = screen.getByRole("button", {
      name: "Kripto content.settings.showCardAria",
    });
    await user.click(showBtn);

    const stored = JSON.parse(
      localStorage.getItem("kfinans_hidden_cards") ?? "[]",
    );
    expect(stored).not.toContain("crypto");
  });
});

// ─── Tehlike bolgesi: hesap silme ────────────────────────────────────────────

describe("SettingsPage — hesap silme", () => {
  it("onay verilir → deleteAccount + clearAuth + login'e yonlendir", async () => {
    deleteAccount.mockResolvedValue({ detail: "ok" });
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(
      await screen.findByRole("button", {
        name: "content.settings.deleteAccountBtn",
      }),
    );

    await waitFor(() => expect(deleteAccount).toHaveBeenCalled());
    expect(clearAuth).toHaveBeenCalled();
    expect(routerReplace).toHaveBeenCalledWith("/login");
  });

  it("onay reddedilir → hicbir sey cagrilmaz", async () => {
    confirmFn.mockResolvedValue(false);
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(
      await screen.findByRole("button", {
        name: "content.settings.deleteAccountBtn",
      }),
    );

    await waitFor(() => expect(confirmFn).toHaveBeenCalled());
    expect(deleteAccount).not.toHaveBeenCalled();
    expect(clearAuth).not.toHaveBeenCalled();
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("deleteAccount hata atsa bile clearAuth + yonlendirme yapilir", async () => {
    deleteAccount.mockRejectedValue(new Error("token gecersiz"));
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(
      await screen.findByRole("button", {
        name: "content.settings.deleteAccountBtn",
      }),
    );

    await waitFor(() => expect(clearAuth).toHaveBeenCalled());
    expect(routerReplace).toHaveBeenCalledWith("/login");
  });
});

// ─── MFA link + geri bildirim linkleri ───────────────────────────────────────

describe("SettingsPage — statik linkler", () => {
  it("MFA ayarlari linki dogru href'e isaret eder", async () => {
    render(<SettingsPage />);
    const link = await screen.findByTestId("mfa-settings-link");
    expect(link).toHaveAttribute("href", "/dashboard/settings/security");
  });

  it("geri bildirim GitHub linkleri render edilir", async () => {
    render(<SettingsPage />);
    const bug = await screen.findByText("content.settings.reportBug");
    const anchor = bug.closest("a");
    expect(anchor).toHaveAttribute(
      "href",
      expect.stringContaining("bug_report.yml"),
    );
  });
});
