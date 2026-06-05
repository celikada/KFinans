import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const i18nStub = { t: (key: string) => key, locale: "tr", setLocale: vi.fn() };
vi.mock("@/app/_i18n/I18nProvider", () => ({ useTranslation: () => i18nStub }));

import OfflinePage from "@/app/offline/page";

describe("OfflinePage (PWA çevrimdışı fallback)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("başlık, açıklama ve yeniden dene butonu gösterir", () => {
    render(<OfflinePage />);
    expect(screen.getByText("pages.offline.title")).toBeInTheDocument();
    expect(screen.getByText("pages.offline.description")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "pages.offline.retry" }),
    ).toBeInTheDocument();
  });

  it("yeniden dene butonu sayfayı yeniden yükler", async () => {
    const reload = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload },
    });

    render(<OfflinePage />);
    await userEvent.click(
      screen.getByRole("button", { name: "pages.offline.retry" }),
    );
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
