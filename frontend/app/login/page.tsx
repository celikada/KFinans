"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { api, setAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api.login(email, password);
      setAuth(data.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Giriş başarısız");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <div className="flex justify-center mb-6">
          <Image src="/images/kfinans-logo.png" alt="KFinans" width={140} height={148} priority />
        </div>
        <p className="text-sm text-gray-500 mb-8 text-center">Portföyünüze giriş yapın</p>

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
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">Şifre</label>
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {showPassword ? "Gizle" : "Göster"}
              </button>
            </div>
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
          </button>
        </form>

        <p className="mt-4 text-xs text-gray-400 text-center">
          Hesabın yok mu?{" "}
          <Link href="/register" className="text-blue-600 hover:text-blue-700 font-medium">
            Kayıt ol
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
