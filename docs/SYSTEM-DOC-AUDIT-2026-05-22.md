# KFinans Dokümantasyon Sistemi — Kapsamlı Audit (2026-05-22)

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

> **Bağlam:** 2026-05-21 büyük audit fix turu (13 commit; PII mask, MultiFernet, zxcvbn, HIBP,
> DB TLS, age backup, etcd at-rest, 7 NetworkPolicy, MFA TOTP, ROFS, SealedSecrets, Postgres
> selfsigned cert, GitLab CI primary). Production rc7 canlı; backend TLSv1.3 ile postgres'e
> bağlı, MFA endpoint canlı.
>
> **Amaç:** Dokümantasyonun bu mimari/güvenlik değişikliklere ne ölçüde yetiştiğini ölçmek;
> **6 kavram** (Tasarım, Uygulama, Bakım, Kullanım, Yedekleme, Güvenlik) × **3 prensip**
> (Best Practice, Reusability, Portability) lensiyle eksik/çelişkili/atıl bölümleri tespit etmek;
> reorganize + güncelle + yeni doc oluşturma planını netleştirmek.
>
> **Kapsam dışı:** Bu raporda **kod değişikliği yok**. Sadece doküman create/update/merge/delete
> önerileri + analiz.

---

## 0. Yönetici Özeti

| Boyut | Durum | Aksiyon |
|-------|-------|---------|
| **Tasarım belgeleri** (01–02, 06) | Versiyon ve içerik drift'i var (`01-tasarim-dokumani.md` v4.3 / 2026-05-10; SealedSecrets/MFA/NetworkPolicy yansımamış) | UPDATE |
| **Uygulama belgeleri** (03–05) | API ref MFA endpoint'lerini içermiyor; rate limit tablosu MFA içermiyor | UPDATE |
| **Bakım belgeleri** (09 + runbook + checklist) | İçerikleri kısmen örtüşüyor; on-call / DR drill / incident-runbook seviyesinde işletim kılavuzu yok | UPDATE + NEW |
| **Kullanım belgesi** | End-user guide yok; `README.md` "Özellikler" listesi var ama feature-by-feature kullanım yönergeleri yok | NEW (önerilen) |
| **Yedekleme belgesi** | `infrastructure-runbook.md §5.3` + `k8s/README.md` `backup-cronjob.yaml` mevcut; ama DR drill / RTO-RPO hedefleri / restore step-by-step yok | NEW (`disaster-recovery.md`) |
| **Güvenlik belgesi** (07) | Doc 2026-05-10 öncesi formda; **2026-05-21 audit fix turunun 9 ana kalemi (MultiFernet, zxcvbn, HIBP, DB TLS, age backup, etcd at-rest, 7 NetworkPolicy, MFA TOTP, ROFS) hâlâ yansımamış** | UPDATE (kritik) |
| **Atıl belgeler** | `github-support-followup-2026-05-12.md` (flag #4360519 kalktı; tek sayfalık atıl); `release.yml` referansları (workflow silindi) | DELETE / MERGE |
| **Mimari belgeler içindeki çelişkiler** | (a) `docs/02-mimari.md` "nginx-ingress" diyor → gerçek **Traefik** (K3s default); (b) `09-altyapi-test.md` "5/6 workflow" diyor → gerçek **GitLab CI primary, GitHub Actions atıl**; (c) `01-tasarim-dokumani.md` "Faz 3 devam" → audit-2026-05-21 sonrası "Faz F prod deploy aktif" | UPDATE |

**Toplam dokümantasyon büyüklüğü:** 9 ana belge (~285KB) + 2 ops belgesi (~20KB) + backlog/legal/k8s/módül README'ler (~70KB). 50K karakter mertebesinde yenileme ihtiyacı var; çoğu **sürgül delta** (mevcut bölümlere ek), 3 yeni belge ~20K karakter.

---

## 1. Belge-Belge Analiz

### 1.1 `docs/01-tasarim-dokumani.md` (40KB, v4.3, 2026-05-10)

**Durum:** GÜNCELLEME GEREK.

**Eksikler / drift:**
- Versiyon header'ı 4.3 / 2026-05-10 — 2026-05-21 audit fix turundan haberdar değil.
- "Faz Planı" tablosunda Faz F (production rollout) henüz "Planlı" yazıyor; gerçekte rc7 canlı (kfinans.app).
- Faz H sonu **FAZ I — Audit Fix Turu (2026-05-21)** olarak eklenmemiş.
- `docs/02-mimari.md` referansı **`./mimari.md`** olarak yanlış (gerçek: `./02-mimari.md`); aynı hata 6 link için var.

**Önerilen güncelleme:**
- Versiyon 4.4 / 2026-05-22; "Faz I — Audit Fix (tamam)" satırı ekle.
- Doküman link'lerini `./0X-...md` formatına çevir (md link rot fix).
- "Production Durum" üst başlığı ekle: rc7 canlı, MFA aktif, 7 NetworkPolicy, postgres TLSv1.3, age backup.

### 1.2 `docs/02-mimari.md` (65KB)

**Durum:** GÜNCELLEME GEREK.

**Eksikler / drift:**
- Bölüm 2 mimari diyagramında **"nginx-ingress + cert-manager"** yazıyor (~satır 44). Gerçekte **Traefik** kullanılıyor (K3s default; `k8s/README.md` "Traefik CRD'leri Middleware için gerekli" doğrular).
- Postgres StatefulSet diyagramda `replicas: 1`, 50Gi PVC — şu an ayrıca **postgres-cert.yaml** ile selfsigned TLS cert mount edildi; mimari diyagramda yok.
- Mimari diyagramında **SealedSecrets controller (`kube-system`)** + **Bitnami sealed-secrets** yok.
- **NetworkPolicy katmanı** (default-deny + 6 allowlist) mimari diyagrama eklenmemiş.

**Önerilen güncelleme:**
- Diyagramı **Traefik** + **cert-manager** + **SealedSecrets** + **NetworkPolicy** + **Postgres-with-TLS** ile yenile.
- "Modüler Monolit Karar Çerçevesi" tablosunun altına **Faz I değişiklikleri**: TLS sertifika dağıtımı (cert-manager selfsigned vs Let's Encrypt), 7 NetworkPolicy hedefleri.

### 1.3 `docs/03-api-referansi.md` (51KB)

**Durum:** GÜNCELLEME GEREK (kritik — MFA endpoint'leri canlı ama doc'ta yok).

**Eksikler:**
- **MFA endpoint'leri yok:** `POST /auth/mfa/setup`, `POST /auth/mfa/verify`, `POST /auth/mfa/disable`, `POST /auth/login` için `mfa_code` zorunlu hale geldiğinde response/422 değişimi yok.
- **HIBP password policy:** `/auth/register` ve `/auth/password-change` artık zxcvbn ≥3 + HIBP k-anonymity ile guard'lı; 422 dönen yeni hata kodu doc'ta yok.
- **MultiFernet key rotation:** Endpoint değil ama "API key encrypted_key" başlığı altında rotation prosedürü belirtilmemiş.
- Rate limit tablosuna **MFA setup/verify** satırları eklenmeli (5/dk + 10/dk önerisi).
- "1.3 Standart HTTP Kodları" tablosuna `423 Locked` (account lockout — zaten kod, doc'ta yok) ve `403 Forbidden` (MFA gerekli ama eksik) eklenmeli.

**Önerilen güncelleme:**
- Yeni **§3.X MFA (TOTP)** alt başlığı: setup/verify/disable + recovery code + rate limit.
- "Şifre Politikası" başlığı: zxcvbn ≥3 + HIBP k-anonymity (`SHA-1(password)[:5]` pwnedpasswords.com sorgusu).

### 1.4 `docs/04-frontend.md` (27KB)

**Durum:** KÜÇÜK GÜNCELLEME.

**Eksikler:**
- MFA setup UI akışı yok (TOTP QR code, recovery code).
- `confirm()` → ConfirmDialog refactor yer alıyor (✓), ama CSP nonce revert geri alımı yansıtılmamış (`f963d7b revert(csp)`).

**Önerilen güncelleme:**
- "MFA Setup UI" alt başlığı: QR + recovery + rate limit handling.
- "CSP nonce-based middleware geri alındı (build patladi)" notu — gelecek tasarım borcu.

### 1.5 `docs/05-ai-ve-finans.md` (16KB)

**Durum:** GÜNCEL (küçük rötuş).

**Eksikler:**
- Şu an AI tavsiye motoru SPK uyumlu (AI-003, AI-008) ve credit_balance gate'i + slowapi 5/hour + atomic decrement var — `CHANGELOG.md`'de mevcut, doc'ta net değil.

### 1.6 `docs/06-kredi-sistemi.md` (14KB)

**Durum:** PLANLAMA AŞAMASINDA, OLDUĞU GİBİ KALSIN.

**Not:** iyzico entegrasyonu hâlâ Faz 3 placeholder. Kullanıcı tarafı tüketim (`/advice/generate` artık 1 credit) doc'a eklenebilir.

### 1.7 `docs/07-guvenlik.md` (25KB)

**Durum:** GÜNCELLEME GEREK (KRİTİK — Faz I audit fix turunun 9 ana güvenlik kalemi yansımamış).

**Eksikler (önemli sırayla):**
1. **MFA TOTP** — `/auth/mfa/*` endpoint'leri canlı; "Mevcut Korumalar" tablosunda yok; "Bilinen Açıklar §3.5" madde 4 (toplu logout) hâlâ açık.
2. **MultiFernet (key rotation)** — Şu an `cryptography.fernet.MultiFernet` kullanılıyor; "§5 API Key Şifreleme" tek-key Fernet anlatıyor. Key rotation prosedürü (yeni key → MultiFernet list başına ekle → mevcut ciphertext'ler okunabilir → cron migrate → eski key list'ten kaldır) doc'a girmeli.
3. **zxcvbn ≥3 + HIBP k-anonymity** — Şifre politikası "§3 Auth" altında yok. Yeni alt başlık şart.
4. **PII masking** (`celikada@gmail.com` → `c***@gmail.com`) — Log/audit_log/Sentry breadcrumb'larda. "§10 Loglama" altında yok.
5. **DB TLS (asyncpg ssl=prefer + cert-manager selfsigned)** — "§5 Şifreleme" Fernet'i anlatıyor; postgres TLSv1.3 hattı doc'ta yok.
6. **age asymmetric backup encryption** — `infrastructure-runbook.md §4` bahsediyor ama "§5.3 K8s Secrets" bölümünde backup encryption stratejisi yok.
7. **etcd at-rest encryption** — `K3s --secrets-encryption=true` veya EncryptionConfiguration. "§5.4 K8s Secrets Yerleşimi" altında ekleme şart.
8. **NetworkPolicy (7 policy: default-deny + DNS + backend-in/eg + frontend-in + postgres-in + backup-eg)** — "§8 Eksik Korumalar" altında "[ ] NetworkPolicy" varken artık tamamlandı. Mimari diyagram + her policy'nin amacı eklenmeli.
9. **readOnlyRootFilesystem (ROFS) + emptyDir mounts** — Pod securityContext sertleştirme. "§8.X Pod Security" başlığında yok.
10. **SealedSecrets (Bitnami)** — "§5.3 Kritik: Master Key Yönetimi" yalnızca "K8s Secret + sealed-secrets" diye geçici geçiyor; gerçek prosedür (kubeseal, master key backup, .credentials.local.md §8) `k8s/README.md` ve `infrastructure-runbook.md`'de var ama **`07-guvenlik.md` ana otorite olduğu için orada da olması şart**.

**Önerilen güncelleme:** Yeni "§14 — FAZ I: 2026-05-21 Audit Fix Turu" başlığı altında 10 madde + her birinin tehdit modelinde nereye oturduğu. "Mevcut Korumalar" tablosuna 10 yeni satır.

### 1.8 `docs/08-uyumluluk-kvkk.md` (20KB)

**Durum:** GÜNCEL (küçük rötuş).

**Eksikler:**
- Bölüm 3.1 "Yasal Belgeler" — placeholder'lar (`[TİCARİ ÜNVAN]`, `kvkk@kfinans.app`, `privacy@kfinans.app`) hâlâ var; `production-deploy-checklist.md` ile çapraz referans tutarlı, ama **MFA opsiyonel/zorunlu** kararı KVKK m.12/4 "veri güvenliği önlemi" olarak doc'ta belirtilmeli.

### 1.9 `docs/09-altyapi-test.md` (28KB)

**Durum:** GÜNCELLEME GEREK (GitHub Actions → GitLab CI geçişi yansımamış).

**Eksikler:**
- "1.2 CI Pipeline (Çalışıyor — 6 workflow)" — gerçekte **GitLab CI primary** (`.gitlab-ci.yml`), GitHub Actions release.yml **silindi** (`d400f3d ci: release.yml kaldir`). Workflow listesi yenilenmeli.
- "3. Production: Kubernetes" altında **NetworkPolicy 7 policy + SealedSecrets + Postgres TLS cert mount** yok.
- "3.4 Faz 3 TODO'ları" listesinde "NetworkPolicy" + "external-secrets/SealedSecrets" zaten **tamam** — listeden çıkarılmalı.
- "5. Test Stratejisi" backend test sayısı 159 (gerçek: ~357+ integration + 192+ unit; CLAUDE.md 192+357 diyor).
- **Kaniko build** ve **self-hosted GitLab runner + SonarQube** Mimari notu olarak eklenmeli (`gitlab.192.168.3.191.nip.io`, `sonar.192.168.3.191.nip.io`).

**Önerilen güncelleme:**
- "§4 CI/CD Pipeline" tamamen GitLab-first yeniden yaz; GitHub Actions sadece **CodeQL + Dependabot** olarak kalır.
- "§3.4 Faz 3 TODO" → "§3.4 Faz 4 TODO" (HPA, PDB, Prometheus, PgBouncer, off-cluster backup sync).

### 1.10 `docs/infrastructure-runbook.md` (13KB)

**Durum:** GÜNCELLEME GEREK.

**Eksikler:**
- "§3 Oracle Cloud VM + K3s" — **cert-manager selfsigned** (Postgres TLS için, `letsencrypt-prod` Ingress için), **sealed-secrets controller**, **NetworkPolicy 7 policy** yok.
- "§4 Periyodik Bakım" — **MultiFernet key rotation aylık/yıllık**, **DB cert auto-renewal 90 gün**, **MFA recovery code rotation** satırları yok.
- "§5 Acil Durum" — MFA bypass / kullanıcı kendi TOTP'sini kaybederse prosedür yok.
- "§7 Değişiklik Geçmişi" tablosu son güncellemeyi 2026-05-14 olarak gösteriyor (gerçek: 2026-05-21 rc7).

### 1.11 `docs/production-deploy-checklist.md` (7KB)

**Durum:** BİRLEŞTİRME ADAYI.

**Çelişkiler:**
- "§6 Oracle Cloud K3s" altında "DEVOPS-008 #54 NetworkPolicy" tamam görünüyor; aynı zamanda "etcd encryption" + "Pod Security Standards" da tamam — yani Faz I audit fix turu sonrası **çoğu satır ✓ hale geldi**.
- "§7 İlk deploy senaryosu" — `git tag v0.1.0` referansı: rc7 zaten canlı; **stable release tag v0.1.0** henüz çekilmediyse açıklayıcı not şart.

**Öneri:** Bu belge bir kez **"Faz F → tamamlandı, v0.1.0 RC süreç tutanak"** olarak `docs/releases/` alt klasörüne arşivlenebilir; veya `infrastructure-runbook.md` ile **birleştirilebilir** (tek deploy ops belgesi).

### 1.12 `docs/legal/incident-response-plan.md` (9KB)

**Durum:** GÜNCEL — IŞIK ROTÜŞ.

**Eksikler:**
- "§2 Roller" — MFA Recovery Code rotation IR sırasında zorunlu adım olarak eklenebilir.
- "§3 Tetikleyiciler" altında **NetworkPolicy log scan** (denied connection spike) yeni canary olarak listelenmeli.

### 1.13 `docs/backlog/audit-2026-05-08-summary.md` (24KB)

**Durum:** ARŞIVLEME ADAYI.

**Not:** 240 bulgu raporu — büyük çoğunluğu kapatıldı. Arşiv değeri yüksek (geçmiş kararlar için), ama **`backlog/` klasör adı yanıltıcı** (artık geçmiş). Öneri: `docs/audits/2026-05-08-faz-g-audit.md` olarak yeniden adlandır + üst başlığa "kapatıldı 2026-05-21" not düş.

### 1.14 `docs/backlog/sprint-plan.md` (5.5KB)

**Durum:** GÜNCEL DEĞİL — ARŞİVLE veya SİL.

**Not:** P0/P1/P2 issue listesi (40+ issue, çoğu kapatıldı). `audit-2026-05-08-summary.md` ile birlikte arşivleyelim. Aktif sprint planı (Faz I sonrası) için yeni `docs/roadmap.md` önerilebilir.

### 1.15 `docs/github-support-followup-2026-05-12.md` (3.6KB)

**Durum:** SİLINEBILIR.

**Not:** Flag #4360519 6 günlük followup mesaj taslağı. Geçici niteliği itibariyle commit'lenmemeliydi. Şu an GitLab CI primary olduğu için flag drama'sı çözüldü/önemsiz. Sil; gerekirse `docs/audits/2026-05-12-github-flag-archive.md` olarak tek satırlık not bırak.

### 1.16 `docs/README.md` (3KB)

**Durum:** GÜNCELLEME GEREK.

**Eksikler:**
- "İçindekiler" tablosunda **yeni 3 belge** (operations-playbook, disaster-recovery, user-guide) eklenmeli.
- "Diğer Belgeler" altında **portability-matrix.md** + **reusability-patterns.md** + **`audits/`** + **`releases/`** klasörleri eklenmeli.

---

## 2. Modül README'leri

### 2.1 `backend/README.md` (6.3KB)

**Durum:** KÜÇÜK GÜNCELLEME.

- "Proje Yapısı" listesinde router sayısı drift'i (21 router CLAUDE.md'de; backend README'de "router.py — Tüm router'ları birleştirir" var ama liste eksik MFA).
- "Mimari Kararlar" altına **MultiFernet rotation**, **MFA TOTP**, **DB TLS asyncpg ssl=prefer** eklenmeli.
- "Test" coverage hedefi `%50+` yazıyor — CLAUDE.md `%60 line + %50 branch + critical path %90` diyor. **Gerçek değerle senkronize** edilmeli.

### 2.2 `frontend/README.md` (5.5KB)

**Durum:** GÜNCEL.

**Eksik:** MFA setup sayfası `/dashboard/settings/mfa` (varsa) belirtilmeli; i18n-002 turn 5 (FE-013 ConfirmDialog) ve A11Y-001 yansıtılmış.

### 2.3 `k8s/README.md` (9KB)

**Durum:** EN GÜNCEL DOSYA (en yeni info burada). Diğer doc'lar bu dosyaya senkronize edilmeli.

- Bu doc artık SealedSecrets, NetworkPolicy referansları, postgres-cert.yaml, GitLab CI → Docker Hub flow'unu **doğru** anlatıyor.
- "Bilinen Eksikler / TODO" listesinde "NetworkPolicy" + "External-secrets / SealedSecrets" eskimişse temizlenmeli (gerçek: tamam).

### 2.4 `frontend/CLAUDE.md` (11 byte) + `frontend/AGENTS.md` (327 byte)

**Durum:** ÇOK MİNİMAL.

- `frontend/CLAUDE.md` tek satır — kök `CLAUDE.md`'ye merge edilebilir veya genişletilebilir.
- `frontend/AGENTS.md` — agent talimat formatında. Karışıklığı azaltmak için **tek bir `frontend/CLAUDE.md`'ye birleştir** ve `AGENTS.md` sil.

### 2.5 Kök `CLAUDE.md` (36KB)

**Durum:** EN GÜNCEL belge (2026-05-21 commit `8d751c0` öncesi). Çoğu bilgi burada doğru.

**Eksikler:**
- "Tech Stack" tablosunda **CI/CD: GitHub Actions** yazıyor — gerçek: **GitLab CI primary**, GitHub Actions sadece CodeQL+Dependabot.
- "Hosting" satırında "nginx-ingress" yazıyor — gerçek **Traefik**.
- "Güvenlik" satırına **MFA TOTP + MultiFernet + zxcvbn + HIBP + DB TLS + age backup + etcd at-rest + 7 NetworkPolicy + ROFS** eklenmeli.

---

## 3. Çelişkiler (Doc-Doc + Doc-Kod)

| # | Yer | Çelişki | Çözüm |
|---|----|---------|-------|
| C1 | `02-mimari.md` Bölüm 2 ↔ `k8s/README.md` Ön Koşullar | "nginx-ingress" vs "Traefik" | `02-mimari.md` → Traefik |
| C2 | `09-altyapi-test.md` §1.2 ↔ `.gitlab-ci.yml` | "6 workflow GitHub" vs "GitLab CI primary" | `09-altyapi-test.md` yeniden yaz |
| C3 | `01-tasarim-dokumani.md` link'leri (`./mimari.md`) ↔ gerçek dosya isimleri (`./02-mimari.md`) | Link rot — 6 link bozuk | Tüm link'leri `./0X-...md`'e çevir |
| C4 | `07-guvenlik.md` §5.4 "SealedSecrets — Faz 3 hedefi" ↔ `k8s/sealed-secrets.yaml` (canlı) | "Hedefi" → "Aktif" | §5.4 güncel duruma çek |
| C5 | `07-guvenlik.md` §8.X "NetworkPolicy [ ]" ↔ `k8s/networkpolicies/` (7 policy canlı) | Eksik → Tamam | §8 tamam işaretle |
| C6 | `03-api-referansi.md` §1.4 Rate Limit tablosu ↔ MFA endpoint'leri | Eksik | MFA satırları ekle |
| C7 | `CLAUDE.md` "Tech Stack" CI/CD ↔ `.gitlab-ci.yml` | GitHub Actions vs GitLab | CLAUDE.md → "GitLab CI primary" |
| C8 | `infrastructure-runbook.md` §1.3 Namecheap 2FA: "⏳ Faz D3" ↔ project memory `project_namecheap_pending_security.md` | Faz D3 geçti, bekleniyor | Status: "Bekliyor — post-Faz F" |
| C9 | `02-mimari.md` Postgres "StatefulSet 50Gi" ↔ `k8s/postgres-cert.yaml` mount + cert TLSv1.3 | Cert mount yok | Diyagrama + manifest açıklamasına ekle |
| C10 | `production-deploy-checklist.md` §6 "[ ] etcd encryption-at-rest" ↔ commit `ce3b9fc` (audit#4 tamam) | Eksik → Tamam | ✓ işaretle |
| C11 | `01-tasarim-dokumani.md` versiyon 4.3 / 2026-05-10 ↔ CLAUDE.md son güncelleme 2026-05-21 | 11 gün drift | Versiyon 4.4 / 2026-05-22 |
| C12 | `09-altyapi-test.md` §5.2 backend test sayısı "159" ↔ CLAUDE.md "192 unit + 357 integration" | Eski sayı | "192+357 = 549" güncelle |

---

## 4. Reorganize / Birleştirme / Silme Önerileri

### 4.1 SİLİNECEK / ARŞİVLENECEK
| Dosya | Aksiyon | Gerekçe |
|-------|---------|---------|
| `docs/github-support-followup-2026-05-12.md` | **SİL** | Mesaj taslağı; flag drama bitti; commit'lenmemeliydi |
| `docs/backlog/audit-2026-05-08-summary.md` | **TAŞI** → `docs/audits/2026-05-08-faz-g-audit.md` | Geçmiş audit raporu; arşiv değeri |
| `docs/backlog/sprint-plan.md` | **TAŞI** → `docs/audits/2026-05-08-sprint-plan.md` veya **SİL** | P0/P1 bitti; ya arşiv ya sil |
| `docs/backlog/` klasörü | **YENİDEN ADLANDIR** → `docs/audits/` veya **SİL** (içerik taşınınca) | İsmi yanıltıcı |
| `frontend/AGENTS.md` | **BIRLEŞTIR** → `frontend/CLAUDE.md` | Tek CLAUDE.md zaten standart |

### 4.2 BİRLEŞTIRME ADAYLARI (opsiyonel — yapılırsa)
| Kombo | Hedef | Karar |
|-------|-------|-------|
| `infrastructure-runbook.md` + `production-deploy-checklist.md` | Tek "ops belgesi" | **AYRI TUT.** Birincisi periyodik bakım (zaman-bağımsız), ikincisi tek-seferlik prod cutover. Karıştırılırsa ikisi de zayıflar. |
| `backend/README.md` + `frontend/README.md` + `k8s/README.md` + kök `CONTRIBUTING.md` | Tek mega README | **AYRI TUT.** Modül README'leri quickstart için ayrı kalsın; `CONTRIBUTING.md` PR/branch flow için tek otorite. |

### 4.3 YENİ KLASÖR YAPISI ÖNERİSİ

```
docs/
├── README.md                       # ana index (güncellenmiş)
├── 01-tasarim-dokumani.md          # (UPDATE)
├── 02-mimari.md                    # (UPDATE)
├── 03-api-referansi.md             # (UPDATE — MFA + HIBP)
├── 04-frontend.md                  # (UPDATE — MFA UI)
├── 05-ai-ve-finans.md              # (rotüş)
├── 06-kredi-sistemi.md             # (rotüş)
├── 07-guvenlik.md                  # (KRİTİK UPDATE — Faz I)
├── 08-uyumluluk-kvkk.md            # (rotüş)
├── 09-altyapi-test.md              # (UPDATE — GitLab CI)
│
├── operations/                     # YENİ KLASÖR
│   ├── infrastructure-runbook.md   # (TAŞI + UPDATE)
│   ├── production-deploy-checklist.md  # (TAŞI)
│   ├── operations-playbook.md      # YENİ: on-call, alerting, common troubleshooting
│   └── disaster-recovery.md        # YENİ: DR drill, RTO/RPO, backup restore step-by-step
│
├── reference/                      # YENİ KLASÖR
│   ├── user-guide.md               # YENİ: end-user sayfa-bazlı feature açıklaması
│   ├── portability-matrix.md       # YENİ: vendor lock-in noktaları + alternatif provider
│   └── reusability-patterns.md     # YENİ: BaseIntegration, masking, MultiFernet patterns
│
├── audits/                         # YENİ KLASÖR (eski "backlog/" yerine)
│   ├── 2026-05-08-faz-g-audit.md   # (TAŞI)
│   ├── 2026-05-21-faz-i-security-fix.md   # YENİ: 2026-05-21 audit fix turu kayıt tutanağı
│   └── SYSTEM-DOC-AUDIT-2026-05-22.md     # (BU DOSYA — taşı buraya)
│
└── legal/
    └── incident-response-plan.md   # (rotüş)
```

### 4.4 Aksiyon: bu reorganize yapılırsa **`docs/README.md`** "İçindekiler" tablosu tamamen yeniden yazılmalı.

---

## 5. Yeni Dokümanlar — Taslak Yapı

### 5.1 `docs/operations/operations-playbook.md` (Yeni)

> **Amaç:** Günlük/haftalık/aylık ops rutinleri, on-call müdahale, yaygın troubleshooting senaryoları.

**Bölümler:**
1. **On-Call Tanımı** — IC + Teknik Lead rolleri, 30 dk first ack, telefon/SMS pager
2. **Günlük Sağlık Kontrolü** (sabah 5 dk):
   - `kubectl get pods -n kfinans` — pod restart > 0 mı?
   - `kubectl get certificate -A` — cert Not After > 30 gün
   - Sentry dashboard error rate normal mı?
   - SonarQube quality gate yeşil mi?
3. **Haftalık Bakım** — Pazar 23:00 snapshot başarılı mı? Backup CronJob log
4. **Aylık Bakım** — Postgres backup integrity check (random restore), DNS propagasyon
5. **Alerting Setup** — Sentry alert kuralları (500 spike, slow request, MFA bypass attempt), Prometheus + Alertmanager (Faz 4)
6. **Yaygın Troubleshooting**:
   - "Site yavaş" → X-Response-Time header / PERF-004 metrik → DB slow query → `pg_stat_statements`
   - "Email gitmiyor" → Resend dashboard logs → DKIM TXT propagasyon
   - "Pod CrashLoopBackOff" → `kubectl logs --previous` → migration fail / SecretsNotFound
   - "Backup fail" → age private key valid mı, PVC dolmuş mu
   - "Backend → Postgres TLS fail" → cert-manager renewal, asyncpg ssl=prefer fallback
7. **Common kubectl Tarifleri** — secret rotation, image rollback, cert force renewal
8. **Escalation Path** — IC ulaşılamazsa, hangi sırayla?

**Tahmini boyut:** ~6KB

### 5.2 `docs/operations/disaster-recovery.md` (Yeni)

> **Amaç:** Tam disaster (DB corruption, node loss, ransomware, secret leak) durumunda restore prosedürü; yıllık DR drill.

**Bölümler:**
1. **RTO / RPO Hedefleri**
   - RTO (Recovery Time Objective): **4 saat** (ilk MVP; Faz 4: 1 saat)
   - RPO (Recovery Point Objective): **24 saat** (günlük backup; Faz 4: 6 saat PITR)
2. **Backup Envanteri**
   - Postgres `pg_dump` günlük 02:00 → `postgres-backups` PVC (5Gi, 30 gün)
   - age asymmetric encryption (`backup-cronjob.yaml`)
   - SealedSecrets master key offline backup (`.credentials.local.md §8`)
   - Fernet master key offline backup (USB + Bitwarden)
3. **Backup Test (Yıllık DR Drill)**
   - Ocak ayı — table-top + canlı restore deneme (staging cluster)
   - Test senaryoları: (a) tek pod kaybı, (b) DB volume corruption, (c) tam cluster kaybı
4. **Step-by-Step Restore Prosedürleri**
   - **A. Sadece DB corruption (cluster sağ)**: pod restart → backup gunzip → psql restore → migration upgrade head doğrula → smoke
   - **B. Tam cluster kaybı (Oracle VM sıfırdan)**: K3s reinstall → cert-manager kurulum → sealed-secrets controller + master key import → `kubectl apply -k k8s/` → backup PVC mount → restore → DNS doğrulama
   - **C. Secret leak (Fernet master key sızdı)**: 1. yeni Fernet key üret, 2. MultiFernet list başına ekle (eski hâlâ decrypt için), 3. tüm encrypted_key/wallet xpub re-encrypt cron, 4. eski key list'ten kaldır
   - **D. SealedSecrets controller kaybı**: master key restore → controller redeploy → SealedSecret manifest'ler decrypt edilir
5. **Out-of-Cluster Backup Stratejisi** (Faz 4)
   - Oracle Object Storage (S3-compatible) sync — backup-cronjob.yaml job sonrası
   - pgBackRest PITR (~1 hafta WAL retention)
6. **Communication Plan** — Kullanıcıya status page (statuspage.io / GitHub Status), email blast, RTBT (return-to-business-time) tahmin paylaşımı

**Tahmini boyut:** ~8KB

### 5.3 `docs/reference/user-guide.md` (Yeni)

> **Amaç:** Son kullanıcı dokümantasyonu. Her dashboard sayfasının ne yaptığı, hangi veri kaynağı, nasıl import.

**Bölümler:**
1. **Hızlı Tur** — Login → register → email verify → dashboard
2. **Sayfa-Bazlı Rehber** (17 dashboard sayfası):
   - `/dashboard/tefas` — fon ekleme, MKK Excel import, maliyet bazı
   - `/dashboard/stocks` — hisse ekleme, BIST/.IS suffix, Yahoo Finance fallback
   - `/dashboard/wallets` — 10 zincir, xpub vs adres, blockchain veri kaynakları
   - `/dashboard/crypto` — Binance/iCrypex API key, read-only şart
   - `/dashboard/manual-crypto` — API'siz borsalar (BinanceTR/BTCTurk), 3 fiyat modu (auto/manual/linked)
   - `/dashboard/bes` — manuel giriş + Excel
   - `/dashboard/commodities` — XAU/XAG, gram/BiGA/sikke
   - `/dashboard/expenses`, `/dashboard/income`, `/dashboard/budget`, `/dashboard/planned`, `/dashboard/cash`, `/dashboard/cash-flow`, `/dashboard/credit-cards`, `/dashboard/goal`
   - `/dashboard/history` — snapshot grafikleri, TL/USD toggle, xlsx/pdf rapor
   - `/dashboard/settings` — şifre, MFA setup, hesap silme, kart gizleme
3. **KVKK Hakları Kılavuzu** (kullanıcı tarafından kullanım):
   - Veri dışa aktarma (`/user/data-export` → JSON)
   - Hesap silme (soft-delete + 30 gün hard-delete cron)
   - Anthropic açık rıza geri çekme
4. **Sık Sorulanlar** — şifre unutma akışı, MFA recovery code, e-posta değiştirme

**Tahmini boyut:** ~10KB

### 5.4 `docs/reference/portability-matrix.md` (Yeni)

> **Amaç:** Vendor lock-in noktalarını şeffaf hale getir; multi-cloud migration için checklist.

**Bölümler:**
1. **Lock-in Heat Map**

   | Bileşen | Şu anki | Lock-in | Alternatif | Migration Effort |
   |---------|---------|---------|------------|-------------------|
   | Compute | Oracle Cloud Always Free VM | 🟡 Orta | AWS EC2 t4g, GCP e2-micro, Hetzner | Düşük (cloud-init + K3s) |
   | Kubernetes | K3s | 🟢 Düşük | vanilla K8s, EKS, GKE | Düşük (manifest portable) |
   | Ingress | Traefik (K3s default) | 🟢 Düşük | nginx-ingress, AWS ALB | Düşük (Ingress spec standart) |
   | DB | Postgres StatefulSet (in-cluster) | 🟢 Düşük | AWS RDS, GCP Cloud SQL, Supabase | Düşük (dump/restore) |
   | TLS Cert | cert-manager Let's Encrypt | 🟢 Düşük | AWS ACM, GCP managed cert | Orta |
   | Backup | age + local PVC | 🟡 Orta | Oracle Object Storage, AWS S3, B2 | Orta |
   | Container Registry | Docker Hub | 🟡 Orta | GHCR, AWS ECR, GCP Artifact Registry | Düşük (re-tag + push) |
   | CI/CD | GitLab self-hosted | 🟠 Yüksek | GitHub Actions, CircleCI | Yüksek (pipeline rewrite) |
   | AI | Anthropic API | 🔴 Yüksek | OpenAI, Google Vertex AI | Yüksek (prompt + system message ABI) |
   | Email | Resend | 🟢 Düşük | AWS SES, Mailgun, Postmark | Düşük (SDK abstract; `services/email.py`) |
   | Domain | Namecheap | 🟢 Düşük | Cloudflare Registrar, Route53 | Düşük (auth code transfer) |

2. **Hard-Coded IP / Domain'ler** (kod arama tabanlı):
   - `141.144.243.54` — 8 yerde (release manifests + scripts). Multi-region için **DNS-based discovery** veya **K8s Service'lere bağlı** kalınmalı.
   - `kfinans.app` — 12 yerde (config, manifests). Multi-tenant SaaS hedeflenirse env-driven olmalı.
   - `gitlab.192.168.3.191.nip.io` — `.gitlab-ci.yml` (self-hosted; lab IP).

3. **Vendor-Specific Optimizasyonlar**
   - Oracle K3s `svclb-traefik` — Oracle iSCSI specific; vanilla K8s'te yok
   - Resend `region: ap-northeast-1` (Tokyo) — domain re-add olmadan değiştirilemez
   - cert-manager **selfsigned** ClusterIssuer (postgres TLS için) — Let's Encrypt only desteklemediği için lokal CA

4. **Migration Playbook** (örnek: Oracle → AWS EKS, 4-8 hafta hedef)
   - Veri taşıma: pg_dump → AWS RDS restore
   - Secret taşıma: SealedSecrets master key portable; AWS Secrets Manager opsiyon
   - DNS cutover: TTL 5dk → switchover

**Tahmini boyut:** ~6KB

### 5.5 `docs/reference/reusability-patterns.md` (Yeni)

> **Amaç:** Yeni geliştirici onboarding'i için projedeki **best practice pattern'lerin** kataloğu.

**Bölümler:**
1. **`BaseIntegration` abstraction** (varsa) — `services/exchange/base.py`, blockchain'de var mı?
   - **NOT — kod tarafı çelişki:** `02-mimari.md` `BaseExchangeIntegration` referansı veriyor; ama blockchain servisleri (Sonic, Bitcoin, Solana) bu pattern'i takip etmiyor (ad hoc class'lar). Yeni geliştirici karışıklığını önlemek için ya pattern genişletilmeli ya da "blockchain ayrı, ad hoc" açıkça not edilmeli.
2. **Fault tolerance pattern** — `fetch_combined_prices` Binance + CoinGecko fallback örneği
3. **In-memory cache + single-flight pattern** — Bitcoin/Solana/P-Chain örnekleri
4. **Multi-RPC fallback (EVM)** — Ethereum/Avalanche `_select_rpc` rotation
5. **Fernet + MultiFernet pattern** — encrypt/decrypt + key rotation
6. **Address masking helper** — `app/core/masking.py::mask_address` Pydantic field_serializer
7. **Audit log pattern** — `services/audit.py::log_audit()` best-effort + X-Forwarded-For
8. **Pagination pattern** — `app/schemas/pagination.py::PaginatedResponse[T]`
9. **Soft-delete + hard-delete cron pattern** — KVKK m.7 uyumlu
10. **File upload validation** — magic byte + size + extension (`upload_validation.py`)
11. **Sanitized exception handler pattern** — `try/except` + `logger.exception` + generic Türkçe mesaj
12. **Frontend shared components** — `PageHeader`, `Logos`, `MkkHint`, `ConfirmDialog`, `TLValue`, `LanguageSwitcher`
13. **i18n key naming convention** — `auth.*`, `common.*`, `legal.*`, dictionary fallback

**Tahmini boyut:** ~7KB

---

## 6. Best Practice / Reusability / Portability — Kod Karşı NOT'lar (Düzeltme YOK)

Aşağıdaki maddeler **kod tarafına müdahale değil, doc'a sadece NOT olarak girer**; düzeltme için ayrı backlog issue açılır.

### 6.1 Best Practice Sapmaları
| # | Madde | Etki | Backlog |
|---|-------|------|---------|
| BP1 | Test coverage threshold: backend %60 line / frontend coverage threshold realistik = düşük (commit `599c1fa fix(tests): ... frontend coverage threshold realistik`) | Regresyon riski | Faz 4: %70 hedef |
| BP2 | Coverage % düşük olduğu kabul edildi (`bab66ad chore: ... coverage threshold realistik`) | Test borç | Faz 4: kademeli artır |
| BP3 | `f963d7b revert(csp): CSP nonce-based middleware geri al (build patladi)` — CSP nonce hâlâ pasif; `script-src 'unsafe-inline' 'unsafe-eval'` aktif | XSS surface | Faz 4: Next.js 16 SSR nonce pattern çalış |
| BP4 | `599c1fa fix: 8 HIBP test xfail` — HIBP rate limit / timeout / mock zayıf | Test reliability | Faz 4: HIBP test infrastructure güçlendir |
| BP5 | `frontend/CLAUDE.md` 11 byte (placeholder) | Onboarding eksik | Yukarıda merge önerisi |
| BP6 | Backend `pyproject.toml` `>=` versiyon (pin yok) → reproducibility riski | Supply chain | Faz 4: `pip-tools requirements.lock` üret |

### 6.2 Reusability Sapmaları
| # | Madde | Etki |
|---|-------|------|
| R1 | Blockchain servisleri (`sonic.py`, `bitcoin.py`, `solana.py`, ...) `BaseBlockchainIntegration` ortak interface'i yok — her servis kendi `fetch()` signature'ı | Yeni zincir eklerken duplicate kod; test mock'ları zor |
| R2 | `services/aggregator.py` 4 sorumluluk (TL normalize + USD/TRY + breakdown + paralel fetch) — ARC-005 backlog'ta |
| R3 | `services/snapshot.py` 624 satır god module — ARC-002 backlog'ta |
| R4 | Frontend `lib/api.ts` tek dosyada — modüler ayırma yok (auth, portfolio, expenses ayrı) |
| R5 | Pydantic schemas — bazı yerlerde inline (`audit_logs.py` router içinde — BACK-002 backlog) |

### 6.3 Portability Sapmaları
| # | Madde | Etki |
|---|-------|------|
| P1 | Hard-coded `141.144.243.54` 8 yerde (release manifests + scripts) — multi-node migration için DNS-based discovery şart |
| P2 | Hard-coded `kfinans.app` 12 yerde — multi-tenant SaaS pivot olursa env-driven config |
| P3 | Oracle K3s spesifik `svclb-traefik` fix (mevcut commit `365b8de`) — vanilla K8s'te yok |
| P4 | Anthropic API hard-coded model (`claude-sonnet-4-6`) — provider abstraction yok (OpenAI/Vertex'e geçiş `services/advisor.py` rewrite) |
| P5 | `.gitlab-ci.yml` self-hosted runner referansları (`gitlab.192.168.3.191.nip.io`, `sonar.192.168.3.191.nip.io`) — başka cluster'a taşınırken yeniden konfig şart |
| P6 | Resend `region: ap-northeast-1` Tokyo — bölge değişikliği domain re-add gerektirir; **portability matrix**'te belirt |
| P7 | `xlrd 1.2.0` MKK import (eski .xls binary) — Python 3.13+ ile uyumsuzluk riski; openpyxl + LibreOffice headless convert path düşünülebilir |

---

## 7. Önceliklendirilmiş Aksiyon Planı

| Sıra | Aksiyon | Tahmini Süre | Sahip |
|------|---------|--------------|-------|
| 1 | **`docs/07-guvenlik.md` KRİTİK UPDATE** — Faz I 10 audit fix maddesi | 2 saat | security-expert |
| 2 | **`docs/09-altyapi-test.md` UPDATE** — GitLab CI primary + NetworkPolicy + SealedSecrets | 1.5 saat | devops |
| 3 | **`docs/02-mimari.md` UPDATE** — Traefik + cert-manager + SealedSecrets + NetworkPolicy diyagramı | 1 saat | architect |
| 4 | **`docs/03-api-referansi.md` UPDATE** — MFA endpoint'leri + HIBP + rate limit + 423 | 1.5 saat | backend-expert |
| 5 | **`docs/01-tasarim-dokumani.md` UPDATE** — v4.4, Faz I bitti, link rot fix | 30 dk | architect |
| 6 | **`docs/infrastructure-runbook.md` UPDATE** — cert-manager selfsigned, SealedSecrets, NetworkPolicy, 2026-05-21 değişiklik geçmişi | 1 saat | devops |
| 7 | **`docs/operations/operations-playbook.md` NEW** | 2 saat | devops + security-expert |
| 8 | **`docs/operations/disaster-recovery.md` NEW** | 2 saat | devops + dba |
| 9 | **`docs/reference/portability-matrix.md` NEW** | 1.5 saat | architect |
| 10 | **`docs/reference/reusability-patterns.md` NEW** | 1.5 saat | backend-expert + frontend-expert |
| 11 | **`docs/reference/user-guide.md` NEW** | 2-3 saat | product (user-facing) |
| 12 | **`docs/backlog/ → docs/audits/` TAŞI** + `github-support-followup-2026-05-12.md` SİL | 15 dk | doc-uzman |
| 13 | **`docs/README.md` UPDATE** — yeni klasör yapısı index | 20 dk | doc-uzman |
| 14 | **CLAUDE.md UPDATE** — Tech Stack CI/CD + Hosting Traefik + Güvenlik 10 madde | 30 dk | doc-uzman |
| 15 | **Modül README'leri rotüş** (backend, frontend, k8s, CONTRIBUTING) | 1 saat | doc-uzman |

**Toplam tahmini süre:** ~18 saat (yarım sprint).

---

## 8. Çıktı Özeti

- **9 ana doc + 2 ops doc**'tan **5 tane KRİTİK UPDATE** gerekiyor (07-guvenlik, 09-altyapi-test, 02-mimari, 03-api, 01-tasarim).
- **2 doc SİL/ARŞİV** (github-support-followup, backlog/sprint-plan).
- **2 doc TAŞI** (backlog/audit-2026-05-08 → audits/, mevcut runbook+checklist → operations/).
- **5 YENİ doc** (operations-playbook, disaster-recovery, user-guide, portability-matrix, reusability-patterns).
- **12 çelişki** tespit edildi (Traefik vs nginx-ingress, GitLab vs GitHub CI, link rot, vb.).
- **20 kod-tarafı NOT** (BP1-6, R1-5, P1-7) — düzeltme yok, backlog için kayıt.

**Doküman kalitesi tutarlılığı için sürekli kural:**
- Her PR'da değişen kod alanı için ilgili 0X-doc satırı + CLAUDE.md güncellemesi **PR şart** olmalı (CONTRIBUTING.md zaten diyor).
- Aylık doc-drift check (yapılan commit'lerin doc'a yansıması) — bu raporun **rutinleştirilmiş hali**.

---

## 9. Değişiklik Geçmişi

| Tarih | Değişiklik |
|-------|-----------|
| 2026-05-22 | İlk versiyon — Faz I (2026-05-21 audit fix turu) sonrası kapsamlı doc audit; 9 doc + 2 ops + 5 modül README + CLAUDE.md değerlendirildi; 12 çelişki + 18 saat aksiyon planı çıkarıldı. |
