# Test Audit Notları — 2026-05-22

Kapsam: backend pytest (192 unit + 357 integration + FAZ H, %57.34 line cov), frontend vitest (%2.93 lines), Playwright @smoke 11 senaryo. Görsel inceleme; kod değişikliği yapılmadı.

## ✓ Mevcut Pozitif

- **conftest izolasyonu sağlam.** `tests/conftest.py` TEST_DB_URL son ek kontrolü ile production `kfinans` DB'sine yanlış bağlanmayı engelliyor (`drop_all` koruması). `engine` `NullPool` ile event-loop kaynaklı async pool sızıntılarını önlüyor.
- **TRUNCATE autouse pattern (TEST-004).** `tests/integration/conftest.py::_truncate_after_test` her test sonrası `TRUNCATE RESTART IDENTITY CASCADE` ile DB sıfırlıyor; `Base.metadata.sorted_tables` dinamik liste — yeni tablo eklendiğinde manuel güncelleme yok.
- **make_user ortak helper (TEST-002).** Önceki dağınık `_make_user` (18 dosya) merkezi `tests.conftest.make_user(client, email=None)`'a taşındı; `age_confirmed=True` (COMP-010) varsayılan.
- **password_policy marker pattern.** Autouse fixture default'ta zxcvbn + HIBP bypass eder; `@pytest.mark.password_policy_enabled` marker test bazında gerçek policy'yi aktive eder — test gürültüsü minimum.
- **Modül-level cache reset (FIN-007).** `_reset_tcmb_cache` autouse fixture aggregator'ın 300s TTL cache'ini her test öncesi sıfırlıyor — respx mock'larının tutarlı olmasını garantiliyor.
- **`--strict-markers` + `--strict-config`** pytest config'inde aktif; marker typo'ları kaynağı yutmadan yakalanıyor.
- **TEFAS respx unit test örneği temiz.** `tests/unit/test_tefas.py` `respx.post(_EXPORT_URL)` ile servis modülünden URL constant import ediyor — magic-string yok, refactor güvenli.
- **Frontend api.test.ts kalitesi yüksek.** Single-flight refresh, 401 retry, clearAuth+redirect, paralel istek senaryoları covered — `vi.stubGlobal("fetch", ...)` ile transport interception net.

## ⚠ Çelişti / Düzeltme Notları

| #  | Öncelik | Sorun | Etki | Öneri |
|----|---------|-------|------|-------|
| 1  | Yüksek  | 8 HIBP integration test `@pytest.mark.xfail` (`respx mock URL match issue`); `strict=False` → mock çalışırsa CI sessizce geçer | HIBP fail-open / pwned-password reject akışı CI'da gerçek kapsamda değil; production-only davranış | `respx.mock(assert_all_called=False, base_url=None)` yerine `httpx.AsyncClient` `app.lifespan` içindeki module-level client'ı patch'le; ya da `app/services/hibp.py::_client` factory'sini test-replaceable yap |
| 2  | Yüksek  | Frontend coverage threshold `lines: 2, statements: 2, branches: 0` — _de facto_ kapı yok | Yeni component'lerin sıfır test ile merge edilmesi mümkün; vitest sadece `lib/api.ts` (~30 sat) cover ediyor | `lines: 5` ile başlayıp her sprint 5 puan artır; `app/_components/{ConfirmDialog, LanguageSwitcher}.tsx` ve `app/login/page.tsx` smoke test'leri öncelik |
| 3  | Yüksek  | `app/dashboard/**/*` 17 sayfa için vitest 0 test (sadece Playwright @smoke 11 senaryo) | Page-level form validation + RHF state + URL param parse + recharts render regression'ları sadece prod'da yakalanır | `@testing-library/react` + `vi.mock("@/lib/api")` ile 5 kritik sayfa (login, dashboard root, expenses, wallets, settings) için render + happy-path component test |
| 4  | Orta    | Playwright `@smoke` token'lı dashboard'a giremiyor (a11y testi açıkça not düşmüş: "Token'sız /dashboard'a gidişi /login redirect eder") | Skip-link, focus trap, dialog accessibility gerçek dashboard sayfasında doğrulanmıyor | `playwright/fixtures.ts` içinde `loggedInPage` fixture (storageState ile authenticated context); MFA helper de buraya taşı |
| 5  | Orta    | `tests/unit/test_blockchain_*.py` mock pattern karışık: `respx`, `unittest.mock.AsyncMock`, doğrudan monkeypatch | Yeni geliştirici hangi pattern'i kullanacağına karar veremez; review zaman kaybı | `tests/_helpers/mocks.py` modülü oluştur: `mock_glacier_balance()`, `mock_ethplorer_tokens()`, `mock_solana_rpc()` gibi domain-aware helper'lar |
| 6  | Orta    | `respx.mock` decorator + `respx.mock context manager` karışık kullanımı (`test_asset_catalog.py` decorator, `test_auth.py` context manager) | Refactor sırasında her dosya kendi convention'ını izliyor; lint kuralı yok | Tek convention belirle (öneri: decorator `@respx.mock` + `assert_all_called=False` keyword); CONTRIBUTING.md test bölümüne ekle |
| 7  | Orta    | `frontend/__tests__/api.test.ts` `vi.stubGlobal("fetch", ...)` raw kullanıyor; MSW (`msw: ^2.6.0`) `devDependency` olarak yüklü ama hiç kullanılmıyor | İleride komponenti test ederken her test fetch mock duplikasyonu yazacak; MSW handler reusability yüksekti | `frontend/__tests__/_msw/handlers.ts` setup; vitest setup'da `server.listen()` — react component test'leri için hazır |
| 8  | Düşük   | Backend `[tool.coverage.run] omit = ["app/main.py", "app/scheduler.py"]` — kritik startup + cron path'leri coverage'dan dışlanmış | %57.34 line cov gerçek production code path'inin daha düşüğünü gösteriyor; cron job regression riski | `_weekly_snapshot_job` ve `_hard_delete_expired_users_job` için unit test yazılınca omit kaldır; coverage `services/scheduler.py`'a hak ettiği görünürlüğü kazansın |
| 9  | Düşük   | Test piramidi dengesizliği: unit 192 / integration 357 / e2e 11 (1.86:3.46:1 oranı integration-ağır) | Integration testleri yavaş (PostgreSQL TRUNCATE/test ~100ms); CI süresi ~6-8dk | Yeni testler için "önce unit, sonra integration" kuralı + `services/aggregator.py::_compute_breakdown` gibi pure-function'ları integration yerine unit'e taşı |
| 10 | Düşük   | Test taşınabilirliği zayıf: `TEST_DB_URL` `localhost:5432` hardcoded; cluster içi (K3s) test ortamı için ayrı setup yok | Develop ortamında pre-deploy smoke pipeline kurulamıyor; `kubectl run --rm pytest-runner` çalıştırılamaz | Backend `Dockerfile.test` ekle (pytest+respx+psql client); `tests/README.md` "Docker Compose ile test çalıştırma" + "K3s pod içinde test" bölümleri |
| 11 | Düşük   | `password_policy_enabled` marker test izolasyonu zorunlu kılmıyor; aynı dosyada marker'lı + marker'sız testler arada monkeypatch leak edebilir | Flaky test riski (low frequency) | Marker kullanan testleri `tests/integration/policy/` alt klasöre ayır; conftest scope sadece klasör için |
| 12 | Düşük   | E2E `playwright.config.ts` sadece Chromium proje tanımlı; Firefox/WebKit (Safari) testi yok | Cross-browser regression yakalanmaz (Next.js 16 + React 19 hala stabilize oluyor) | `projects: [chromium, webkit]` minimum; release smoke için yeterli |

## Coverage Roadmap

- **Backend %57.34 → %80 hedefi**
  - Quick wins (%65'e taşır): `app/services/scheduler.py` (cron job unit testleri), `app/api/v1/advice.py` (credit consumption edge case'leri zaten kapsanmış; rate-limit + Anthropic SDK hata path'i mock), `app/services/reports.py` (Excel/PDF üretim happy + Türkçe karakter regression)
  - Orta vadeli (%75'e taşır): `app/services/blockchain/avalanche_p_chain.py` Glacier→JSON-RPC fallback + 429 backoff retry; `app/services/blockchain/bitcoin.py` xpub cache + single-flight race condition
  - Long-tail (%80+): `app/api/v1/cash_flow.py` 12-aylık projeksiyon, `app/api/v1/credit_cards.py` çift sayım kuralı (`is_paid=true → exclude`)

- **Frontend %2.93 → %15 → %30 → %50 kademeli**
  - Faz 1 (%15): `app/_components/ConfirmDialog.tsx`, `app/_components/LanguageSwitcher.tsx`, `app/_i18n/I18nProvider.tsx` + `useTranslation()` hook (RTL ile)
  - Faz 2 (%30): `app/login/page.tsx` (form validation + 401 hata mesajı + reset link), `app/dashboard/page.tsx` (loading spinner + boş state + USD/TRY toggle)
  - Faz 3 (%50): `app/dashboard/expenses`, `app/dashboard/wallets`, `app/dashboard/credit-cards/[id]` form + tablo + filtre senaryoları
  - Threshold kademeli yükselt: 5 → 10 → 15 → 25 → 40 (her sprint sonu PR ile `vitest.config.ts` güncelle)

- **Edge case + error path coverage**
  - 4xx/5xx response handling: `lib/api.ts` 401 retry ✓, 403 KVKK consent, 429 rate-limit toast, 503 backend down banner — şu an sadece 401 covered
  - Empty/loading/error state'leri component bazında testlenmeli: skeleton, "kayıt yok", "yüklenirken hata oluştu" tüm dashboard sayfalarında tekrar eden pattern → `app/_components/EmptyState.tsx` çıkar + tek yerden test et

## Reusability

- **conftest fixture pattern'leri ✓ olgun.**
  - `make_user(client, email)` — 18 dosya çapraz kullanım; auth helper olarak referans.
  - `_disable_password_policy_by_default(request, monkeypatch)` — marker-based opt-in; `tests/conftest.py:71` örneği yeni policy fixture'lar (rate-limit, MFA mandatory) için kalıp.
  - `_reset_tcmb_cache` — modül-level cache reset pattern'i yeni servisler için kopyalanmalı (`aggregator._tcmb_cache`, `bitcoin._BALANCE_CACHE`, `avalanche_p_chain._PCHAIN_CACHE` da aynı pattern bekliyor — şu an unit testlerde manuel reset).

- **respx mock helper'ları zayıf — merkez yok.**
  - Şu an her test dosyası kendi URL constant'ını referanslıyor (`_EXPORT_URL`, `_HIBP_RANGE_URL`).
  - Öneri: `tests/_mocks/external.py` modülü — `mock_tefas_export(rows)`, `mock_hibp_clean()`, `mock_hibp_pwned(password, count)`, `mock_binance_ticker(symbol, price)`, `mock_glacier_balance(address, balance)` factory'ler. Context manager veya decorator'la dön.
  - Bonus: `assert_all_called=False` default sapması yerine factory'de net opt-in (`strict_mode=True`).

- **Playwright fixture (login, MFA) reusable değil.**
  - `playwright/mfa.spec.ts` 10KB; muhtemelen kendi setup'ını tekrarlıyor.
  - Öneri: `playwright/fixtures.ts` ekle:
    - `loggedInPage` — `storageState` ile pre-auth context
    - `mfaEnabledUser` — backend `make_user` + `/auth/mfa/setup` curl call
    - `testUser` — auto-cleanup pattern (`afterEach` user delete)
  - `playwright.config.ts::projects` içinde `dependencies: ["auth-setup"]` ile login state'i tek seferlik üret (Playwright "global setup" pattern).

- **Test taşınabilirliği — cluster içi test ortamı kurulumu.**
  - Şu an: `TEST_DB_URL` `localhost:5432` hardcoded; CI'da `services.postgres` GitHub Actions container.
  - Eksik: `kubectl run --rm pytest-runner --image=ghcr.io/celikada/kfinans-backend-test:latest` ile prod cluster içi smoke imkânı yok.
  - Öneri:
    - `backend/Dockerfile.test` — `pytest + respx + asyncpg client + psql` minimal image
    - `k8s/jobs/pytest-runner.yaml` — Job manifest (DB için cluster-internal `postgresql.kfinans.svc` host)
    - `make test-cluster` Makefile target — `kubectl apply -f k8s/jobs/pytest-runner.yaml && kubectl logs -f job/pytest-runner`
  - Bu sayede release.yml smoke job'ı curl-only yerine pytest suite çalıştırabilir (prod traffic'e dokunmadan).

## Aksiyon Önerileri (Öncelik Sırası)

1. **HIBP xfail testleri düzelt (#1)** — production fail-open davranışı doğrulanmalı; refactor `respx` URL match yerine module-level httpx client'ı patch'le.
2. **Frontend component test base'i kur (#3 + #7)** — MSW handler setup + 5 kritik sayfa için happy-path test; threshold `5` ile başla.
3. **Cluster içi test runner (#10)** — `Dockerfile.test` + K8s Job manifest; release pipeline smoke gate genişlesin.
4. **Playwright authenticated fixture (#4)** — dashboard a11y testleri gerçek sayfada çalışsın.
5. **respx helper modülü (#5 + #6)** — convention belirle, helper factory'ler ekle; CONTRIBUTING.md güncelle.
