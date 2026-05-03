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
