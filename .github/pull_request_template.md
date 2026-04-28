## Değişiklikler

<!-- Ne eklendi / değiştirildi / düzeltildi? -->

## Neden

<!-- Motivasyon veya bağlantılı issue -->

## Test

- [ ] Unit testler geçiyor (`pytest tests/unit/`)
- [ ] Integration testler geçiyor (`pytest tests/integration/`)
- [ ] Manuel test yapıldı

## Kontrol Listesi

- [ ] Kod `ruff check .` ile lint'ten geçiyor
- [ ] Yeni migration varsa `alembic upgrade head` test edildi
- [ ] Secrets veya `.env` içeriği commit'e girmedi
- [ ] `develop` → `main` PR'ı ise versiyon bump yapıldı
