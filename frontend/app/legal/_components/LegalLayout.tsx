"use client";
import { ReactNode } from "react";
import Link from "next/link";
import { MayotekLogo } from "@/app/_components/Logos";

interface LegalLayoutProps {
  readonly title: string;
  readonly lastUpdated: string;
  readonly children: ReactNode;
}

export function LegalLayout({ title, lastUpdated, children }: LegalLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <Link href="/" className="text-gray-400 hover:text-gray-600 text-sm">
          ← Ana sayfa
        </Link>
        <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <p className="text-xs text-gray-400 mb-6">Son güncelleme: {lastUpdated}</p>
        <article className="prose prose-sm max-w-none text-gray-700 space-y-4">
          {children}
        </article>

        <nav className="mt-12 pt-6 border-t border-gray-200 flex flex-wrap gap-4 text-xs">
          <LegalLink href="/legal/kvkk" label="KVKK Aydınlatma" />
          <LegalLink href="/legal/privacy" label="Gizlilik Politikası" />
          <LegalLink href="/legal/terms" label="Kullanım Şartları" />
          <LegalLink href="/legal/cookies" label="Çerez Politikası" />
        </nav>
      </main>

      <footer className="mt-auto py-6 flex justify-center items-center gap-2 border-t border-gray-100">
        <span className="text-xs text-gray-300">Bir</span>
        <MayotekLogo />
        <span className="text-xs text-gray-300">ürünüdür</span>
      </footer>
    </div>
  );
}

function LegalLink({ href, label }: { readonly href: string; readonly label: string }) {
  return (
    <Link href={href} className="text-blue-600 hover:text-blue-700 hover:underline">
      {label}
    </Link>
  );
}

export function LegalSection({ title, children }: { readonly title: string; readonly children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold text-gray-900 mt-6">{title}</h2>
      <div className="text-sm text-gray-700 leading-relaxed space-y-2">{children}</div>
    </section>
  );
}
