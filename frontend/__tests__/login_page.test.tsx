import { describe, expect, it, beforeEach, vi } from "vitest";

// v8 coverage instrumentasyonu altinda her test 3-5sn surebiliyor; default 5sn
// timeout flaky kaliyor. Bu dosya icin timeout'u yukselt (deterministik gecsin).
vi.setConfig({ testTimeout: 30000 });
import { render, screen, waitFor } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";

// userEvent.setup() — per-keystroke delay'i kapat (delay: null). v8 coverage
// instrumentasyonu altinda yavaslama + default async delay birlesince
// etkilesimler findBy* timeout'una takilabiliyor; delay:null deterministik kilar.
const userEvent = {
  setup: () => userEventLib.setup({ delay: null }),
};

// ─── Mock'lar ──────────────────────────────────────────────────────────────
// next/navigation (Next.js 16 App Router) — useRouter().push spy'lanir.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/login",
}));

// i18n — t(key) => key (deterministik assertion; gercek dictionary'e bagimsiz).
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => ({
    t: (k: string) => k,
    locale: "tr",
    setLocale: vi.fn(),
  }),
}));

// lib/api — auth metodlari + setAuth mock'lanir.
const loginMock = vi.fn();
const mfaVerifyMock = vi.fn();
const resendVerificationMock = vi.fn();
const setAuthMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    login: (...a: unknown[]) => loginMock(...a),
    mfaVerify: (...a: unknown[]) => mfaVerifyMock(...a),
    resendVerification: (...a: unknown[]) => resendVerificationMock(...a),
  },
  setAuth: (...a: unknown[]) => setAuthMock(...a),
}));

import LoginPage from "@/app/login/page";

// Yardimci: kimlik bilgisi alanlarini doldur + submit et.
async function fillCredentialsAndSubmit(
  user: ReturnType<typeof userEvent.setup>,
  email = "test@example.com",
  password = "Sifre123!",
) {
  await user.type(screen.getByLabelText("auth.email"), email);
  await user.type(screen.getByLabelText("auth.password"), password);
  // Submit butonu (login formundaki tek "submit" tipli buton).
  const submit = screen.getByRole("button", { name: "auth.login" });
  await user.click(submit);
}

describe("LoginPage — kimlik dogrulama formu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ilk renderda kimlik formu gosterilir (email + password + login butonu)", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("auth.email")).toBeInTheDocument();
    expect(screen.getByLabelText("auth.password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "auth.login" })).toBeInTheDocument();
    // MFA formu henuz yok.
    expect(screen.queryByTestId("mfa-challenge-form")).not.toBeInTheDocument();
    // Register linki kimlik asamasinda gorunur.
    expect(screen.getByRole("link", { name: "auth.register" })).toBeInTheDocument();
  });

  it("sifre goster/gizle butonu input type'ini degistirir", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    const pwd = screen.getByLabelText("auth.password");
    expect(pwd).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "auth.showPassword" }));
    expect(pwd).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "auth.hidePassword" }));
    expect(pwd).toHaveAttribute("type", "password");
  });

  it("basarili login → setAuth cagrilir + /dashboard'a yonlendirir", async () => {
    const user = userEvent.setup();
    loginMock.mockResolvedValue({
      access_token: "acc-1",
      refresh_token: "ref-1",
      token_type: "bearer",
    });
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(loginMock).toHaveBeenCalledWith("test@example.com", "Sifre123!");
    expect(setAuthMock).toHaveBeenCalledWith("acc-1", "ref-1");
  });

  it("login token donmezse (access_token yok) hata gosterilir, yonlendirme yok", async () => {
    const user = userEvent.setup();
    // mfa_required false + access_token yok → throw loginFailed.
    loginMock.mockResolvedValue({ token_type: "bearer" });
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("auth.loginFailed");
    expect(pushMock).not.toHaveBeenCalled();
    expect(setAuthMock).not.toHaveBeenCalled();
  });

  it("yanlis kimlik → api hata firlatir → role=alert mesaji gosterilir", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue(new Error("E-posta veya parola hatalı"));
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("E-posta veya parola hatalı");
    expect(pushMock).not.toHaveBeenCalled();
    // Dogrulama akisi tetiklenmez (mesaj "dogrulan/verif" icermez).
    expect(
      screen.queryByRole("button", { name: "auth.resendVerification" }),
    ).not.toBeInTheDocument();
  });

  it("login Error olmayan deger firlatirsa loginFailed fallback mesaji", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue("string-hata");
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("auth.loginFailed");
  });
});

describe("LoginPage — e-posta dogrulama (resend) akisi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("403 'doğrulanmadı' hatasi → resend butonu gorunur", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue(new Error("E-posta adresiniz henüz doğrulanmadı"));
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    expect(
      await screen.findByRole("button", { name: "auth.resendVerification" }),
    ).toBeInTheDocument();
  });

  it("resend basarili → resendVerification cagrilir + basari notice gosterilir", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue(new Error("Hesabınız doğrulanmadı, lütfen e-postanızı kontrol edin"));
    resendVerificationMock.mockResolvedValue({ detail: "ok" });
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user, "kullanici@ornek.com", "Parola1!");

    const resendBtn = await screen.findByRole("button", { name: "auth.resendVerification" });
    await user.click(resendBtn);

    await waitFor(() =>
      expect(resendVerificationMock).toHaveBeenCalledWith("kullanici@ornek.com"),
    );
    expect(await screen.findByText("auth.resendSuccess")).toBeInTheDocument();
  });

  it("resend hata firlatirsa hata mesaji notice'da gosterilir", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue(new Error("hesap doğrulanmadı"));
    resendVerificationMock.mockRejectedValue(new Error("Çok fazla istek"));
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    const resendBtn = await screen.findByRole("button", { name: "auth.resendVerification" });
    await user.click(resendBtn);

    expect(await screen.findByText("Çok fazla istek")).toBeInTheDocument();
  });

  it("verif (ingilizce) iceren hata da resend akisini tetikler", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue(new Error("Email not verified yet"));
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    expect(
      await screen.findByRole("button", { name: "auth.resendVerification" }),
    ).toBeInTheDocument();
  });
});

describe("LoginPage — MFA challenge akisi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("login mfa_required + pre_mfa_token donerse MFA formuna gecilir", async () => {
    const user = userEvent.setup();
    loginMock.mockResolvedValue({ mfa_required: true, pre_mfa_token: "pre-1" });
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);

    expect(await screen.findByTestId("mfa-challenge-form")).toBeInTheDocument();
    expect(screen.getByTestId("mfa-login-code")).toBeInTheDocument();
    // Kimlik formu artik gorunmez.
    expect(screen.queryByLabelText("auth.email")).not.toBeInTheDocument();
    // setAuth henuz cagrilmadi (MFA dogrulamasi bekleniyor).
    expect(setAuthMock).not.toHaveBeenCalled();
  });

  async function reachMfaStage(user: ReturnType<typeof userEvent.setup>) {
    loginMock.mockResolvedValue({ mfa_required: true, pre_mfa_token: "pre-1" });
    render(<LoginPage />);
    await fillCredentialsAndSubmit(user);
    await screen.findByTestId("mfa-challenge-form");
  }

  it("gecerli TOTP kodu → mfaVerify cagrilir + setAuth + /dashboard", async () => {
    const user = userEvent.setup();
    mfaVerifyMock.mockResolvedValue({
      access_token: "macc",
      refresh_token: "mref",
      token_type: "bearer",
    });
    await reachMfaStage(user);

    await user.type(screen.getByTestId("mfa-login-code"), "123456");
    await user.click(screen.getByTestId("mfa-login-submit"));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(mfaVerifyMock).toHaveBeenCalledWith("pre-1", { totp_code: "123456" });
    expect(setAuthMock).toHaveBeenCalledWith("macc", "mref");
  });

  it("TOTP input \\D karakterleri filtreler ve 6 haneye kirpar", async () => {
    const user = userEvent.setup();
    await reachMfaStage(user);

    const input = screen.getByTestId("mfa-login-code") as HTMLInputElement;
    await user.type(input, "12a3-45 6789");
    // \D temizlenir + 6 haneye kirpilir.
    expect(input.value).toBe("123456");
  });

  it("eksik/gecersiz TOTP kodu → mfaVerify cagrilmaz, invalidCode hatasi", async () => {
    const user = userEvent.setup();
    await reachMfaStage(user);

    // 6 haneden kisa kod gir, submit et.
    await user.type(screen.getByTestId("mfa-login-code"), "123");
    await user.click(screen.getByTestId("mfa-login-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent("mfa.invalidCode");
    expect(mfaVerifyMock).not.toHaveBeenCalled();
  });

  it("mfaVerify reddederse hata mesaji gosterilir, yonlendirme yok", async () => {
    const user = userEvent.setup();
    mfaVerifyMock.mockRejectedValue(new Error("Geçersiz doğrulama kodu"));
    await reachMfaStage(user);

    await user.type(screen.getByTestId("mfa-login-code"), "654321");
    await user.click(screen.getByTestId("mfa-login-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Geçersiz doğrulama kodu");
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("recovery moduna gecis → recovery input gorunur, gecerli kod ile verify", async () => {
    const user = userEvent.setup();
    mfaVerifyMock.mockResolvedValue({
      access_token: "racc",
      refresh_token: "rref",
      token_type: "bearer",
    });
    await reachMfaStage(user);

    await user.click(screen.getByTestId("mfa-login-toggle-mode"));
    const recovery = screen.getByTestId("mfa-login-recovery");
    expect(recovery).toBeInTheDocument();
    // TOTP input artik yok.
    expect(screen.queryByTestId("mfa-login-code")).not.toBeInTheDocument();

    await user.type(recovery, "abcd-efgh-1234");
    await user.click(screen.getByTestId("mfa-login-submit"));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(mfaVerifyMock).toHaveBeenCalledWith("pre-1", { recovery_code: "abcd-efgh-1234" });
  });

  it("recovery modunda 8 karakterden kisa kod → invalidRecovery hatasi", async () => {
    const user = userEvent.setup();
    await reachMfaStage(user);

    await user.click(screen.getByTestId("mfa-login-toggle-mode"));
    await user.type(screen.getByTestId("mfa-login-recovery"), "kisa");
    await user.click(screen.getByTestId("mfa-login-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent("mfa.invalidRecovery");
    expect(mfaVerifyMock).not.toHaveBeenCalled();
  });

  it("toggle iki kez basinca tekrar TOTP moduna doner", async () => {
    const user = userEvent.setup();
    await reachMfaStage(user);

    const toggle = screen.getByTestId("mfa-login-toggle-mode");
    await user.click(toggle); // → recovery
    expect(screen.getByTestId("mfa-login-recovery")).toBeInTheDocument();
    await user.click(toggle); // → totp
    expect(screen.getByTestId("mfa-login-code")).toBeInTheDocument();
  });

  it("iptal (cancel) → kimlik formuna geri doner", async () => {
    const user = userEvent.setup();
    await reachMfaStage(user);

    await user.click(screen.getByRole("button", { name: "common.cancel" }));
    expect(screen.getByLabelText("auth.email")).toBeInTheDocument();
    expect(screen.queryByTestId("mfa-challenge-form")).not.toBeInTheDocument();
  });
});
