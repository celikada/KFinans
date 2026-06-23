"use client";

/**
 * Sunucu-cache canlı portföy hook'u (fix/dashboard-live-cache-resilience).
 *
 * Dashboard + 6 detay sayfası (wallets/crypto/tefas/stocks/commodities/
 * manual-crypto) ağır dış-API çağrılarını HER açılışta tetiklemek yerine
 * backend'in per-user cache'inden `GET /portfolio/live` ile TEK seferde okur.
 *
 * Akış:
 *   - Mount'ta `getLivePortfolio()` oku (hızlı; otomatik dış-refetch YOK).
 *   - status === "refreshing" ise kısa aralıkla (POLL_INTERVAL_MS, üst sınır
 *     MAX_POLLS) tekrar oku; status ok/error olunca dur.
 *   - `refresh()` → `POST /portfolio/refresh?force=1` + tekrar poll.
 *
 * Bayat veri KASITLI gösterilebilir (kullanıcı kararı); "Son güncelleme" +
 * "Yenile" bunu yönetir. Sunucu cache hata/timeout'ta takılmamak için
 * `_client.ts` request timeout'u (30s) devreye girer.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { LivePortfolioOut } from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
// Arka plan refresh (paralel cüzdan zincirleri + dış API) ~45-60 sn sürebilir
// (BTC/LTC xpub taraması, RPC fallback). Poll bütçesi bunu yakalamalı: 20×3s=60s.
const MAX_POLLS = 20;

export interface UseLivePortfolioResult {
  /** Son okunan canlı portföy (cache yoksa null). */
  data: LivePortfolioOut | null;
  /** İlk yükleme (henüz hiç veri gelmedi). */
  loading: boolean;
  /** Arka plan yenileme/poll sürüyor (status="refreshing" veya refresh() çağrıldı). */
  refreshing: boolean;
  /** Okuma sırasında oluşan hata mesajı (boşsa hata yok). */
  error: string;
  /** Manuel "Yenile": backend'i zorla yeniden hesaplat + poll et. */
  refresh: () => Promise<void>;
  /** Tek bir kartı (bölümü) yeniden hesaplat + poll et (per-kart yenile ikonu). */
  refreshSection: (section: string) => Promise<void>;
  /** Şu an tek-kart yenilemesi süren bölüm (null = yok) — yalnız o kart spinner gösterir. */
  refreshingSection: string | null;
  /** Tek bir cüzdanı yeniden hesaplat + poll et (per-cüzdan yenile ikonu). */
  refreshWallet: (walletId: string) => Promise<void>;
  /** Şu an tek-cüzdan yenilemesi süren cüzdan id (null = yok) — yalnız o satır spinner gösterir. */
  refreshingWalletId: string | null;
}

export function useLivePortfolio(): UseLivePortfolioResult {
  const [data, setData] = useState<LivePortfolioOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingSection, setRefreshingSection] = useState<string | null>(null);
  const [refreshingWalletId, setRefreshingWalletId] = useState<string | null>(null);
  const [error, setError] = useState("");

  // Cleanup için: aktif poll timer + unmount bayrağı.
  const cancelledRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Aktif manuel yenileme (global/section) varken yeni tetiklemeyi engeller.
  const inFlightRef = useRef(false);
  // Recursive poll zincirini ref üzerinden çözer (callback kendini deklarasyondan
  // önce referanslayamaz → ref-indirection TDZ/eslint sorununu giderir). Ref bir
  // effect içinde güncellenir (render sırasında ref yazımı yapılmaz).
  const loopRef = useRef<(pollsLeft: number) => Promise<void>>(async () => {});

  // Tek okuma + gerekirse poll zinciri. `pollsLeft` kalan deneme sayısı.
  const loop = useCallback(async (pollsLeft: number): Promise<void> => {
    try {
      const res = await api.getLivePortfolio();
      if (cancelledRef.current) return;
      setData(res);
      setError("");
      setLoading(false);

      if (res.status === "refreshing" && pollsLeft > 0) {
        setRefreshing(true);
        if (timerRef.current !== null) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          // loop kendi içinde tüm hataları yutar; .catch yalnız floating-promise
          // guard'ı (void operatörü S3735'i tetikliyordu).
          if (!cancelledRef.current) loopRef.current(pollsLeft - 1).catch(() => {});
        }, POLL_INTERVAL_MS);
      } else {
        // ok / error / poll bütçesi bitti → dur.
        setRefreshing(false);
      }
    } catch (err) {
      if (cancelledRef.current) return;
      setLoading(false);
      setRefreshing(false);
      setError(err instanceof Error ? err.message : "Portföy verisi okunamadı");
    }
  }, []);

  // En güncel `loop`'u ref'e yansıt (setTimeout closure'ı bunu kullanır).
  useEffect(() => {
    loopRef.current = loop;
  }, [loop]);

  useEffect(() => {
    cancelledRef.current = false;
    // Mikrotask: senkron setState-in-effect uyarısını (cascading render)
    // tetiklemeden ilk okumayı başlat (fetch zaten async). loop hataları yutar;
    // .catch yalnız floating-promise guard'ı (void operatörü S3735'i tetikliyordu).
    Promise.resolve()
      .then(() => {
        if (!cancelledRef.current) return loop(MAX_POLLS);
      })
      .catch(() => {});
    return () => {
      cancelledRef.current = true;
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, [loop]);

  const refresh = useCallback(async () => {
    // Çakışma engeli: bir yenileme/kart-yenileme zaten koşuyorsa yenisini başlatma
    // (iki loop aynı timerRef'i paylaşıp birbirini iptal etmesin).
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setRefreshing(true);
    setRefreshingSection(null); // global yenileme tek-kart spinner'ını süpürür
    setError("");
    try {
      await api.refreshPortfolio(true);
    } catch (err) {
      // Tetikleme best-effort; başarısız olsa bile mevcut cache'i poll et.
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : "Yenileme tetiklenemedi");
      }
    }
    // Backend arka planda hesaplar → poll ile sonucu yakala.
    await loop(MAX_POLLS);
    inFlightRef.current = false;
  }, [loop]);

  const refreshSection = useCallback(async (section: string) => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setRefreshingSection(section);
    setError("");
    try {
      await api.refreshPortfolioSection(section);
    } catch (err) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : "Yenileme tetiklenemedi");
      }
    }
    // Bölüm arka planda hesaplanır → poll ile sonucu yakala, sonra spinner'ı kapat.
    await loop(MAX_POLLS);
    if (!cancelledRef.current) setRefreshingSection(null);
    inFlightRef.current = false;
  }, [loop]);

  const refreshWallet = useCallback(async (walletId: string) => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setRefreshingWalletId(walletId);
    setError("");
    try {
      await api.refreshWallet(walletId);
    } catch (err) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : "Yenileme tetiklenemedi");
      }
    }
    // Cüzdan arka planda hesaplanır → poll ile sonucu yakala, sonra spinner'ı kapat.
    await loop(MAX_POLLS);
    if (!cancelledRef.current) setRefreshingWalletId(null);
    inFlightRef.current = false;
  }, [loop]);

  return {
    data,
    loading,
    refreshing,
    refreshingSection,
    refreshingWalletId,
    error,
    refresh,
    refreshSection,
    refreshWallet,
  };
}
