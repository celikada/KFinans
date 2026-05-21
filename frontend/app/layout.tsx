import type { Metadata } from "next";
import { headers } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { I18nProvider } from "./_i18n/I18nProvider";
import { ConfirmDialogProvider } from "./_components/ConfirmDialog";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KFinans",
  description: "Kişisel yatırım portföyü",
  icons: { icon: "/images/kfinans-logo.png" },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // CSP nonce — proxy.ts her request icin yeniden uretir; Next.js 16'da
  // `<script>` etiketlerine bu nonce'u tasiyarak 'unsafe-inline' kaldirilir.
  const hdrs = await headers();
  const nonce = hdrs.get("x-nonce") ?? undefined;

  return (
    <html
      lang="tr"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* Nonce'u tum next/script ve inline scriptlerde aktive eden meta isaret.
            Next.js production build, runtime'i bu nonce ile imzalar. */}
        {nonce && <meta property="csp-nonce" content={nonce} />}
      </head>
      <body className="min-h-full flex flex-col">
        <I18nProvider>
          <ConfirmDialogProvider>{children}</ConfirmDialogProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
