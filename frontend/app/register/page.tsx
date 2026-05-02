"use client";
import { useState, FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";

type RiskProfile = "conservative" | "balanced" | "aggressive";

const RISK_LABELS: Record<RiskProfile, string> = {
  conservative: "Tutucu (düşük risk)",
  balanced: "Dengeli",
  aggressive: "Atak (yüksek risk)",
};

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("balanced");
  const [kvkkRead, setKvkkRead] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [overseasConsent, setOverseasConsent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendNotice, setResendNotice] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Şifre en az 8 karakter olmalı");
      return;
    }
    if (password !== passwordConfirm) {
      setError("Şifreler eşleşmiyor");
      return;
    }
    if (!kvkkRead) {
      setError("KVKK Aydınlatma Metni'ni okuduğunuzu onaylamanız gerekir");
      return;
    }
    if (!termsAccepted) {
      setError("Kullanım Şartları ve Gizlilik Politikası'nı kabul etmeniz gerekir");
      return;
    }
    if (!overseasConsent) {
      setError("Yurt dışı veri aktarımı için açık rıza vermeniz gerekir");
      return;
    }

    setLoading(true);
    try {
      const data = await api.register(email, password, riskProfile);
      setSuccess(true);
      setEmailSent(data.verification_email_sent);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResending(true);
    setResendNotice("");
    try {
      await api.resendVerification(email);
      setResendNotice("Yeni doğrulama bağlantısı gönderildi.");
    } catch (err) {
      setResendNotice(err instanceof Error ? err.message : "Gönderim başarısız");
    } finally {
      setResending(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
          <div className="flex justify-center mb-6">
            <Image src="/images/kfinans-logo.png" alt="KFinans" width={140} height={148} priority />
          </div>
          <h2 className="text-base font-semibold text-gray-900 mb-2">
            {emailSent ? "E-postanı kontrol et" : "Kayıt tamamlandı"}
          </h2>
          <p className="text-sm text-gray-500 mb-6">
            {emailSent
              ? `${email} adresine doğrulama bağlantısı gönderdik. Hesabını aktifleştirmek için bağlantıya tıklaman yeterli.`
              : "Hesabın oluşturuldu ancak doğrulama e-postası şu an gönderilemedi. Aşağıdaki butonla tekrar dene."}
          </p>

          {resendNotice && (
            <p className="text-xs text-gray-500 bg-gray-50 px-3 py-2 rounded-lg mb-4">{resendNotice}</p>
          )}

          <button
            onClick={handleResend}
            disabled={resending}
            className="w-full py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors mb-3"
          >
            {resending ? "Gönderiliyor..." : "Doğrulama e-postasını yeniden gönder"}
          </button>

          <Link
            href="/login"
            className="block text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Giriş sayfasına dön
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 py-8">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <div className="flex justify-center mb-6">
          <Image src="/images/kfinans-logo.png" alt="KFinans" width={140} height={148} priority />
        </div>
        <p className="text-sm text-gray-500 mb-8 text-center">Hesap oluştur</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">E-posta</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="ornek@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Şifre</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="En az 8 karakter"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Şifre (tekrar)</label>
            <input
              type="password"
              required
              minLength={8}
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Risk Profili</label>
            <select
              value={riskProfile}
              onChange={(e) => setRiskProfile(e.target.value as RiskProfile)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {(Object.keys(RISK_LABELS) as RiskProfile[]).map((key) => (
                <option key={key} value={key}>{RISK_LABELS[key]}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2 pt-1">
            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={kvkkRead}
                onChange={(e) => setKvkkRead(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>
                <Link href="/legal/kvkk" target="_blank" className="text-blue-600 hover:underline">
                  KVKK Aydınlatma Metni
                </Link>
                &apos;ni okudum, anladım.
              </span>
            </label>

            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>
                <Link href="/legal/terms" target="_blank" className="text-blue-600 hover:underline">
                  Kullanım Şartları
                </Link>
                {" "}ve{" "}
                <Link href="/legal/privacy" target="_blank" className="text-blue-600 hover:underline">
                  Gizlilik Politikası
                </Link>
                &apos;nı kabul ediyorum.
              </span>
            </label>

            <label className="flex items-start gap-2 text-xs text-gray-600 leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={overseasConsent}
                onChange={(e) => setOverseasConsent(e.target.checked)}
                className="mt-0.5 accent-blue-600"
              />
              <span>
                E-posta gönderimi (Resend, ABD) ve AI tavsiye üretimi (Anthropic, ABD) için
                kişisel verilerimin <strong>yurt dışına aktarılmasına</strong> KVKK m.9 kapsamında
                <strong> açık rıza</strong> veriyorum.
              </span>
            </label>
          </div>

          {error && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Kayıt yapılıyor..." : "Kayıt Ol"}
          </button>
        </form>

        <p className="mt-4 text-xs text-gray-400 text-center">
          Zaten hesabın var mı?{" "}
          <Link href="/login" className="text-blue-600 hover:text-blue-700 font-medium">
            Giriş yap
          </Link>
        </p>
      </div>

      <div className="mt-8 flex flex-col items-center gap-2">
        <p className="text-xs text-gray-400">Bir</p>
        <Image src="/images/mayotek-logo.png" alt="Mayotek" width={90} height={30} />
        <p className="text-xs text-gray-400">ürünüdür</p>
      </div>

      <div className="mt-4 flex gap-3 text-xs text-gray-400">
        <Link href="/legal/kvkk" className="hover:text-gray-600">KVKK</Link>
        <Link href="/legal/privacy" className="hover:text-gray-600">Gizlilik</Link>
        <Link href="/legal/terms" className="hover:text-gray-600">Şartlar</Link>
        <Link href="/legal/cookies" className="hover:text-gray-600">Çerezler</Link>
      </div>
    </div>
  );
}
