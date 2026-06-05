import { describe, expect, it } from "vitest";

import manifest from "@/app/manifest";

describe("PWA web app manifest", () => {
  const m = manifest();

  it("standalone, dashboard'a açılan kurulabilir uygulama tanımlar", () => {
    expect(m.name).toBe("KFinans");
    expect(m.short_name).toBe("KFinans");
    expect(m.display).toBe("standalone");
    expect(m.start_url).toBe("/dashboard");
    expect(m.scope).toBe("/");
    expect(m.theme_color).toBe("#1D4ED8");
    expect(m.lang).toBe("tr");
  });

  it("192/512 düz + 512 maskable ikonları içerir", () => {
    const icons = m.icons ?? [];
    const sizes = icons.map((i) => i.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");

    const maskable = icons.find((i) => i.purpose === "maskable");
    expect(maskable).toBeDefined();
    expect(maskable?.sizes).toBe("512x512");
    expect(maskable?.src).toBe("/icons/maskable-512.png");

    // Tüm ikonlar PNG ve /icons/ altından servis edilir.
    for (const icon of icons) {
      expect(icon.type).toBe("image/png");
      expect(icon.src.startsWith("/icons/")).toBe(true);
    }
  });
});
