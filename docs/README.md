# KFinans Dokümantasyonu

Bu klasör KFinans'ın tüm teknik tasarım belgelerini içerir. Numara önekleri okunma sırasını gösterir — yeni başlayanlar 01'den itibaren ilerleyebilir.

---

## İçindekiler

| # | Belge | Konu | Sahip Ajanlar |
|---|---|---|---|
| 01 | [Sistem Tasarım Dokümanı](01-tasarim-dokumani.md) | Ürün vizyonu, kapsam, üst seviye mimari | architect |
| 02 | [Mimari + DB Şeması](02-mimari.md) | Servis sınırları, modüller, PostgreSQL şema | architect, dba |
| 03 | [API Referansı](03-api-referansi.md) | FastAPI endpoint'leri, request/response, hata kodları | backend-expert |
| 04 | [Frontend Mimarisi](04-frontend.md) | Next.js sayfa hiyerarşisi, state, routing, bileşen kataloğu | frontend-expert |
| 05 | [AI ve Finans Hesaplamaları](05-ai-ve-finans.md) | Claude prompt mühendisliği, portföy ağırlık, kâr/zarar, kur dönüşüm | ai-expert, finance-expert |
| 06 | [Kredi Sistemi ve Ödeme Akışı](06-kredi-sistemi.md) | SaaS abonelik, kredi defteri, iyzico ödeme akışı | architect, finance-expert |
| 07 | [Güvenlik Mimarisi](07-guvenlik.md) | OWASP, JWT, Fernet şifreleme, rate limiting, secrets | security-expert |
| 08 | [KVKK ve Regülasyon Uyumluluğu](08-uyumluluk-kvkk.md) | KVKK aydınlatma, açık rıza, veri saklama, hesap silme | compliance-expert |
| 09 | [Altyapı, Deployment ve Test](09-altyapi-test.md) | Docker Compose dev, Kubernetes prod, CI/CD, test stratejisi | devops, test-expert |
| 10 | [Yol Haritası 2026](10-yol-haritasi-2026.md) | Rekabet analizi + ürün stratejisi + teknik yol haritası (3 kova: parite, iyileştirme, farklılaştırma) | architect |

---

## Okuma Sırası

**Yeni geliştirici onboarding:**
1 → 2 → 3 (backend) **veya** 4 (frontend) → 9 (altyapıyı çalıştırmak için)

**Yeni özellik tasarlamak:**
1 (kapsam ve vizyon) → 2 (nereye sığar) → 3 / 4 (uygulama katmanı) → 7 (güvenlik gözden geçirmesi)

**Production'a almak:**
9 (deploy + test) → 7 (güvenlik) → 8 (KVKK) → 6 (billing aktivasyonu)

---

## Doküman Bakım Politikası

- Her özellik tamamlandığında ilgili belge **aynı PR'da** güncellenir (push öncesi zorunlu).
- Belge sahipleri (örn. `backend-expert`, `frontend-expert`) ilgili kısımlardan sorumludur.
- Tarih damgalı versiyon notları belgenin üst kısmında tutulur.
- Tasarım belgeleri Türkçe; kod örneklerindeki tanımlayıcılar İngilizce.

---

## Diğer Belgeler

Proje kökü:
- [`README.md`](../README.md) — Hızlı başlangıç ve genel bakış
- [`backend/README.md`](../backend/README.md) — Backend kurulumu, komutlar, .env
- [`frontend/README.md`](../frontend/README.md) — Frontend yapısı, bileşenler, stil
- [`CLAUDE.md`](../CLAUDE.md) — Claude Code asistanına proje yönergeleri

Operasyonel belgeler (`operations/`):
- [`operations/production-deploy-checklist.md`](operations/production-deploy-checklist.md) — İlk production deploy (v0.1.0) checklist
- [`operations/infrastructure-runbook.md`](operations/infrastructure-runbook.md) — DNS, email, K3s, cert-manager kurulum kayıtları + periyodik bakım
- [`operations/operations-playbook.md`](operations/operations-playbook.md) — Günlük operasyon + alerting + troubleshooting (taslak)
- [`operations/disaster-recovery.md`](operations/disaster-recovery.md) — DR drill + restore prosedürü + RTO/RPO (taslak)

Referans belgeleri (`reference/`):
- [`reference/user-guide.md`](reference/user-guide.md) — Son kullanıcı kılavuzu (17 dashboard sayfası feature listesi)
- [`reference/portability-matrix.md`](reference/portability-matrix.md) — Vendor lock-in + multi-cloud migration plan
- [`reference/reusability-patterns.md`](reference/reusability-patterns.md) — Kod pattern kataloğu (BaseIntegration, MultiFernet, masking, audit, vs.)

Audit tutanakları (`audits/`):
- [`audits/2026-05-22-master-audit.md`](audits/2026-05-22-master-audit.md) — **Faz I sonrası master audit (11 paralel uzman ajan)**
- [`audits/2026-05-08-faz-g-audit.md`](audits/2026-05-08-faz-g-audit.md) — Faz G sistem audit özeti (240 bulgu)
- [`audits/2026-05-08-sprint-plan.md`](audits/2026-05-08-sprint-plan.md) — Faz G audit sonrası sprint planı
- [`SYSTEM-DOC-AUDIT-2026-05-22.md`](SYSTEM-DOC-AUDIT-2026-05-22.md) — Dokümantasyon audit + reorganize plan (doc-expert)
- [`MIMARI-AUDIT-2026-05-22.md`](MIMARI-AUDIT-2026-05-22.md) — Sistem mimarisi audit (architect)
- [`audit-2026-05-22/`](audit-2026-05-22/) — 9 uzman ajan notu (compliance, security, dba, ai, backend, devops, test, finance, frontend)

Legal:
- [`legal/incident-response-plan.md`](legal/incident-response-plan.md) — Veri ihlali müdahale planı (ISO 27035 + KVKK m.12/5 + GDPR Art.33)
