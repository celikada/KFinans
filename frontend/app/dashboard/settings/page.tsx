"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearAuth, RISK_PROFILE_LABELS, UserMeDTO } from "@/lib/api";
import { PageHeader } from "@/app/_components/PageHeader";
import { INPUT_CLS, fmtDate, DASHBOARD_CARDS, DASHBOARD_GROUPS, DashboardCardId, getHiddenCards, saveHiddenCards } from "@/lib/format";
import { getShowUsd, setShowUsd } from "@/app/_components/TLValue";

const RISK_OPTIONS: Array<{ key: "conservative" | "balanced" | "aggressive"; label: string }> = [
  { key: "conservative", label: RISK_PROFILE_LABELS.conservative },
  { key: "balanced",     label: RISK_PROFILE_LABELS.balanced },
  { key: "aggressive",  label: RISK_PROFILE_LABELS.aggressive },
];

const CARD_CLS = "bg-white rounded-2xl border border-gray-100 shadow-sm p-6";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser]       = useState<UserMeDTO | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);

  // Risk profili
  const [selectedRisk, setSelectedRisk] = useState<"conservative" | "balanced" | "aggressive">("balanced");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg]       = useState("");
  const [profileError, setProfileError]   = useState("");

  // Dashboard kart görünürlüğü
  const [hiddenCards, setHiddenCards] = useState<DashboardCardId[]>([]);
  // Genel: USD karşılığı göster
  const [showUsd, setShowUsdState] = useState(false);

  useEffect(() => {
    setHiddenCards(getHiddenCards());
    setShowUsdState(getShowUsd());
  }, []);

  // Şifre değiştir
  const [curPwd, setCurPwd]     = useState("");
  const [newPwd, setNewPwd]     = useState("");
  const [newPwd2, setNewPwd2]   = useState("");
  const [pwdSaving, setPwdSaving] = useState(false);
  const [pwdMsg, setPwdMsg]       = useState("");
  const [pwdError, setPwdError]   = useState("");

  useEffect(() => {
    if (!localStorage.getItem("access_token")) { router.replace("/login"); return; }
    api.getMe()
      .then((data) => {
        setUser(data);
        setSelectedRisk(data.risk_profile);
      })
      .catch((err: Error) => {
        if (err.message.includes("401")) router.replace("/login");
      })
      .finally(() => setLoadingUser(false));
  }, [router]);

  async function handleProfileSave() {
    setProfileMsg("");
    setProfileError("");
    setProfileSaving(true);
    try {
      const updated = await api.updateProfile(selectedRisk);
      setUser(updated);
      setProfileMsg("Profil güncellendi");
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Kaydedilemedi");
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordChange() {
    setPwdMsg("");
    setPwdError("");
    if (newPwd !== newPwd2) {
      setPwdError("Yeni şifreler eşleşmiyor");
      return;
    }
    if (newPwd.length < 8) {
      setPwdError("Yeni şifre en az 8 karakter olmalı");
      return;
    }
    setPwdSaving(true);
    try {
      await api.changePassword(curPwd, newPwd);
      setPwdMsg("Şifre güncellendi");
      setCurPwd("");
      setNewPwd("");
      setNewPwd2("");
    } catch (err) {
      setPwdError(err instanceof Error ? err.message : "Güncellenemedi");
    } finally {
      setPwdSaving(false);
    }
  }

  async function handleDeleteAccount() {
    const confirmed = globalThis.confirm("Hesabınızı silmek istediğinizden emin misiniz?");
    if (!confirmed) return;
    try {
      await api.deleteAccount();
    } catch {
      // Soft-delete başarılı olsa bile token'lar geçersiz sayılır; devam et
    }
    clearAuth();
    router.replace("/login");
  }

  if (loadingUser) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PageHeader title="Ayarlar" />
        <p className="text-sm text-gray-400 text-center py-16">Yükleniyor...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader title="Ayarlar" />

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">

        {/* Bölüm 1: Hesap Bilgileri */}
        <section className={CARD_CLS}>
          <h2 className="text-base font-semibold text-gray-900 mb-4">Hesap Bilgileri</h2>
          <div className="space-y-3">
            <div>
              <label htmlFor="s-email" className="block text-xs text-gray-500 mb-1">E-posta</label>
              <input
                id="s-email"
                type="text"
                readOnly
                value={user?.email ?? ""}
                className={`${INPUT_CLS} w-full bg-gray-50 text-gray-500 cursor-default`}
              />
            </div>
            <div>
              <label htmlFor="s-joined" className="block text-xs text-gray-500 mb-1">Üyelik tarihi</label>
              <input
                id="s-joined"
                type="text"
                readOnly
                value={
                  user?.created_at
                    ? fmtDate(user.created_at, {
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                      })
                    : ""
                }
                className={`${INPUT_CLS} w-full bg-gray-50 text-gray-500 cursor-default`}
              />
            </div>
          </div>
        </section>

        {/* Bölüm 2: Yatırım Profili */}
        <section className={CARD_CLS}>
          <h2 className="text-base font-semibold text-gray-900 mb-4">Yatırım Profili</h2>
          <div className="flex gap-2 mb-4">
            {RISK_OPTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setSelectedRisk(key)}
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
                  selectedRisk === key
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {profileError && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg mb-3">{profileError}</p>
          )}
          {profileMsg && (
            <p className="text-sm text-green-600 bg-green-50 px-3 py-2 rounded-lg mb-3">
              {profileMsg}
            </p>
          )}
          <button
            onClick={handleProfileSave}
            disabled={profileSaving}
            className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {profileSaving ? "Kaydediliyor..." : "Kaydet"}
          </button>
        </section>

        {/* Bölüm 3: Şifre Değiştir */}
        <section className={CARD_CLS}>
          <h2 className="text-base font-semibold text-gray-900 mb-4">Şifre Değiştir</h2>
          <div className="space-y-3 mb-4">
            <div>
              <label htmlFor="s-cur-pwd" className="block text-xs text-gray-500 mb-1">Mevcut şifre</label>
              <input
                id="s-cur-pwd"
                type="password"
                value={curPwd}
                onChange={(e) => setCurPwd(e.target.value)}
                className={`${INPUT_CLS} w-full`}
                placeholder="••••••••"
              />
            </div>
            <div>
              <label htmlFor="s-new-pwd" className="block text-xs text-gray-500 mb-1">Yeni şifre (en az 8 karakter)</label>
              <input
                id="s-new-pwd"
                type="password"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                className={`${INPUT_CLS} w-full`}
                placeholder="••••••••"
              />
            </div>
            <div>
              <label htmlFor="s-new-pwd2" className="block text-xs text-gray-500 mb-1">Yeni şifre tekrar</label>
              <input
                id="s-new-pwd2"
                type="password"
                value={newPwd2}
                onChange={(e) => setNewPwd2(e.target.value)}
                className={`${INPUT_CLS} w-full`}
                placeholder="••••••••"
              />
            </div>
          </div>
          {pwdError && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg mb-3">{pwdError}</p>
          )}
          {pwdMsg && (
            <p className="text-sm text-green-600 bg-green-50 px-3 py-2 rounded-lg mb-3">{pwdMsg}</p>
          )}
          <button
            onClick={handlePasswordChange}
            disabled={pwdSaving}
            className="w-full py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {pwdSaving ? "Güncelleniyor..." : "Şifreyi Güncelle"}
          </button>
        </section>

        {/* Bölüm 4: Genel Tercihler */}
        <section className={CARD_CLS}>
          <h2 className="text-base font-semibold text-gray-900 mb-1">Genel Tercihler</h2>
          <p className="text-xs text-gray-500 mb-4">Görünüm ayarları.</p>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm text-gray-700">USD karşılığı göster</p>
              <p className="text-xs text-gray-400 mt-0.5">TL değerlerin altında anlık $ karşılığı (TCMB kuru, 5 dk önbellek)</p>
            </div>
            <button
              type="button"
              onClick={() => {
                const next = !showUsd;
                setShowUsdState(next);
                setShowUsd(next);
              }}
              className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${showUsd ? "bg-blue-600" : "bg-gray-200"}`}
              aria-label={showUsd ? "USD karşılığını kapat" : "USD karşılığını aç"}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${showUsd ? "translate-x-5" : ""}`}
              />
            </button>
          </div>
        </section>

        {/* Bölüm 5: Dashboard Görünümü */}
        <section className={CARD_CLS}>
          <h2 className="text-base font-semibold text-gray-900 mb-1">Dashboard Görünümü</h2>
          <p className="text-xs text-gray-500 mb-4">Görmek istemediğiniz kartları gizleyin.</p>
          <div className="space-y-5">
            {DASHBOARD_GROUPS.map((group) => (
              <div key={group.id}>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-2">
                  {group.label}
                </h3>
                <div className="space-y-1 border border-gray-100 rounded-xl divide-y divide-gray-50">
                  {DASHBOARD_CARDS.filter((c) => c.group === group.id).map(({ id, label }) => {
                    const isHidden = hiddenCards.includes(id);
                    return (
                      <div key={id} className="flex items-center justify-between px-3 py-2.5">
                        <span className="text-sm text-gray-700 select-none">{label}</span>
                        <button
                          type="button"
                          onClick={() => {
                            const next = isHidden
                              ? hiddenCards.filter((c) => c !== id)
                              : [...hiddenCards, id];
                            setHiddenCards(next);
                            saveHiddenCards(next);
                          }}
                          className={`relative w-10 h-5 rounded-full transition-colors ${isHidden ? "bg-gray-200" : "bg-blue-600"}`}
                          aria-label={isHidden ? `${label} göster` : `${label} gizle`}
                        >
                          <span
                            className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${isHidden ? "" : "translate-x-5"}`}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Bölüm 5: Geri Bildirim — bug, feature, soru için GitHub'a yönlendir */}
        <section className={CARD_CLS}>
          <h2 className="text-base font-semibold text-gray-900 mb-2">Geri Bildirim</h2>
          <p className="text-sm text-gray-500 mb-4">
            KFinans&apos;ı geliştirmek için yardımınıza ihtiyacımız var. Bug, öneri veya sorularınız için
            aşağıdaki kanalları kullanın.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <a
              href="https://github.com/celikada/KFinans/issues/new?template=bug_report.yml"
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col items-start p-4 rounded-lg border border-gray-200 hover:border-red-300 hover:bg-red-50 transition-colors group"
            >
              <span className="text-2xl mb-2">🐛</span>
              <span className="text-sm font-semibold text-gray-900 group-hover:text-red-700">Hata Bildir</span>
              <span className="text-xs text-gray-500 mt-1">Bir şey çalışmıyor mu? Detaylı raporlayın</span>
            </a>
            <a
              href="https://github.com/celikada/KFinans/issues/new?template=feature_request.yml"
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col items-start p-4 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors group"
            >
              <span className="text-2xl mb-2">💡</span>
              <span className="text-sm font-semibold text-gray-900 group-hover:text-blue-700">Özellik İste</span>
              <span className="text-xs text-gray-500 mt-1">Yeni bir özellik öneriniz var mı?</span>
            </a>
            <a
              href="https://github.com/celikada/KFinans/discussions"
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col items-start p-4 rounded-lg border border-gray-200 hover:border-purple-300 hover:bg-purple-50 transition-colors group"
            >
              <span className="text-2xl mb-2">💬</span>
              <span className="text-sm font-semibold text-gray-900 group-hover:text-purple-700">Tartışmaya Katıl</span>
              <span className="text-xs text-gray-500 mt-1">Sorular, fikirler, deneyim paylaşımı</span>
            </a>
          </div>
          <p className="text-xs text-gray-400 mt-4">
            🔐 Güvenlik açıkları için public issue açmayın —{" "}
            <a
              href="https://github.com/celikada/KFinans/security/advisories/new"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              private vulnerability report
            </a>{" "}
            kullanın.
          </p>
        </section>

        {/* Bölüm 6: Tehlike Bölgesi */}
        <section className={`${CARD_CLS} border-red-100`}>
          <h2 className="text-base font-semibold text-red-600 mb-2">Tehlike Bölgesi</h2>
          <p className="text-sm text-gray-500 mb-4">
            Hesabınızı kalıcı olarak silin. Bu işlem geri alınamaz.
          </p>
          <button
            onClick={handleDeleteAccount}
            className="w-full py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
          >
            Hesabı Sil
          </button>
        </section>
      </main>
    </div>
  );
}
