import type { MetadataRoute } from "next";

/**
 * Web App Manifest (PWA). Served at /manifest.webmanifest.
 *
 * Enables "Add to Home Screen" with a native-like standalone experience on
 * iOS Safari and Android/Chromium. Brand blue (#1D4ED8) matches the KFinans
 * logo; start_url points straight to the dashboard.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "KFinans",
    short_name: "KFinans",
    description:
      "Kişisel yatırım portföyü: kripto, hisse, fon, cüzdan ve finans takibi tek ekranda.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    lang: "tr",
    dir: "ltr",
    background_color: "#ffffff",
    theme_color: "#1D4ED8",
    categories: ["finance", "productivity"],
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
