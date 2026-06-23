## Değişiklikler

<!-- Ne eklendi / değiştirildi / düzeltildi? Tek paragraf yeterli. -->

## Neden

<!-- Motivasyon, bağlantılı issue veya tasarım kararı -->

## Test

- [ ] Backend unit testler geçiyor (`pytest tests/unit/`)
- [ ] Backend integration testler geçiyor (`pytest tests/integration/`)
- [ ] Frontend testler geçiyor (`npm test` + `npx playwright test` UI değişikliği varsa)
- [ ] Manuel test yapıldı (UI değişikliği için ekran görüntüsü ekleyin)
- [ ] Yeni endpoint için curl/httpie örneği denendi

## Kalite Kontrolü

- [ ] Kod `ruff check . && ruff format --check .` ile temiz (backend)
- [ ] Kod `npm run lint` ile temiz (frontend)
- [ ] Yeni migration varsa `alembic upgrade head` + `alembic downgrade -1` test edildi
- [ ] Coverage %50 hedefinin altına düşmedi (CI gate kontrol eder)
- [ ] Sonar Quality Gate yeşil (PR'da otomatik kontrol edilir)

## Güvenlik Kontrol Listesi

> Yeni bir endpoint, model veya integration ekliyorsanız aşağıdaki maddeleri **mutlaka** doğrulayın. Detay: [docs/07-guvenlik.md §12](../docs/07-guvenlik.md).

- [ ] Yeni endpoint var mı? `Depends(get_current_user)` kullanılıyor (auth gerektiriyor)
- [ ] Veritabanı sorgusunda `user_id == current_user.id` filtresi var (IDOR koruması)
- [ ] Pydantic ile input validation tam (özellikle string uzunlukları, numeric range)
- [ ] Sensitive data (API key, password, token) **asla** API yanıtında dönmüyor
- [ ] Hata mesajları stack trace içermiyor (production-safe)
- [ ] File upload varsa: tip + boyut + content-type kontrolü
- [ ] Yeni write endpoint için rate limit gerekiyor mu? (`@limiter.limit(...)`)
- [ ] Kritik eylem (login, integration add, wallet add, password change) → audit log eklendi mi?
- [ ] Secret veya `.env` içeriği commit'e girmedi (`gitleaks` CI'da kontrol eder)
- [ ] Yeni dış servis çağrısı: timeout + retry + fallback eklendi (fault-tolerance pattern)

## Dokümantasyon

- [ ] API değiştiyse `docs/03-api-referansi.md` güncel
- [ ] Mimari değiştiyse `docs/02-mimari.md` güncel
- [ ] Yeni özellik için `docs/0X-*.md` ilgili bölüm güncel
- [ ] CLAUDE.md'de etkilenen mimari kararlar güncel (geliştirici onboarding için)

## Deploy

- [ ] Bu PR `develop` → `main` mı? Eğer evetse:
  - [ ] Versiyon bump yapıldı (`pyproject.toml` + `package.json`)
  - [ ] CHANGELOG güncel (varsa)
  - [ ] Tag oluşturulacak: `v?.?.?`
  - [ ] Production secret değişikliği gerekiyor mu (Hetzner k3s)?
