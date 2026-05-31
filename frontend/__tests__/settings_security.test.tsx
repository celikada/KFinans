import type { ReactNode } from "react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ─── Mocks ──────────────────────────────────────────────────────────────────

const mfaStatus = vi.fn();
const mfaSetup = vi.fn();
const mfaEnable = vi.fn();
const mfaDisable = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    mfaStatus: (...a: unknown[]) => mfaStatus(...a),
    mfaSetup: (...a: unknown[]) => mfaSetup(...a),
    mfaEnable: (...a: unknown[]) => mfaEnable(...a),
    mfaDisable: (...a: unknown[]) => mfaDisable(...a),
  },
}));

const routerReplace = vi.fn();
// STABIL router objesi — her render'da yeni referans dönerse useEffect([router])
// sonsuz tekrar çalışır ve mfaStatus state'i ezer.
const routerStub = { replace: routerReplace, push: vi.fn(), prefetch: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => routerStub,
}));

// next/link → basit anchor
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

// PageHeader → sade başlık (back prop'u önemsiz)
vi.mock("@/app/_components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}));

// useTranslation → key'i geri döner (deterministik, dictionary'ye bağımlı değil)
vi.mock("@/app/_i18n/I18nProvider", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "tr",
    setLocale: vi.fn(),
  }),
}));

// Import AFTER mocks
import MfaSecurityPage from "@/app/dashboard/settings/security/page";

const SETUP_RESPONSE = {
  secret_base32: "ABCDEFGHIJKLMNOP",
  otpauth_url: "otpauth://totp/KFinans:test?secret=ABCDEFGHIJKLMNOP",
  qr_png_base64: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
};

const RECOVERY_CODES = [
  "AAAA-1111",
  "BBBB-2222",
  "CCCC-3333",
  "DDDD-4444",
  "EEEE-5555",
];

beforeEach(() => {
  mfaStatus.mockReset();
  mfaSetup.mockReset();
  mfaEnable.mockReset();
  mfaDisable.mockReset();
  routerReplace.mockReset();
  // Güvenli varsayılan: aksi belirtilmezse MFA kapalı statüsü döner.
  mfaStatus.mockResolvedValue({ mfa_enabled: false });
});

// ─── Loading + status ─────────────────────────────────────────────────────

describe("MfaSecurityPage — yükleme ve durum", () => {
  it("yüklenirken loading metni gösterir, sonra durumu çeker", async () => {
    let resolveStatus!: (v: { mfa_enabled: boolean }) => void;
    const pending = new Promise<{ mfa_enabled: boolean }>((res) => {
      resolveStatus = res;
    });
    mfaStatus.mockImplementation(() => pending);

    render(<MfaSecurityPage />);
    // loading state
    expect(screen.getByText("common.loading")).toBeInTheDocument();

    resolveStatus({ mfa_enabled: false });

    await waitFor(() =>
      expect(screen.queryByText("common.loading")).not.toBeInTheDocument(),
    );
    expect(mfaStatus).toHaveBeenCalledTimes(1);
  });

  it("MFA kapalı → inactive durum + setup butonu görünür", async () => {
    mfaStatus.mockResolvedValue({ mfa_enabled: false });
    render(<MfaSecurityPage />);

    await screen.findByTestId("mfa-setup-btn");
    expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent(
      "mfa.statusInactive",
    );
    expect(screen.queryByTestId("mfa-disable-btn")).not.toBeInTheDocument();
  });

  it("MFA açık → active durum + disable butonu görünür", async () => {
    mfaStatus.mockResolvedValue({ mfa_enabled: true });
    render(<MfaSecurityPage />);

    await screen.findByTestId("mfa-disable-btn");
    expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent(
      "mfa.statusActive",
    );
    expect(screen.queryByTestId("mfa-setup-btn")).not.toBeInTheDocument();
  });

  it("status 401 hatası → login'e yönlendirir", async () => {
    mfaStatus.mockRejectedValue(new Error("Request failed 401 Unauthorized"));
    render(<MfaSecurityPage />);

    await waitFor(() =>
      expect(routerReplace).toHaveBeenCalledWith("/login"),
    );
  });

  it("status 401 dışı hata → yönlendirme yok, loading biter", async () => {
    mfaStatus.mockRejectedValue(new Error("500 server error"));
    render(<MfaSecurityPage />);

    await screen.findByTestId("mfa-setup-btn");
    expect(routerReplace).not.toHaveBeenCalled();
  });
});

// ─── Setup + enable akışı ──────────────────────────────────────────────────

describe("MfaSecurityPage — kurulum (setup) + etkinleştirme (enable)", () => {
  beforeEach(() => {
    mfaStatus.mockResolvedValue({ mfa_enabled: false });
  });

  it("setup başlatma → QR, secret ve kod formu gösterilir", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));

    const panel = await screen.findByTestId("mfa-setup-panel");
    expect(within(panel).getByTestId("mfa-secret")).toHaveTextContent(
      "ABCDEFGHIJKLMNOP",
    );
    const img = within(panel).getByTestId("mfa-qr-image") as HTMLImageElement;
    expect(img.src).toContain("data:image/png;base64,");
    expect(img.src).toContain(SETUP_RESPONSE.qr_png_base64);
  });

  it("setup hatası → error mesajı (alert) gösterilir", async () => {
    mfaSetup.mockRejectedValue(new Error("setup patladı"));
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("setup patladı");
    expect(screen.queryByTestId("mfa-setup-panel")).not.toBeInTheDocument();
  });

  it("setup hatası (Error olmayan) → fallback çeviri mesajı", async () => {
    mfaSetup.mockRejectedValue("string hata");
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("mfa.setupFailed");
  });

  it("QR zaten data: URL ise prefix eklenmez (qrSrc branch)", async () => {
    const dataUrl = "data:image/png;base64,QUJD";
    mfaSetup.mockResolvedValue({ ...SETUP_RESPONSE, qr_png_base64: dataUrl });
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    const img = (await screen.findByTestId("mfa-qr-image")) as HTMLImageElement;
    // Çift "data:" prefix'i olmamalı — değer aynen korunur.
    expect(img.src).toBe(dataUrl);
  });

  it("geçersiz kod (6 hane değil) → enable çağrılmaz, invalidCode hatası", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");

    // 3 hane gir (input zaten non-digit'i filtreler, ama uzunluk yetersiz)
    await user.type(screen.getByTestId("mfa-setup-code"), "123");
    await user.click(screen.getByTestId("mfa-enable-btn"));

    expect(mfaEnable).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "mfa.invalidCode",
    );
  });

  it("input non-digit karakterleri filtreler ve 6 haneye keser", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");

    const input = screen.getByTestId("mfa-setup-code") as HTMLInputElement;
    await user.type(input, "12ab34cd5678");
    expect(input.value).toBe("123456");
  });

  it("geçerli 6 haneli kod → enable çağrılır, recovery panel + active durum", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    mfaEnable.mockResolvedValue({ recovery_codes: RECOVERY_CODES });
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");

    fireEvent.change(screen.getByTestId("mfa-setup-code"), {
      target: { value: "654321" },
    });
    await user.click(screen.getByTestId("mfa-enable-btn"));

    const recoveryPanel = await screen.findByTestId("mfa-recovery-panel");
    expect(mfaEnable).toHaveBeenCalledWith("654321");

    const list = within(recoveryPanel).getByTestId("mfa-recovery-list");
    expect(within(list).getAllByRole("listitem")).toHaveLength(
      RECOVERY_CODES.length,
    );
    RECOVERY_CODES.forEach((code) =>
      expect(within(list).getByText(code)).toBeInTheDocument(),
    );

    // Durum rozeti artık aktif
    await waitFor(() =>
      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent(
        "mfa.statusActive",
      ),
    );
    // Setup paneli kapandı
    expect(screen.queryByTestId("mfa-setup-panel")).not.toBeInTheDocument();
  });

  it("enable backend hatası → error mesajı, recovery paneli açılmaz", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    mfaEnable.mockRejectedValue(new Error("kod yanlış"));
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");

    fireEvent.change(screen.getByTestId("mfa-setup-code"), {
      target: { value: "111111" },
    });
    await user.click(screen.getByTestId("mfa-enable-btn"));

    expect(await screen.findByRole("alert")).toHaveTextContent("kod yanlış");
    expect(screen.queryByTestId("mfa-recovery-panel")).not.toBeInTheDocument();
  });

  it("enable hatası (Error olmayan) → invalidCode fallback", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    mfaEnable.mockRejectedValue({ not: "an error" });
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");

    fireEvent.change(screen.getByTestId("mfa-setup-code"), {
      target: { value: "222222" },
    });
    await user.click(screen.getByTestId("mfa-enable-btn"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "mfa.invalidCode",
    );
  });

  it("setup iptal → panel kapanır, idle'a döner", async () => {
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");

    // Setup formundaki cancel butonu
    await user.click(screen.getByRole("button", { name: "common.cancel" }));

    await waitFor(() =>
      expect(screen.queryByTestId("mfa-setup-panel")).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("mfa-setup-btn")).toBeInTheDocument();
  });
});

// ─── Recovery codes: kopyala + tamamla ─────────────────────────────────────

describe("MfaSecurityPage — recovery codes", () => {
  async function reachRecovery() {
    mfaStatus.mockResolvedValue({ mfa_enabled: false });
    mfaSetup.mockResolvedValue(SETUP_RESPONSE);
    mfaEnable.mockResolvedValue({ recovery_codes: RECOVERY_CODES });
    const user = userEvent.setup();
    render(<MfaSecurityPage />);
    await user.click(await screen.findByTestId("mfa-setup-btn"));
    await screen.findByTestId("mfa-setup-panel");
    fireEvent.change(screen.getByTestId("mfa-setup-code"), {
      target: { value: "654321" },
    });
    await user.click(screen.getByTestId("mfa-enable-btn"));
    await screen.findByTestId("mfa-recovery-panel");
    return user;
  }

  it("kopyala → clipboard.writeText kodları newline ile yazar", async () => {
    const user = await reachRecovery();
    // NOT: userEvent.setup() kendi clipboard stub'unu kurar; bizim mock'u
    // setup'tan SONRA tanimlamali (aksi halde ezilir).
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    await user.click(screen.getByRole("button", { name: "mfa.copyCodes" }));

    expect(writeText).toHaveBeenCalledWith(RECOVERY_CODES.join("\n"));
  });

  it("clipboard fırlatırsa → çökmez (best-effort catch)", async () => {
    const user = await reachRecovery();
    const writeText = vi.fn(() => {
      throw new Error("clipboard yok");
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    await user.click(screen.getByRole("button", { name: "mfa.copyCodes" }));
    // panel hâlâ ayakta
    expect(screen.getByTestId("mfa-recovery-panel")).toBeInTheDocument();
  });

  it("'kaydettim' → recovery paneli kapanır, başarı info mesajı", async () => {
    const user = await reachRecovery();

    await user.click(screen.getByTestId("mfa-recovery-saved-btn"));

    await waitFor(() =>
      expect(
        screen.queryByTestId("mfa-recovery-panel"),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText("mfa.enabledOk")).toBeInTheDocument();
  });
});

// ─── Disable akışı ─────────────────────────────────────────────────────────

describe("MfaSecurityPage — devre dışı bırakma (disable)", () => {
  beforeEach(() => {
    mfaStatus.mockResolvedValue({ mfa_enabled: true });
  });

  it("disable formu açılır ve iptal edilebilir", async () => {
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-disable-btn"));
    expect(screen.getByTestId("mfa-disable-code")).toBeInTheDocument();
    // disable butonu (durum kartındaki) gizlendi
    expect(screen.queryByTestId("mfa-disable-btn")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "common.cancel" }));
    await waitFor(() =>
      expect(
        screen.queryByTestId("mfa-disable-code"),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("mfa-disable-btn")).toBeInTheDocument();
  });

  it("geçersiz kod → mfaDisable çağrılmaz, invalidCode hatası", async () => {
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-disable-btn"));
    await user.type(screen.getByTestId("mfa-disable-code"), "12");
    await user.click(screen.getByTestId("mfa-disable-confirm-btn"));

    expect(mfaDisable).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "mfa.invalidCode",
    );
  });

  it("geçerli kod → mfaDisable çağrılır, durum inactive + info mesajı", async () => {
    mfaDisable.mockResolvedValue({ ok: true });
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-disable-btn"));
    fireEvent.change(screen.getByTestId("mfa-disable-code"), {
      target: { value: "999888" },
    });
    await user.click(screen.getByTestId("mfa-disable-confirm-btn"));

    await waitFor(() => expect(mfaDisable).toHaveBeenCalledWith("999888"));
    await waitFor(() =>
      expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent(
        "mfa.statusInactive",
      ),
    );
    expect(screen.getByText("mfa.disabledOk")).toBeInTheDocument();
    // setup butonu yeniden görünür (artık disabled)
    expect(screen.getByTestId("mfa-setup-btn")).toBeInTheDocument();
  });

  it("disable backend hatası → error mesajı, MFA açık kalır", async () => {
    mfaDisable.mockRejectedValue(new Error("disable reddedildi"));
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-disable-btn"));
    fireEvent.change(screen.getByTestId("mfa-disable-code"), {
      target: { value: "777666" },
    });
    await user.click(screen.getByTestId("mfa-disable-confirm-btn"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "disable reddedildi",
    );
    expect(screen.getByTestId("mfa-status-badge")).toHaveTextContent(
      "mfa.statusActive",
    );
  });

  it("disable hatası (Error olmayan) → invalidCode fallback", async () => {
    mfaDisable.mockRejectedValue(42);
    const user = userEvent.setup();
    render(<MfaSecurityPage />);

    await user.click(await screen.findByTestId("mfa-disable-btn"));
    fireEvent.change(screen.getByTestId("mfa-disable-code"), {
      target: { value: "555444" },
    });
    await user.click(screen.getByTestId("mfa-disable-confirm-btn"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "mfa.invalidCode",
    );
  });
});
