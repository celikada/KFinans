# Güvenlik Politikası

> **English version below.**

## 🇹🇷 Türkçe

KFinans, kişisel finansal verileri (portföy, exchange API key, blockchain cüzdan adresleri) işleyen bir uygulamadır. Güvenliği ciddiye alıyoruz ve sorumlu açıklama (responsible disclosure) prensibini benimsiyoruz.

### Desteklenen Sürümler

| Sürüm | Destekleniyor mu |
| ----- | ---------------- |
| `main` (en güncel) | ✅ |
| `develop` | ✅ |
| Tag'li release (en son `v*.*.*`) | ✅ |
| Daha eski tag'ler | ❌ |

Production deploy yalnızca `main` üzerinde tag'li release'lerden yapılır. Açık tespit edildiğinde `main`'e patch düşer ve yeni bir patch release tag'i (`v1.0.x`) yayınlanır.

> **Repo notu:** Kod tabanı self-hosted **GitLab** (primary) üzerinde tutulur; GitHub bir mirror'dır. `develop` ve `main` her iki platformda da korumalıdır (force-push + branch silme engelli; GitLab'da push=No one → yalnızca MR ile).

### Zafiyet Bildirimi

**Lütfen GÜVENLİK AÇIKLARINI KAMU GitHub Issue'su olarak AÇMAYIN.**

Aşağıdaki kanaldan bildiriniz:

- 📧 **E-posta:** `celikada@gmail.com` (PGP key talep üzerine)
- 🔐 **GitHub Private Vulnerability Report:** Bu repo'nun "Security" sekmesi → "Report a vulnerability"

Bildiriminizde lütfen şu bilgileri verin:
1. Açığın kısa açıklaması (örn. "JWT validate atlatma", "IDOR — wallet endpoint")
2. Tekrar üretim adımları (mümkünse minimal PoC)
3. Etki değerlendirmesi (örn. "diğer kullanıcının portföyü okunabilir")
4. Önerdiğiniz çözüm (varsa)
5. İletişim için tercih ettiğiniz isim/takma ad (kabul edilen bildirimlerde teşekkür kısmında geçecek)

### Yanıt Süreci

| Zaman | Aksiyon |
|-------|---------|
| **48 saat** | İlk yanıt — bildirimi aldığımızı teyit ederiz |
| **7 gün** | Triage — açığın geçerli olup olmadığını ve önem seviyesini bildiririz |
| **30 gün** | Düzeltme planı — hedef yayın tarihi paylaşılır |
| **90 gün (max)** | Kamu açıklaması — düzeltme yayınlanır, CVE varsa atanır |

90 günden sonra (sorumlu açıklama penceresi) açığı kamuya açıklayabilirsiniz. Yamada gecikme yaşanıyorsa süreyi birlikte uzatabiliriz.

### Kapsam

**Kapsam içi:**
- KFinans backend API (`backend/`)
- KFinans frontend (`frontend/`)
- Kubernetes manifest'ler (`k8s/`)
- CI/CD workflow'ları (`.github/workflows/`)
- Production deployment (`https://kfinans.app`)

**Kapsam dışı:**
- Üçüncü taraf bağımlılıklar (kendi maintainer'larına bildiriniz; ardından bizi haberdar edin)
- DoS / volumetric saldırılar (rate limit zaten var; teorik DoS PoC kabul edilmez)
- Otomatik tarayıcı (Acunetix, ZAP) çıktıları — manuel doğrulanmamışsa
- Sosyal mühendislik / phishing senaryoları
- Fiziksel güvenlik
- Outdated browser zafiyetleri

### Otomatik Güvenlik Gate'leri

Her değişiklik CI pipeline'ında (GitLab primary; GitHub Actions mirror'da hesap flag nedeniyle pasif) şu kontrollerden geçer:

| Gate | Araç | Davranış |
|------|------|----------|
| Secret tarama | gitleaks (`.gitleaks.toml` allowlist'li) | Gerçek secret → fail. Allowlist yalnızca kanıtlanmış zararsız test/örnek değerleri ve SealedSecrets ciphertext'ini kapsar |
| SAST | CodeQL (Python + TS) | security-and-quality query suite |
| Kod kalitesi + güvenlik | **SonarQube quality gate (blocking)** | Yeni kodda bug/vulnerability/review edilmemiş security hotspot → fail. `new_security_hotspots_reviewed=%100` zorunlu |
| Bağımlılık (Python) | pip-audit (osv, strict) | HIGH+ → fail |
| Bağımlılık (Node) | npm audit (`--audit-level=high`) | HIGH+ → fail |
| Dosya sistemi + IaC | Trivy fs | HIGH/CRITICAL → fail |
| Container image | Trivy image (release pipeline) | HIGH/CRITICAL → fail (deploy öncesi) |
| Bağımlılık güncellemeleri | Dependabot (haftalık) | pip + npm + actions + docker |

Secret yönetimi production'da **SealedSecrets (bitnami)** ile GitOps-safe yürütülür: `k8s/sealed-secrets.yaml` içindeki `encryptedData` asimetrik şifrelidir ve yalnızca cluster private key'i ile çözülür.

### Ödüllendirme

Şu an formel bir bug bounty programımız **yok**. Ancak:
- Geçerli bildirimler için `SECURITY-HALL-OF-FAME.md` dosyasında alenen teşekkür ederiz
- Kritik bulgu için sembolik bir hediye (örn. T-shirt, kahve) gönderebiliriz
- Programı genişlettiğimizde önce siz haberdar olursunuz

### Bilinen Açıklar

Aktif tespit edilen ama henüz çözülmemiş açıklar `docs/07-guvenlik.md §3.5` (JWT) ve `§8` (eksik korumalar) bölümlerinde listelidir. Bu açıklar production deploy öncesi kapatılacaktır.

---

## 🇬🇧 English

KFinans is an application that processes personal financial data (portfolios, exchange API keys, blockchain wallet addresses). We take security seriously and follow responsible disclosure.

### Supported Versions

Production runs only the latest tag on `main`. Older tags are not patched.

### Reporting a Vulnerability

**Please DO NOT open a public GitHub Issue for security vulnerabilities.**

Use one of these channels:
- 📧 **Email:** `celikada@gmail.com` (PGP key on request)
- 🔐 **GitHub Private Vulnerability Report:** "Security" tab on this repo → "Report a vulnerability"

Please include:
1. Brief description (e.g., "JWT validation bypass", "IDOR — wallet endpoint")
2. Reproduction steps (minimal PoC if possible)
3. Impact assessment
4. Suggested fix (if any)
5. Your preferred handle for the credits

### Response SLA

| Time | Action |
|------|--------|
| 48 h | Acknowledgement |
| 7 days | Triage (validity + severity) |
| 30 days | Fix plan + target release |
| 90 days (max) | Public disclosure |

After 90 days (responsible disclosure window) you may publicly disclose. We can mutually extend if a patch is in flight.

### Scope

In-scope: backend, frontend, k8s manifests, CI/CD, `https://kfinans.app`.
Out-of-scope: third-party deps, theoretical DoS, unverified scanner output, social engineering, physical security, outdated browsers.

### Automated Gates

Every change passes blocking CI gates (GitLab primary): gitleaks (secret scan), CodeQL SAST, **SonarQube quality gate** (100% new-hotspot review required), pip-audit, npm audit, and Trivy (fs + image). Production secrets are managed GitOps-safely via SealedSecrets (asymmetric ciphertext, committed to the repo).

### Rewards

No formal bug bounty yet. We offer public credit in `SECURITY-HALL-OF-FAME.md` and may send a token gift for critical findings.

---

**Last updated:** 2026-06-01
