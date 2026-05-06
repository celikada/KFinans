# Katkı Rehberi

KFinans'a katkıda bulunmak istediğiniz için teşekkürler! Bu rehber yeni başlayanlar için hızlı bir başlangıç sağlar.

## 📋 Ön Şart: Davranış Kuralları

Tüm katkıcılar [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) (Contributor Covenant 2.1) kurallarına uymakla yükümlüdür.

## 🚀 Hızlı Başlangıç

```bash
# 1. Fork + clone
git clone https://github.com/<kullanici-adi>/KFinans.git
cd KFinans

# 2. Backend
cd backend
pip install -e ".[dev]"
cp .env.example .env  # değerleri kendi makinanıza göre düzenleyin
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend (yeni terminal)
cd frontend
npm install
npm run dev
```

Detaylı kurulum: [docs/09-altyapi-test.md](./docs/09-altyapi-test.md).

## 🌳 Branch Stratejisi

| Branch | Amaç | Doğrudan push? |
|--------|------|----------------|
| `main` | Production — sadece tag'li release'lere kaynak | ❌ Sadece PR + status check'ler yeşil |
| `develop` | Aktif geliştirme | ⚠️ Sürdürücü için açık, dış katkıcılar PR açar |
| `feature/<isim>` | Yeni özellik | – (PR ile `develop`'a) |
| `fix/<isim>` | Bug fix | – (PR ile `develop`'a) |
| `hotfix/<isim>` | Acil prod fix | – (PR ile `main` + cherry-pick `develop`) |

## 🔀 Pull Request Süreci

1. `develop`'tan branch açın: `git checkout -b feature/cool-thing develop`
2. Değişiklikleri yapın, **küçük commit'ler** halinde tutun
3. Test ekleyin (`backend/tests/` veya `frontend/__tests__/`)
4. Lokal kontrol:
   ```bash
   cd backend && ruff check . && ruff format --check . && pytest
   cd frontend && npm test && npm run lint
   ```
5. PR açın (template otomatik dolar). PR açıklamasında:
   - Hangi sorunu çözüyor?
   - Nasıl test edildi?
   - Ekran görüntüsü (UI değişikliği varsa)
6. CI yeşil olunca, sürdürücü merge eder

### Commit Mesajı Formatı

Tüm commit mesajları **Türkçe** yazılır (proje konvansiyonu). Önek tutarlılığı için:
- `feat:` yeni özellik
- `fix:` bug düzeltmesi
- `refactor:` davranış değişmeden kod düzenleme
- `test:` test ekleme/düzeltme
- `docs:` dokümantasyon
- `chore:` ufak işler (dependency güncelleme, lint config)
- `ci:` GitHub Actions / pipeline değişikliği

Örnek: `feat: cüzdan adresi Fernet şifrelemesi`

## 🧪 Testler

| Tip | Dizin | Çalıştırma |
|-----|-------|------------|
| Backend unit | `backend/tests/unit/` | `pytest tests/unit` |
| Backend integration | `backend/tests/integration/` | `pytest tests/integration` (gerçek Postgres ister) |
| Frontend unit | `frontend/__tests__/` | `npm test` |
| Frontend E2E | `frontend/playwright/` | `npx playwright test` |

Coverage hedefi: **%50** (Faz 2.5), **%70** (Faz 3 hedef). PR'da coverage düşmemeli.

## 🎨 Kod Stili

- **Python:** `ruff` (PEP 8 + flake8 + isort) — `ruff format` kullanın, pre-commit hook'a alın
- **TypeScript:** ESLint + Prettier (Next.js default config)
- **Identifier'lar İngilizce**, **yorumlar minimum** (kod kendi kendini açıklamalı), **dokümantasyon Türkçe**
- Yorum yazmadan önce: "Bu yorum 6 ay sonra yanlış olur mu?" — olabilirse yazma. Sadece **niçin** açıklayın, ne yaptığını değil.

## 🔒 Güvenlik

- **API key, şifre, token** asla commit edilmez (`.gitleaks.toml` CI'da kontrol eder)
- Yeni endpoint eklerken [docs/07-guvenlik.md §12](./docs/07-guvenlik.md) kontrol listesine bakın
- Güvenlik açığı bulduysanız **public issue açmayın** — [SECURITY.md](./SECURITY.md) izleyin

## 📚 Dokümantasyon

- Yeni özellik: ilgili `docs/0X-*.md` belgesini güncelleyin
- API değişikliği: `docs/03-api-referansi.md` güncellemeli
- Mimari karar: ADR formatında `docs/02-mimari.md`'ye ekleyin

## 🐛 Bug Raporu

[Issue template](./.github/ISSUE_TEMPLATE/) doldurun. Şunlar olmadan bug kapatılır:
- Tekrar üretim adımları
- Beklenen vs. gerçekleşen davranış
- Browser/OS/Python sürümü
- Log çıktısı (varsa)

## 💬 İletişim

- Genel sorular: GitHub Discussions
- Bug: GitHub Issues
- Güvenlik: `celikada@gmail.com` ([SECURITY.md](./SECURITY.md))

Emek ve zamanınız için teşekkürler! 🙏
