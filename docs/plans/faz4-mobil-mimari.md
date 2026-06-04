# Faz 4 — Flutter Mobil Uygulama Mimari Tasarımı

> **Statü:** Tasarım dokümanı (kod yazılmadı) · **Tarih:** 2026-06-02
> **Roadmap konumu:** `docs/10-yol-haritasi-2026.md` §A5 (P2) + §4 Faz D3 (Platform Genişleme, v2.0).
> **Bağımlılık zinciri:** web → Flutter → MCP (memory `project_roadmap_post_web`).
> **Önkoşullar (roadmap):** B3 (pagination) + A4 (bildirim FCM/APNs). JWT + refresh rotation + MFA
> TOTP **zaten mobil uyumlu**; biyometrik kilit + secure storage (Keychain/Keystore) bu fazda eklenir.
>
> Bu belge `CLAUDE.md` (auth/MFA/refresh rotation/i18n), `docs/04-frontend.md` (web `authedFetch`
> 401→refresh→retry single-flight deseni) ve `docs/07-guvenlik.md` ile birlikte okunmalıdır.

---

## 1. Kapsam ve Hedef

### 1.1 Hedef
Mevcut KFinans **FastAPI backend'ini değiştirmeden** tüketen, **iOS + Android** native deneyimli
bir Flutter istemcisi. Backend, web frontend için yazılmış REST yüzeyini aynen sunar; mobil yalnız
bu yüzeyi tüketen ikinci bir istemcidir.

**Mimari ilke (değişmez):** KFinans **modüler monolit** kalır (memory `project_saas_architecture_decision`).
Mobil, mikroservis veya BFF (Backend-for-Frontend) **getirmez**; doğrudan mevcut `/api/v1/*` uçlarını çağırır.
Web istemcisi (Next.js) ile aynı sözleşmeyi paylaşır.

### 1.2 Backend'in mobil için yapacağı (sınırlı, geriye-uyumlu) değişiklikler
Backend "değişmez" ilkesi **iş mantığı** içindir. Mobil için yalnız iki **opt-in / geriye-uyumlu**
iyileştirme gerekir (detay §8):
1. **B3 pagination** — `/expenses /incomes /wallets /planned-expenses` için (web'i kırmadan, opt-in).
2. **İnce payload** — mobil listelerde ağır alanların (tam xpub, geçmiş seriler) kırpılması.
3. **A4 bildirim (FCM/APNs)** — push için cihaz token kaydı; M3'e ertelenir, M1/M2 blocker değil.

### 1.3 Kapsam dışı (bu faz)
- Open banking (A6), MCP (C4) — ayrı fazlar.
- Yeni iş mantığı / yeni varlık tipi — mobil yalnız mevcut veriyi gösterir.
- Web feature paritesi %100 (mobil MVP read-ağırlıklı; bkz. §7 ekran envanteri).

---

## 2. Ortam Önkoşulları (Geliştirme Makinesi)

> **Kritik gerçek (bu makinede teyit edildi 2026-06-02):** Geliştirme makinesinde **Flutter SDK yok,
> Dart yok, Android SDK yok, `adb` yok**. Yalnız Java mevcut (Oracle JDK 8 + Adoptium JDK 25).
> Flutter Android derlemesi **JDK 17** tercih eder; mevcut JDK'lar Flutter/Gradle ile birebir uyumlu
> değildir → ayrı bir **JDK 17** kurulumu ve `flutter config --jdk-dir` ile yönlendirme gerekir.

### 2.1 Platform gerçeği: Windows = yalnız Android tarafı
- **Windows makinesinde** yalnız **Android** build + emülatör + cihaz testi yapılabilir.
- **iOS build/test/imzalama `macOS` zorunlu** (Xcode yalnız macOS'ta çalışır). Apple'ın kuralı; aşılamaz.
  iOS için seçenekler: (a) fiziksel/sanal Mac, (b) bulut macOS runner (Codemagic / GitHub-hosted macOS /
  MacStadium) — bkz. §11 CI/CD.
- Sonuç: **M1/M2 Android-öncelikli** geliştirilir; iOS derlemesi **CI'da macOS runner** ile veya bir
  Mac edinildiğinde devreye girer. iOS yayını M3'te (Apple Developer hesabı + macOS gerektirir, §13 risk).

### 2.2 Önerilen araç sürümleri
| Araç | Önerilen | Not |
|------|----------|-----|
| Flutter SDK | **3.27+ (stable kanal)** | Dart 3.6+ ile gelir; null-safety + records/patterns hazır. |
| Dart | 3.6+ | Flutter ile birlikte gelir, ayrı kurulum yok. |
| JDK | **17 (Temurin/Adoptium)** | Mevcut JDK 8/25 Gradle/AGP ile uyumsuz; `flutter config --jdk-dir`. |
| Android SDK | API 35 (compileSdk) / minSdk 24 | `cmdline-tools` + `platform-tools` (`adb`); Android Studio ile kolay. |
| Android Studio | son stable | SDK manager + emülatör (AVD) + Flutter/Dart eklentileri. |
| Xcode (iOS) | son stable | **yalnız macOS** — Windows'ta kurulamaz. |
| CocoaPods (iOS) | son | macOS'ta `gem install cocoapods`. |

### 2.3 İlk kurulum adımları (Windows — Android)
1. Flutter SDK (stable) indir, PATH'e ekle.
2. JDK 17 (Temurin) kur → `flutter config --jdk-dir "<jdk17-yol>"`.
3. Android Studio kur → SDK Manager'dan API 35 + `platform-tools` + emülatör.
4. `flutter doctor --android-licenses` → lisansları kabul et.
5. `flutter doctor` çıktısı Android tarafı yeşil olmalı; iOS satırı Windows'ta "unavailable" kalır (beklenen).
6. Fiziksel cihazda USB debugging veya AVD emülatör ile `flutter run`.

> **`flutter doctor` "iOS toolchain — unavailable on Windows"** uyarısı **normaldir** ve M1/M2 Android
> geliştirmesini engellemez.

---

## 3. Proje Yapısı

### 3.1 Konum: monorepo `mobile/` dizini
Mevcut repo (`KFinans/`) içinde `backend/` ve `frontend/` ile aynı seviyede **`mobile/`** dizini.
Gerekçe: tek repo → tek sürüm/etiket hizası, DTO sözleşmesini (backend Pydantic ↔ mobil model) yan yana
tutma, i18n sözlüklerini paylaşma kolaylığı (§9). CI ise dizin-bazlı tetiklenir (`mobile/` değişince
mobil pipeline; bkz. §11).

### 3.2 Mimari yaklaşım: feature-first (katman içte)
**Feature-first** seçildi (layer-first değil). Gerekçe: tek geliştirici + orta karmaşıklık + çok sayıda
bağımsız modül (portföy, harcama, gelir, ayarlar...). Her özellik kendi `data/domain/presentation`
katmanını içinde taşır → bir ekran üzerinde çalışırken tek klasörde kalınır, web'deki `_components/`
sayfa-parçalama disiplininin (docs/04 §4) mobil karşılığı. Layer-first (tüm `models/`, tüm `screens/`)
büyüdükçe dağılır.

```
mobile/
├── pubspec.yaml
├── analysis_options.yaml          # flutter_lints + proje kuralları (identifier/comment İngilizce)
├── lib/
│   ├── main.dart                  # bootstrap: ProviderScope + uygulama açılış kilidi (biyometrik)
│   ├── app.dart                   # MaterialApp.router + tema + i18n delegate
│   ├── core/
│   │   ├── api/
│   │   │   ├── api_client.dart     # dio instance + base URL + interceptor zinciri
│   │   │   ├── auth_interceptor.dart   # Bearer ekleme + 401→refresh→retry (single-flight) — §5
│   │   │   ├── token_store.dart        # flutter_secure_storage sarmalayıcı (Keychain/Keystore) — §6
│   │   │   └── api_exception.dart      # sanitized hata modeli ({detail, code, request_id})
│   │   ├── auth/
│   │   │   ├── auth_controller.dart    # login / MFA verify / logout / oturum durumu
│   │   │   └── biometric_gate.dart     # local_auth açılış kilidi — §6
│   │   ├── config/
│   │   │   └── env.dart                # API base URL (dev/prod), pinning anahtarları
│   │   ├── i18n/                       # tr/en (web sözlüğünden türetilmiş — §9)
│   │   └── widgets/                    # paylaşılan UI (MoneyText, ErrorView, RefreshScaffold)
│   ├── features/
│   │   ├── dashboard/
│   │   │   ├── data/        # repository + dio çağrıları + DTO eşleme
│   │   │   ├── domain/      # model (PortfolioSummary, AssetCard) + saf hesap
│   │   │   └── presentation/# screen + widget + riverpod provider'ları
│   │   ├── wallets/         # (aynı data/domain/presentation üçlüsü)
│   │   ├── expenses/
│   │   ├── income/
│   │   ├── history/         # snapshot geçmişi (grafik)
│   │   ├── settings/        # hesap + güvenlik (MFA durumu) + dil + tema
│   │   └── ...              # (sonraki modüller M2'de eklenir)
│   └── routing/
│       └── app_router.dart         # go_router; auth guard (token yok → /login)
├── test/                           # unit + widget testleri
├── integration_test/               # uçtan uca akış (login + dashboard)
├── android/                        # Gradle, imzalama config (§11)
└── ios/                            # Xcode workspace, Info.plist (yalnız macOS'ta build)
```

---

## 4. State Management Seçimi

### 4.1 Karar: **Riverpod** (v2, `flutter_riverpod` + `riverpod_generator`)

| Aday | Artı | Eksi | Bu proje için |
|------|------|------|---------------|
| **Riverpod** | Derleme-zamanı güvenli, BuildContext'siz, test/mock kolay, async (`FutureProvider`/`AsyncNotifier`) yerleşik, otomatik dispose | Öğrenme eğrisi orta | ✅ **Seçildi** |
| Bloc | Net event/state ayrımı, büyük ekipte disiplin | Çok boilerplate; tek geliştiriciye ağır | ❌ Fazla seremoni |
| Provider | Basit, resmi | Büyüdükçe yetersiz; web `useState`+`useEffect` (docs/04 §5 "yetersiz") hatası tekrarlanır | ❌ Ölçeklenmez |

**Gerekçe (tek geliştirici, orta karmaşıklık):**
- KFinans verisi **çoğunlukla async cache'lenebilir REST çağrısı** (portföy, wallet, snapshot). Riverpod'un
  `AsyncNotifier` + `FutureProvider` modeli bunu birinci sınıf destekler; web tarafında
  `@tanstack/react-query` için planlanan rolün (docs/04 §5) Flutter karşılığıdır.
- `BuildContext` bağımsızlığı → interceptor/refresh akışı ve biyometrik kilit gibi UI-dışı mantık temiz.
- `ProviderScope` + override ile **test mock** doğrudan; backend'i sarmalayan repository'ler kolayca taklit edilir.
- Bloc'un event/state ayrımı bu boyutta gereksiz boilerplate; tek geliştiricinin hızını düşürür.

**Yan kararlar:**
- Sunucu durumu (server state) → Riverpod `AsyncNotifier` + repository; TTL/cache web cache tablosuyla (docs/04 §5) hizalı.
- İstemci UI durumu (tema, dil, kart gizleme) → basit `Notifier` + secure/normal storage.
- Routing → `go_router` (auth guard: token yoksa `/login`'e — web `proxy.ts` davranışının karşılığı).

---

## 5. API Client Katmanı

### 5.1 Karar: **dio** (http değil)
**dio** seçildi. Gerekçe: **interceptor zinciri** (auth + retry + logging), iptal token'ı, `FormData`
(Excel/dosya yükleme — TEFAS/MKK/BES import uçları), zaman aşımı yapılandırması yerleşik. `http` paketi
minimal; 401→refresh→retry single-flight gibi merkezî davranışı elle örmeyi gerektirir. dio bunu
tek interceptor'da toplar.

### 5.2 Interceptor zinciri
```
İstek  → AuthInterceptor (Bearer ekle) → [dio] → Sunucu
Yanıt  → AuthInterceptor (401 yakala → refresh → retry) → çağıran
```

### 5.3 401 → refresh → retry (web `authedFetch` deseninin birebir karşılığı)
Web `lib/api/_client.ts` (docs/04 §3) ile **aynı mantık**, çünkü backend **refresh token rotation**
uygular (`docs/07 §3` + CLAUDE.md): her `/auth/refresh` eski refresh `jti`'sini `revoked_tokens`
blacklist'ine atar ve yeni refresh üretir. Bu yüzden iki kural zorunludur:

1. **Single-flight refresh:** Aynı anda birden çok istek 401 alırsa **tek bir** `/auth/refresh` çağrısı
   yapılmalı; diğerleri o sonucu beklemeli (kuyruk). Aksi halde 2. refresh çağrısı rotation gereği 401
   alır → kullanıcı gereksiz logout olur. (Web'deki `_refreshInflight` promise paylaşımının Dart karşılığı:
   tek bir `Completer`/`Future` + bekleyen istek kuyruğu.)
2. **`/auth/refresh` kendi 401'inde retry yapma** (sonsuz döngü engeli) → temizle + `/login`.

**Dart akışı (sözde-kod, kod değil):**
```
onError(err):
  if err.status == 401 ve path != "/auth/refresh" ve !alreadyRetried:
      newToken = await _refreshSingleFlight()   # tek uçuş; eşzamanlı çağrılar aynı Future'ı bekler
      if newToken != null:
          retry original request with newToken   # bir kez
      else:
          await tokenStore.clear()
          router.go("/login")
  else:
      forward sanitized ApiException(detail, code, request_id)

_refreshSingleFlight():
  if _inflight != null: return _inflight       # kuyruk — yeni çağrı başlatma
  _inflight = (async {
      try:
        res = POST /auth/refresh {refresh_token}
        if !res.ok: return null
        await tokenStore.save(res.access_token, res.refresh_token)  # rotated refresh kaydet
        return res.access_token
      finally: _inflight = null
  })()
  return _inflight
```

### 5.4 Hata yönetimi
- Backend zaten sanitized `{detail, code, request_id}` döner (BACK-008/SEC-007, docs/07). Mobil **trace
  veya ham SQL göstermez**; `ApiException`'a eşler, kullanıcıya i18n'li mesaj + (opsiyonel) `request_id`.
- Ağ/timeout hataları → tekrar-dene UI (RefreshScaffold + "yeniden dene" butonu).
- 402 (yetersiz kredi — `/advice/generate`), 403 (KVKK consent / e-posta doğrulanmadı), 423 (hesap kilidi
  + `Retry-After`), 429 (rate limit) → her biri için özel kullanıcı mesajı (web ile aynı semantik).

---

## 6. Auth Akışı (Mobil)

### 6.1 Login → MFA → oturum (backend sözleşmesiyle birebir)
Backend login, `totp_enabled` ise iki adımlı döner (CLAUDE.md MFA + docs/07 §3):

```
POST /auth/login {email, password}
  ├─ MFA kapalı  → { access_token, refresh_token }                → oturum açık
  └─ MFA açık    → { mfa_required: true, pre_mfa_token, expires_in_seconds }
        ↓ kullanıcı TOTP (6 hane) veya recovery kodu girer
        POST /mfa/verify { pre_mfa_token, code }   → { access_token, refresh_token }
```
- `pre_mfa_token` JWT `type=pre_mfa`, 15 dk TTL, yalnız `/mfa/verify`'da geçerli. Mobil bunu **bellekte**
  tutar (secure storage'a yazmaya gerek yok — kısa ömür); `expires_in_seconds` ile geri sayım UI gösterilir.
- Web ile aynı: 403 → "e-posta doğrulanmadı" + tekrar gönder; 423 → kilit + `Retry-After`.

### 6.2 Secure storage (Keychain / Keystore)
- **`flutter_secure_storage`** → iOS **Keychain**, Android **Keystore** (AES, donanım destekli).
  **localStorage muadili DEĞİL** — web tarafındaki `localStorage` XSS açığı (docs/04 §3 güvenlik notu)
  mobilde tekrarlanmaz; refresh token OS düzeyinde korunur.
- Saklananlar: `access_token` (kısa ömür, prod 30 dk), `refresh_token` (rotated, ~7 gün). `pre_mfa_token`
  saklanmaz (bellekte).
- Çıkışta `POST /auth/logout` (backend access+refresh `jti`'sini blacklist'e atar) + secure storage temizliği.

### 6.3 Biyometrik kilit (uygulama açılışı)
- **`local_auth`** → iOS Face ID/Touch ID, Android BiometricPrompt (parmak izi/yüz).
- **Davranış:** Token secure storage'da mevcutsa, uygulama foreground'a geldiğinde (cold start + belirli
  bir arka plan süresinden sonra) biyometrik/PIN doğrulaması istenir. Başarısızsa portföy ekranları
  açılmaz. Bu, çalınan açık cihazda yerel koruma sağlar (token zaten OS-korumalı; biyometrik **ek katman**).
- Opt-in: Ayarlar'dan açılıp kapatılabilir; cihazda biyometrik yoksa cihaz PIN'ine düşülür.
- iOS `Info.plist` `NSFaceIDUsageDescription` zorunlu (App Store review). Android `USE_BIOMETRIC` izni.

---

## 7. Ekran Envanteri (MVP Öncelik Sırası)

Web'de 20 dashboard sayfası var (docs/04 §1). Mobil **kademeli** taşır; v1 read-ağırlıklı.

### M1 — Çekirdek (auth + read-only portföy) — **EN YÜKSEK ÖNCELİK**
| Mobil ekran | Web karşılığı | API |
|-------------|---------------|-----|
| Login + MFA 2. adım | `/login` | `/auth/login`, `/mfa/verify` |
| Dashboard özeti (Toplam Portföy + Finans Net Bakiye + kart listesi) | `/dashboard` | `/portfolio/*` özet uçları |
| Snapshot geçmişi grafiği | `/dashboard/history` | `GET /portfolio/history?limit=12` |
| Cüzdanlar (10 zincir, **maskeli adres**) | `/dashboard/wallets` | `GET /portfolio/wallets` |
| Ayarlar (hesap özeti + MFA durumu + dil + biyometrik toggle + çıkış) | `/dashboard/settings` + `/security` | `/user/me`, `/mfa/status` |

### M2 — Finans modülleri + manuel giriş
- Harcamalar (`/expenses`) — liste + ekle + ay seçici + kategori pasta.
- Gelir (`/income`) — liste + recurring + realize.
- Bütçe (`/budget`), Planlı (`/planned`), Kredi kartları (`/credit-cards`).
- Manuel kripto (`/manual-crypto`) + asset catalog autocomplete.
- Snapshot tetikleme (`POST /portfolio/snapshot`).

### M3 (sonraya) — düşük öncelik / mobile-bağımlı
- Kıymetli madenler, nakit/banka, nakit akışı projeksiyonu (grafik ağır), finansal hedef, BES.
- Excel/MKK import (mobilde dosya seçici; düşük frekanslı kullanım → sonraya).
- AI tavsiye (`/advice/generate`) — kredi tüketimli; consent + 402 akışı M2/M3.

**Kural:** ağır tablo/import içeren web sayfaları mobilde **özet + "web'de aç"** ile başlar; tam paritede
acele edilmez.

---

## 8. Backend Mobil Önkoşulları

### 8.1 B3 Pagination — geriye-uyumlu / opt-in strateji ⚠️
**Sorun:** `/expenses /incomes /wallets /planned-expenses` şu an `list[T]` döner ve **aktif web frontend'i
bunu tüketir** (docs/04). Naif `list[T]` → `PaginatedResponse[T]` değişikliği **web'i kırar** (frontend
`items/total_count` beklemez).

**Önerilen strateji — opt-in query parametresi (kırılmasız):**
- Endpoint, **`limit`/`offset` query parametresi gelmediğinde eski davranışı** korur (`list[T]`), web
  istemcisi değişmeden çalışır.
- `limit`/`offset` **verildiğinde** `PaginatedResponse[T]` (`schemas/pagination.py`, audit-logs deseni)
  döner. Mobil her zaman `limit`/`offset` gönderir → sayfalı yanıt alır.
- Response model `Union[list[T], PaginatedResponse[T]]` (OpenAPI'de belgelenir).
- **Geçiş planı:** web istemcisi zamanla pagination'a taşınınca (docs/04 teknik borç), eski dalı kaldırma
  ayrı/sonraki iş olarak değerlendirilir — **bu fazda kaldırılmaz**.
- **Alternatif (kabul edilmedi):** ayrı `/v2/...` uçları → bakım yükü iki katına çıkar, tek geliştiriciye
  uygun değil. Opt-in query tercih edildi.
- **Mimari karar gereği:** B3, roadmap'te ayrı bir P1 işidir (`backend-expert` + `dba` index). Mobil bunu
  **bağımlılık** olarak işaretler; mobil M2'den önce tamamlanmalı (M1 yalnız portfolio/history/wallets
  okur, pagination'a sıkı bağımlı değil — M1 B3'siz başlayabilir).

### 8.2 İnce payload (mobil veri tasarrufu + gizlilik)
- Cüzdan listesinde adres **zaten maskeli** döner (BACK-013 `field_serializer`, docs/07) — mobil için
  ek koruma gerekmez; tam xpub yalnız audit'li Excel export'ta.
- Mobil liste uçlarında **ağır/gereksiz alanların kırpılması** (örn. her satırda uzun geçmiş serisi yerine
  özet) `fields=` veya mobil-özel özet uçları ile değerlendirilir — **performans optimizasyonu, M2+**.
  M1 mevcut payload'larla çalışabilir.

### 8.3 A4 Bildirim (FCM/APNs) — M3, M1/M2 blocker değil
- Push için `device_tokens` tablosu + `POST /notifications/register-device` (FCM/APNs token) gerekir.
- A4 bildirim sistemi (roadmap §A4, Faz D2) **önce backend'de** kurulur; mobil push **tüketici**.
- iOS APNs sertifikası/anahtarı (Apple Developer) + Android FCM projesi (Firebase) M3 önkoşulu.
- **Bu fazda yalnız tasarım notu**; implementasyon M3'e ertelendi.

---

## 9. i18n Stratejisi

**Mevcut:** web `app/_i18n/dictionaries/{tr,en}.json` (her ikisi 953 satır senkron, namespace'li:
`auth, common, dashboard, table, ...`; docs/04 §8.5).

**Karar: paylaşılan anahtar uzayı, türetilmiş yükleme (ayrı ayrı kopyalama DEĞİL).**
- Mobil, web sözlüklerinin **aynı anahtar düzenini** (dot-notation: `auth.login`, `dashboard.total`)
  benimser → tek terminoloji, çift bakım yok.
- **Yöntem:** web JSON'larını mobil `assets/i18n/{tr,en}.json` olarak kullanan bir **build adımı**
  (basit kopya/dönüştürme script'i, `mobile/` CI'ında). Flutter tarafı `flutter_localizations` +
  `flutter gen-l10n` ARB yerine, hafif bir JSON-tabanlı çözüm (web'deki "next-intl değil, kendi hafif
  çözümü" felsefesiyle aynı) ile yükler — `useTranslation()`'ın Dart karşılığı bir `tr(key)` fonksiyonu.
- **Yalnız-mobil anahtarlar** (biyometrik, push izin metinleri, store açıklamaları) ayrı `mobile.*`
  namespace'inde tutulur; web sözlüğünü kirletmez.
- **Tek kaynak doğruluğu (single source of truth):** TR/EN metin değişimi web JSON'da yapılır → mobil
  build kopyalar. İki ayrı sözlük tutmak (anlam kayması riski) reddedildi.

---

## 10. Güvenlik

| Önlem | Karar | Not |
|-------|-------|-----|
| **Secure storage** | ✅ Zorunlu | `flutter_secure_storage` → Keychain/Keystore; refresh token OS-korumalı (web localStorage XSS açığı tekrarlanmaz). |
| **MFA TOTP** | ✅ Reuse | Backend hazır; mobil yalnız 2-adımlı login'i tüketir (§6.1). |
| **Biyometrik kilit** | ✅ Opt-in | `local_auth`; açılış kilidi (§6.3). |
| **TLS** | ✅ Zorunlu | `.app` TLD HSTS preload (CLAUDE.md) — yalnız HTTPS; cleartext kapalı. Android `usesCleartextTraffic=false`. |
| **Certificate pinning** | ⚠️ Değerlendirildi — **opt-in, dikkatli** | Let's Encrypt sertifikası **90 günde bir döner**; kök/ara sertifika de değişebilir → naif leaf-pin uygulamayı kırar. **Karar:** ya pin **YOK** (HSTS preload + sistem trust store yeterli kabul), ya da **ara CA (intermediate) public-key pin** + kısa zorlama + uzaktan kapatma anahtarı (kill-switch). MVP'de **pinleme yok**; M3'te risk/efor değerlendirmesiyle eklenebilir. Yanlış pin = "kullanıcı kilitlenmesi" riski yüksek. |
| **Jailbreak / root tespiti** | ⚠️ Opsiyonel | `flutter_jailbreak_detection`/benzeri ile tespit + uyarı (engelleme değil). Düşük öncelik; kararlı pozitif değil. M3+. |
| **Screenshot / ekran kaydı engelleme** | ✅ Hassas ekranlarda | Android `FLAG_SECURE` (portföy/cüzdan/MFA recovery ekranları); iOS'ta ekran kaydı/overlay'de bulanıklaştırma. Recovery kodlarının gösterildiği ekran öncelikli. |
| **Sanitized hata** | ✅ Reuse | Backend `{detail, code, request_id}` (docs/07); mobil trace göstermez. |
| **PII log** | ✅ | Mobil loglarda token/email maskeleme; release build'de verbose log kapalı (web PIIFilter muadili). |

---

## 11. CI/CD

### 11.1 Konum: GitLab CI primary (mevcut `.gitlab-ci.yml` deseni)
- Proje **GitLab-primary** (CLAUDE.md). Mobil pipeline da GitLab CI'da; tetik **dizin-bazlı**
  (`mobile/**` değişince çalışır, backend/frontend pipeline'ını tetiklemez).
- Aşamalar (web/backend deseniyle hizalı): `analyze` (`flutter analyze` + `dart format --set-exit-if-changed`)
  → `test` (`flutter test` unit+widget, coverage) → `build` → (`scan`/store).

### 11.2 Android (GitLab self-hosted runner — Linux)
- Mevcut K8s/Kaniko runner Linux; **Android APK/AAB build Linux'ta mümkün** (Flutter + Android SDK image).
- **İmzalama:** upload keystore (`.jks`) **asla repo'ya girmez** → SealedSecrets / CI masked variable
  (CLAUDE.md GitOps secret deseni). `key.properties` CI'da enjekte edilir.
- Çıktı: Play Store için **AAB** (Android App Bundle); internal test track'e Fastlane `supply` ile yükleme.

### 11.3 iOS (macOS runner zorunlu)
- **iOS build Linux'ta İMKANSIZ** → ya **Codemagic** (Flutter-odaklı, macOS runner dahil, kolay) ya da
  bulut macOS runner (GitHub-hosted macOS — ama GitHub Actions flagged, çalışmaz; MacStadium/kendi Mac'i).
- **Karar:** iOS için **Codemagic** önerilir (Flutter ekosisteminde standart, macOS + imzalama + TestFlight
  yükleme yerleşik); Android da Codemagic'e taşınabilir → tek mobil CI sağlayıcı seçeneği masada.
  Alternatif: Android GitLab'da, iOS Codemagic'te (ayrık).
- **İmzalama (iOS):** Apple Developer hesabı ($99/yıl) + sertifika/provisioning profile (Fastlane `match`);
  TestFlight → App Store.

### 11.4 Dağıtım kanalları
- Android: Play Internal Testing → Closed → Production.
- iOS: TestFlight → App Store review.

---

## 12. Fazlama ve Efor

> Tek geliştirici + uzman ajan desteği. Süreler kaba; bağımlılık sırası bağlayıcı.

### Mobil M1 — Auth + Read-only Portföy (**~2-3 hafta**)
- Flutter ortam kurulumu (§2) + `mobile/` iskelet + Riverpod + go_router + dio interceptor (§3-5).
- Login + MFA 2. adım + secure storage + biyometrik kilit (§6).
- Dashboard özeti + snapshot geçmişi grafiği + cüzdanlar (maskeli) + ayarlar (§7 M1).
- i18n web sözlüğü reuse (§9) + Android CI (analyze/test/build) + internal test track.
- **B3 bağımlılığı:** M1 portfolio/history/wallets okur → B3'süz başlayabilir.

### Mobil M2 — Finans Modülleri + Manuel Giriş (**~3-4 hafta**)
- Harcama/gelir/bütçe/planlı/kredi kartları/manuel kripto ekranları (§7 M2).
- Form + CRUD + ay seçici + pasta grafik (web pattern karşılıkları).
- **B3 pagination önkoşulu burada zorunlu** (büyük liste → sayfalama) — §8.1 opt-in strateji.
- İnce payload optimizasyonu (§8.2).

### Mobil M3 — Bildirim + Biyometrik Tamamlama + Store Yayın (**~3-4 hafta + review süreleri**)
- A4 FCM/APNs push entegrasyonu (§8.3) — backend A4 tamamlanmış olmalı.
- Kalan ekranlar (madenler/nakit/hedef/BES/AI tavsiye) + screenshot engelleme + (ops.) cert pinning/root tespit.
- **iOS:** macOS/Codemagic devreye → TestFlight → App Store review.
- **Android:** Play Production review.
- AI tavsiye (kredi + 402 + consent) akışı.

**Toplam kaba tahmin:** ~8-11 hafta saf geliştirme + store review/iOS macOS lojistiği (takvim olarak daha uzun).

---

## 13. Riskler

| Risk | Etki | Azaltma |
|------|------|---------|
| **iOS için macOS zorunlu** | Windows-only makinede iOS build/imzalama yapılamaz | Codemagic (bulut macOS) veya bir Mac edin; M1/M2 Android-öncelikli ilerle. |
| **Apple Developer hesabı $99/yıl + review** | iOS yayını maliyet + gecikme | M3 öncesi hesap aç; TestFlight ile erken review riski azalt. |
| **Play Store + App Store review reddi** | Yayın gecikmesi | Gizlilik beyanı (KVKK), izin gerekçeleri (`NSFaceIDUsageDescription`, biyometrik), finans uygulaması ek inceleme; erken internal/TestFlight. |
| **B3 backend payload değişikliği web'i kırar** | Regresyon | **Opt-in query** stratejisi (§8.1) — `limit`/`offset` yoksa eski `list[T]`; web değişmeden çalışır. |
| **Refresh rotation + eşzamanlı 401** | Yanlış implementasyon → gereksiz logout | Single-flight refresh (§5.3) — web `_refreshInflight` deseninin Dart karşılığı; entegrasyon testiyle doğrula. |
| **Certificate pinning Let's Encrypt 90-gün rotasyonunda kilitlenme** | Kullanıcılar uygulamaya giremez | MVP'de pin YOK; eklenirse intermediate-CA pin + kill-switch (§10). |
| **GitHub Actions flagged** (CLAUDE.md) | macOS bulut runner GitHub'da çalışmaz | iOS CI = Codemagic; GitHub'a bağımlanma. |
| **Tek geliştirici + XL efor** | Takvim kayması | Kademeli M1→M2→M3; M1 hızlı kazanım (read-only) ile erken değer. |
| **KVKK / store gizlilik beyanı** | Yayın engeli | `compliance-expert` ile mobil gizlilik politikası + veri toplama beyanı (push token, biyometrik yerel) M3 öncesi. |

---

## 14. Delegasyon Haritası (uygulama aşaması)

Bu tasarım onaylanınca alt görevler uzmanlara yönlendirilir (mimar → uzman):

| Alt görev | Ajan |
|-----------|------|
| B3 pagination opt-in (4 endpoint) + index | `backend-expert` + `dba` |
| İnce payload / mobil-özet uçları | `backend-expert` |
| A4 bildirim altyapısı (device_tokens, FCM/APNs) | `backend-expert` |
| Mobil dio interceptor / refresh single-flight / secure storage güvenlik incelemesi | `security-expert` |
| Certificate pinning / biyometrik / store gizlilik kararı | `security-expert` + `compliance-expert` |
| Mobil CI (GitLab Android + Codemagic iOS, imzalama) | `devops` |
| Flutter ekran implementasyonu (Riverpod/go_router) | (yeni `mobile-expert` veya `frontend-expert` mobil kapsamı) |
| Mobil i18n sözlük türetme | `frontend-expert` (web sözlük sahibi) |
| KVKK mobil gizlilik politikası + izin metinleri | `compliance-expert` |
| Bu doküman + roadmap güncellemesi | `doc-expert` |

> **Not:** Mobil için ya mevcut `frontend-expert` kapsamı genişletilir ya da yeni bir `mobile-expert`
> ajanı eklenir — bu, mimari değişiklik kriteri (yeni uzman) olduğundan onay gerektirir.

---

## 15. Açık Mimari Kararlar (Onay Bekleyen)

1. **`mobile-expert` ajanı eklensin mi**, yoksa `frontend-expert` mobil kapsam mı? (Delegasyon haritası etkilenir.)
2. **iOS CI sağlayıcısı:** Codemagic (her iki platform) mi, Android-GitLab + iOS-Codemagic ayrık mı?
3. **B3 opt-in** kabul mü, yoksa `/v2` ayrımı mı? (Bu doküman opt-in öneriyor — §8.1.)
4. **Certificate pinning** M1'de yok kararı kabul mü? (§10 — Let's Encrypt rotasyon riski nedeniyle önerilmedi.)
5. Mobil M1 başlamadan **B3 + A4 sırası:** M1 B3'süz başlar, M2 B3 ister, M3 A4 ister — bu sıralama onaylanıyor mu?
