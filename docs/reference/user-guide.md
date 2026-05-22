# KFinans Kullanıcı Kılavuzu

> **Amaç:** Son kullanıcılar için KFinans dashboard sayfalarının feature-bazlı kullanım rehberi.
> **Hedef kitle:** Kişisel yatırım/portföy takibi yapan kullanıcılar.

**Durum:** Taslak — ekran görüntüleri + video link Sprint 3'te eklenir.

## 1. Hesap Yönetimi

### 1.1 Kayıt
- `/register` → e-posta + şifre + KVKK + Şartlar onayı + 18 yaş onayı
- E-posta doğrulama bağlantısı gelir (Resend ile, ~1 dk)
- Mail gelmediyse: spam klasörü kontrol → `/login` sayfasında "Yeniden gönder"

### 1.2 Giriş
- `/login` → e-posta + şifre
- Şifre 5 başarısız deneme → 15 dk hesap kilidi
- MFA TOTP aktifse: 6 haneli kod veya kurtarma kodu

### 1.3 MFA (İki Adımlı Doğrulama)
- Kurulum: `/dashboard/settings/security` → "MFA Kur" → QR kod tara (Google Authenticator) → 6 hane doğrula → 10 kurtarma kodu kaydet
- Devre dışı: aynı sayfada → 6 hane doğrula

### 1.4 KVKK Hakları
- `/dashboard/settings` → "Veri Dışa Aktar" → JSON formatında tüm veri
- Hesap silme: 30 gün geri alma süresi, sonra fiziksel silinme
- Açık rıza geri çekme: Anthropic AI tavsiyesi için ayrı toggle

## 2. Dashboard Sayfaları

### 2.1 Ana Dashboard `/dashboard`
- Toplam portföy değeri (TL + USD toggle)
- Varlık dağılımı grafiği (kripto/fon/hisse/madenler/BES/nakit)
- Haftalık/aylık değişim
- Son işlemler

### 2.2 TEFAS Fonları `/dashboard/tefas`
- Manuel fon ekle + adet/maliyet
- MKK e-Yatırımcı Excel import (otomatik dolum)
- Aracı kurum (distributor) ayrımı

### 2.3 Hisse Senetleri `/dashboard/stocks`
- BIST + ABD + UK hisse desteği (Yahoo Finance)
- MKK Excel import
- Maliyet bazı + kar/zarar

### 2.4 Kripto Borsalar `/dashboard/crypto`
- Binance / iCrypex API key ile otomatik
- Manuel kripto: `/dashboard/manual-crypto` (BinanceTR, BTCTurk, vs.)

### 2.5 Blockchain Cüzdanlar `/dashboard/wallets`
- 10 zincir: Bitcoin (xpub), Ethereum, Sonic, Avalanche C/P, Solana, Cardano, Algorand, Polkadot, Litecoin
- Adres + xpub Fernet ile şifreli saklanır (DB'de plaintext yok)
- ERC-20 token discovery (Ethplorer)

### 2.6 BES `/dashboard/bes`
- Manuel giriş veya Excel import
- Ana para + getiri + devlet katkısı + getirisi (4 metrik)

### 2.7 Kıymetli Madenler `/dashboard/commodities`
- Altın (gram/çeyrek/yarım/tam/cumhuriyet)
- Gümüş gram
- TCMB USD + Yahoo XAU/XAG fallback

### 2.8 Harcama Takibi `/dashboard/expenses`
- Manuel harcama (kategori + tutar + tarih + opsiyonel kart)
- Excel import
- Kart bağlı + ödendi → bütçe ham toplamından **HARİÇ** (çift sayım önleme)

### 2.9 Planlı Ödemeler `/dashboard/planned`
- Tekrar tipi: tek seferlik, aylık, çeyreklik, yıllık, custom
- Gelecek ay projeksiyonu

### 2.10 Gelirler `/dashboard/income`
- Gerçekleşen gelir kayıtları + periyodik gelir tanımları (recurring_incomes)
- "Realize" butonu: periyodik tanımdan gerçek kayıt üretir
- 6 metrik kart (this_month_actual, ytd_actual, yıl sonu beklentisi vs.)

### 2.11 Bütçe `/dashboard/budget`
- Aylık kategori bütçeleri
- Harcama vs bütçe karşılaştırma (yüzde + bar)

### 2.12 Kredi Kartları `/dashboard/credit-cards`
- Kart tanımı + ekstre (aylık) + taksitler
- Dönem içi borç (manuel güncellenir)
- Ödeme tarihi yaklaşan uyarı

### 2.13 Nakit/Banka `/dashboard/cash`
- Hesap bakiyeleri TRY/USD/EUR/CHF/JPY/GBP
- TCMB kuru ile TL'ye normalize

### 2.14 Nakit Akış `/dashboard/cash-flow`
- 12 aylık projeksiyon (gerçekleşen + tahmini)
- ComposedChart (gelir-gider çubuk + Net çizgi)
- Excel/PDF rapor indir

### 2.15 Geçmiş `/dashboard/history`
- Haftalık snapshot tarihi listesi
- Her snapshot → Excel + PDF rapor
- TL/USD toggle

### 2.16 Hedef `/dashboard/goal`
- Yatırım hedefi (tutar + tarih)
- İlerleme yüzdesi

### 2.17 Ayarlar `/dashboard/settings`
- Profil bilgileri (e-posta değiştirme — onaylı)
- Şifre değiştirme (zxcvbn + HIBP)
- İki adımlı doğrulama (MFA)
- API anahtarları (Binance + iCrypex)
- Açık rıza yönetimi
- Veri dışa aktarım
- Hesap silme

## 3. AI Tavsiye (Faz 3 — Kredi sistemli)

- `/dashboard` → "Tavsiye Al" (1 kredi)
- Claude AI portföyünü analiz eder, SPK uyumlu disclaimer ile öneriler
- Anthropic özel açık rıza gerekir (KVKK m.9)
- Geçmiş tavsiyeler: `/dashboard/advice/history` (planlı)

## 4. Bildirimler ve E-postalar

- Kayıt sonrası: doğrulama maili
- Şifre sıfırlama: 1 saat geçerli token
- E-posta değişikliği: yeni adrese onay
- KEP (kurumsal) — planlı

## 5. Dil Desteği

- TR (Türkçe) varsayılan
- EN (English) — login + dashboard layout partial; tam çeviri Sprint 3+
- Üst sağ köşede dil değiştirici (cookie tabanlı)

## 6. Mobil Uyumluluk

- Responsive tasarım — telefon/tablet/desktop
- Mobil uygulama planlı: Flutter (Faz 4)

## 7. Güvenlik İpuçları (Kullanıcı için)

- Şifre: en az 8 karakter (12+ önerilir), zxcvbn ≥3, HIBP'de yok
- MFA mutlaka aktif et
- Recovery code'ları güvenli yere kaydet (offline + şifreli)
- API key'leri sadece KFinans'a ver (üçüncü taraf paylaşma)
- Exchange'lerde **sadece read-only** API key kullan

## 8. Yardım

- E-posta: `iletisim@kfinans.app`
- Hata bildirimi: GitHub issue (https://github.com/celikada/KFinans/issues)
- KVKK soruları: `kvkk@kfinans.app` (Sprint 1 sonu kurulacak)

## 9. Referans

- [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md)
- [`../04-frontend.md`](../04-frontend.md) — Teknik frontend mimari
- [`../08-uyumluluk-kvkk.md`](../08-uyumluluk-kvkk.md) — KVKK detay
