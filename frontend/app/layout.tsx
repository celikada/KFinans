import type { Metadata } from "next";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="tr"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <I18nProvider>
          <ConfirmDialogProvider>{children}</ConfirmDialogProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
