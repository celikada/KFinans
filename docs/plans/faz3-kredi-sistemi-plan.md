# Faz 3 — Kredi Satın Alma Sistemi: Dosya-Bazlı Uygulama Planı

**Sahip:** `architect` (tasarım kararları) → delege: `dba`, `backend-expert`, `finance-expert`, `security-expert`, `test-expert`, `frontend-expert`, `compliance-expert`
**Faz:** 3 — kalan tek büyük parça
**Referans:** [`docs/06-kredi-sistemi.md`](../06-kredi-sistemi.md), [`docs/03-api-referansi.md`](../03-api-referansi.md), `CLAUDE.md`
**Migration head (teyit edildi):** `e2f3a4b5c6d7` → yeni migration `down_revision = "e2f3a4b5c6d7"` olmalı (head'den zincirlenen başka migration yok).

---

## 0. Yönetici Özeti

Bugün bakiye **düşürülebiliyor** (AI tavsiye: `advice.py` doğrudan `user.credit_balance -= 1`) ama bakiye **yüklenemiyor** (ödeme yok) ve **ledger/audit trail yok**. Plan iki aşamaya bölünür:

- **Aşama 1 (iyzico key BEKLEMEDEN, hemen yapılabilir):** Ledger altyapısı. `credit_transactions` tablosu + model + migration, `core/credits.py` helper (`deduct_credits`/`add_credits`, `SELECT FOR UPDATE`), `advice.py` refactor (davranış aynı, düşüm helper'a + ledger insert'e taşınır), `GET /credits` endpoint (bakiye + paginated geçmiş), testler.
- **Aşama 2 (iyzico API key gelince):** Satın alma. `POST /credits/checkout` + `POST /credits/webhook` + HMAC imza + idempotency + frontend (header bakiye, satın alma sayfası, geçmiş, yetersiz bakiye modal).

**Neden bu sıra?** Aşama 1 hiçbir harici bağımlılık gerektirmez ve mevcut tüketim akışını daha sağlam bir temele (audit-trail'li ledger) taşır — bu, iyzico geldiğinde `add_credits`'in hazır olması demektir. Aşama 2'nin tüm yükleme akışı Aşama 1'in `add_credits` helper'ının üzerine oturur.

---

## Aşama 1 — Ledger Altyapısı (key beklemeden)

### Adım 1.1 — `credit_transactions` modeli

- **Oluştur:** `backend/app/models/credit_transaction.py`
- **Ne yapılacak:** `docs/06 §5.2` DDL'ini SQLAlchemy ORM'e çevir. `AuditLog` modelini (`app/models/audit_log.py`) birebir desen olarak kullan: `Base`'den türe, `UUID(as_uuid=True)` PK `default=uuid.uuid4`, `JSONB` metadata, `TIMESTAMP(timezone=True) server_default=func.now()`.
  - Kolonlar: `id` (UUID PK), `user_id` (UUID FK → `users.id`, **`ondelete="RESTRICT"`** — TTK m.82, 10 yıl saklama; `nullable=False`), `amount` (Integer, NOT NULL; pozitif=yükleme, negatif=tüketim), `reason` (String/Text NOT NULL), `reference_id` (String/Text nullable — iyzico paymentId / advice UUID), `idempotency_key` (String, **UNIQUE**, nullable — tüketimde null, satın almada dolu), `extra` (JSONB nullable — **dikkat:** `metadata` SQLAlchemy'de rezerve isim; kolon ismi DB'de `metadata` kalsa da Python attribute `extra` ya da `meta` olmalı; `AuditLog` ile tutarlı olması için **`extra` kullan**, DDL'deki `metadata` kolon adını `extra` olarak hizala VE doc 06 §5.2/§6.1 JSON örneklerini güncelle), `created_at` (TIMESTAMPTZ NOT NULL `server_default=func.now()`).
  - Index'ler `__table_args__`: `ix_credit_transactions_user_id` (`user_id`), `ix_credit_transactions_created_at` (`created_at` DESC). `idempotency_key` zaten UNIQUE constraint ile implicit index alır.
- **Karar:** Doc 06 §5.2'de kolon adı `metadata`; SQLAlchemy Declarative'de `metadata` Base attribute'u ile çakışır → **Python attribute `extra`**, DB kolon adı da `extra` (AuditLog ile tutarlılık; doc 06'daki `metadata` JSON anahtarı plan kapsamında `extra`'ya çevrilecek — `doc-expert`'e doc 06 senkron notu).
- **Delege:** `dba` (şema kararları) + `backend-expert` (ORM).
- **Bağımlılık:** yok.

### Adım 1.2 — Migration

- **Oluştur:** `backend/alembic/versions/<yeni_hash>_add_credit_transactions.py`
- **Ne yapılacak:** `down_revision = "e2f3a4b5c6d7"`. `op.create_table("credit_transactions", ...)` doc 06 §5.2 DDL ile birebir; `gen_random_uuid()` yerine model-side `uuid.uuid4` kullanıldığı için server_default opsiyonel (model default yeterli — ama prod tutarlılığı için `server_default=sa.text("gen_random_uuid()")` eklenebilir; `pgcrypto`/`gen_random_uuid` PG 13+ built-in). `ForeignKey ondelete="RESTRICT"`. İki index + unique constraint. `downgrade()` `drop_table`.
- **Test/doğrulama:** `alembic upgrade head` lokal Docker test ortamında (Windows native değil — bkz. memory `tech_local_test_env_docker`) çalışmalı; `alembic downgrade -1` geri almalı. Migration zincir kontrolü: `alembic history` head'in tek olduğunu doğrula.
- **Delege:** `dba`.
- **Bağımlılık:** Adım 1.1 (model alanları migration ile bire bir).

### Adım 1.3 — Pydantic şemaları

- **Oluştur:** `backend/app/schemas/credit.py`
- **Ne yapılacak:** Pydantic v2 (`model_config = ConfigDict(from_attributes=True)` — proje kuralı DEPS-001, `class Config` YASAK):
  - `CreditTransactionOut`: `id`, `amount`, `reason`, `reference_id`, `extra`, `created_at`.
  - `CreditBalanceOut`: `balance: int` + `transactions: PaginatedResponse[CreditTransactionOut]` (mevcut `app/schemas/pagination.py::PaginatedResponse[T]` reuse) **veya** doc 06 §6.1'deki düz şekil (`balance` + `transactions: list` + `pagination` objesi). **Karar:** Projede PERF-001 standardı `PaginatedResponse[T]`; ona hizala — `GET /credits` → `{ balance, transactions: PaginatedResponse[CreditTransactionOut] }`. Doc 06 §6.1 örneği buna göre güncellenecek (`doc-expert`).
- **Delege:** `backend-expert`.
- **Bağımlılık:** Adım 1.1.

### Adım 1.4 — `core/credits.py` helper (kritik)

- **Oluştur:** `backend/app/core/credits.py`
- **Ne yapılacak:** İki async helper. **Her ikisi de caller'ın transaction'ı içinde çalışır — kendileri commit ETMEZ** (advice.py tek transaction garantisi için kritik; commit caller'a bırakılır, `log_audit` deseniyle aynı felsefe).

  - `async def deduct_credits(db, *, user_id, amount, reason, reference_id=None, extra=None) -> int`:
    1. `SELECT ... FROM users WHERE id=user_id FOR UPDATE` (`select(User).where(...).with_for_update()`) → satır kilidi (doc 06 §8.3). Çok-kullanıcılı yarış durumunu önler; tek-sahip senaryosunda da geleceğe hazır.
    2. `if (user.credit_balance or 0) < amount: raise HTTPException(402, "Yetersiz kredi...")`.
    3. `user.credit_balance = (user.credit_balance or 0) - amount`.
    4. `db.add(CreditTransaction(user_id=user_id, amount=-amount, reason=reason, reference_id=reference_id, extra=extra))` — **negatif amount** (tüketim).
    5. `await db.flush()` (commit DEĞİL) → yeni bakiyeyi döndür.
    - `amount` daima **pozitif int** alınır; ledger'a `-amount` yazılır. Çağıran "kaç kredi düşülecek" verir.
  - `async def add_credits(db, *, user_id, amount, reason, reference_id=None, idempotency_key=None, extra=None) -> int`:
    1. (idempotency_key verildiyse) önce `SELECT ... FROM credit_transactions WHERE idempotency_key=key` — varsa **no-op**, mevcut bakiyeyi döndür (webhook çift-teslimat koruması; Aşama 2'de kullanılır).
    2. `SELECT User ... FOR UPDATE`.
    3. `user.credit_balance += amount`.
    4. `db.add(CreditTransaction(..., amount=+amount, idempotency_key=key, ...))` — **pozitif amount**.
    5. `await db.flush()` → yeni bakiye.
    - Aşama 1'de `add_credits` yalnızca testlerde + ileride manuel/seed için kullanılır; webhook Aşama 2.
- **Karar/risk (SELECT FOR UPDATE):** `with_for_update()` async SQLAlchemy + asyncpg ile çalışır; ancak satır kilidi yalnızca **aktif transaction içinde** anlamlıdır. `get_db` dependency'sinin session'ı request boyunca tek transaction olmalı (mevcut advice.py tek `db.commit()` ile bu varsayımı zaten kullanıyor). Helper commit etmediği için kilit, caller commit/rollback'e kadar tutulur — istenen davranış.
- **Karar/risk (negatif bakiye tutarlılığı):** DB `CHECK (credit_balance >= 0)` (`ck_users_credit_balance_nonnegative`) son savunma hattı; helper'daki 402 kontrolü ilk hat. `amount` pozitif int dışında gelirse (0/negatif) `ValueError` fırlat — defansif.
- **Delege:** `backend-expert` + `security-expert` (kilit/yarış inceleme).
- **Bağımlılık:** Adım 1.1, 1.3.

### Adım 1.5 — `advice.py` refactor (davranış değişmeden)

- **Dokunulacak:** `backend/app/api/v1/advice.py`
- **Ne yapılacak:** Mevcut satır 92-93 (`advice.credits_used = ADVICE_COST` + `current_user.credit_balance -= ADVICE_COST`) → `deduct_credits()` çağrısına taşı. **Davranış birebir korunmalı:**
  - Ön-kontrol (satır 63-67, `credit_balance < ADVICE_COST → 402`) **AI çağrısından ÖNCE kalır** (boşuna LLM çağırmamak için). Bu erken-çıkış optimizasyonu korunur.
  - AI çağrısı (`advisor.generate`) başarılı olduktan **sonra** `deduct_credits(db, user_id=current_user.id, amount=ADVICE_COST, reason="ai_advice_medium", reference_id=str(advice.id), extra={"horizon": payload.horizon, "snapshot_date": ...})` çağrılır. `deduct_credits` içindeki `FOR UPDATE` + ikinci 402 kontrolü, ön-kontrol ile AI çağrısı arasındaki süre içinde başka bir isteğin krediyi tükettiği nadir yarışı yakalar (defence-in-depth).
  - `advice.credits_used = ADVICE_COST` korunur (mevcut `investment_advice.credits_used` kolonu — ledger ile çift kayıt değil, biri tavsiye-bazlı denormalize alan, diğeri global defter).
  - `await log_audit(...)` çağrısı korunur; `credit_balance_after` artık `deduct_credits` dönüşünden alınır.
  - **`await db.commit()` TEK commit olarak kalır** — advice + ledger insert + balance update + audit aynı transaction. `deduct_credits` flush eder, commit etmez → atomiklik korunur.
  - **Kritik garanti (değişmez):** AI fail → `advisor.generate()` exception → `deduct_credits`'e hiç gelinmez → kredi düşmez, ledger'a satır yazılmaz.
- **Karar:** `advice.credits_used` denormalize alan olarak **kalsın** (silme — breaking change + mevcut testler). Ledger ek katman, replacement değil.
- **Delege:** `backend-expert` (refactor) + `ai-expert` (advice akış sahibi onay).
- **Bağımlılık:** Adım 1.4.

### Adım 1.6 — `GET /credits` endpoint + router kaydı

- **Oluştur:** `backend/app/api/v1/credits.py`
- **Dokunulacak:** `backend/app/api/v1/router.py` (import + `api_router.include_router(credits.router)` — `credit_cards` satırının yanına; **isim çakışması yok**: prefix `/credits` vs `/credit-cards`).
- **Ne yapılacak:** `credit_cards.py` router desenini taklit et (`APIRouter(prefix="/credits", tags=["credits"])`, `Annotated[User, Depends(get_current_user)]`, `Annotated[AsyncSession, Depends(get_db)]`).
  - `GET /credits` (`PageParams` query: `limit`, `offset`): `current_user.credit_balance` + `select(CreditTransaction).where(user_id==current_user.id).order_by(desc(created_at)).limit().offset()` + `select(func.count())` total. IDOR koruması: daima `current_user.id` filtresi (kullanıcı yalnızca kendi defterini görür). `CreditBalanceOut` döner.
  - Aşama 2 endpoint'leri (`checkout`, `webhook`) bu dosyaya eklenecek — şimdilik sadece `GET`.
- **Rate limit:** `GET /credits` okuma — özel limit gereksiz (global default yeterli).
- **Delege:** `backend-expert`.
- **Bağımlılık:** Adım 1.1, 1.3.

### Adım 1.7 — Audit action (opsiyonel, küçük)

- **Dokunulacak:** `backend/app/services/audit.py`
- **Ne yapılacak:** `AuditAction` enum'una Aşama 2 için yer hazırla: `CREDIT_PURCHASE = "credit.purchase"`, `CREDIT_WEBHOOK_RECEIVED = "credit.webhook"`. Aşama 1'de zorunlu değil (tüketim zaten `ADVICE_GENERATE` ile audit'leniyor). İstenirse Aşama 2'ye ertelenebilir.
- **Delege:** `security-expert` / `backend-expert`.

### Adım 1.8 — Testler (Aşama 1)

- **Oluştur:**
  - `backend/tests/unit/test_credits_helper.py` — `deduct_credits`/`add_credits` birim testleri.
  - `backend/tests/integration/test_credits_api.py` — `GET /credits` + advice akışı entegrasyonu.
- **Test stratejisi (proje kuralları: `make_user` fixture, TRUNCATE izolasyonu TEST-004, `age_confirmed=True`):**
  - `deduct_credits` happy path: bakiye 10, düş 3 → bakiye 7, ledger'da `amount=-3 reason="ai_advice_medium"` 1 satır.
  - `deduct_credits` yetersiz bakiye: bakiye 0 → `HTTPException 402`, ledger'a satır YOK, bakiye değişmedi (rollback).
  - `add_credits` happy path: +150 → bakiye artar, ledger `amount=+150`.
  - `add_credits` idempotency: aynı `idempotency_key` ile 2 kez → ikinci no-op, bakiye 1 kez arttı, ledger 1 satır.
  - **advice refactor regresyonu (en kritik):** mevcut `test_advice*` testleri **değişmeden geçmeli** (davranış korundu). Ek: başarılı tavsiye sonrası `credit_transactions`'da `amount=-1` satır + `reference_id=advice.id` doğrula. AI fail (mock exception) → kredi düşmedi + ledger boş.
  - `GET /credits`: bakiye + paginated geçmiş; IDOR — başka kullanıcının token'ıyla yalnızca kendi kayıtları (DB constraint + filtre).
  - DB `CHECK (credit_balance >= 0)` — `deduct_credits` 402'yi DB'ye varmadan yakalar; ama doğrudan negatif yazma denemesi `IntegrityError` (defansif test).
- **Delege:** `test-expert`.
- **Bağımlılık:** Adım 1.4, 1.5, 1.6.

### Aşama 1 — ADVICE_COST kararı

`advice.py::ADVICE_COST = 1` **şimdilik 1 kalsın** (doc 06 §0 backlog notu: "fiyatlandırma kesinleşince hizalanır"). 5/10 vade ayrımına hizalamak fiyatlandırma + frontend "yetersiz bakiye" mesajları + mevcut testleri kırar → ayrı backlog. **Tek değişiklik:** ledger `reason` alanı şimdiden anlamlı yazılsın — `reason="ai_advice_medium"` (5/10 modeline geçince `ai_advice_long` eklenir, geçmiş veri analiz edilebilir kalır). `ADVICE_COST` sabiti yerinde kalır; ileride `calculate_advice_cost(horizon, asset_count)` (doc 06 §3.1) ile değiştirilebilir hale gelir.

---

## Aşama 2 — iyzico Satın Alma (API key gelince)

> Tetikleyici: `IYZICO_API_KEY` + `IYZICO_SECRET_KEY` elde. Sandbox ile başlanır (`sandbox-api.iyzipay.com`, test kartları doc 06 §7.4).

### Adım 2.1 — Konfigürasyon

- **Dokunulacak:** `backend/app/config.py` (`Settings`: `iyzico_api_key: str = ""`, `iyzico_secret_key: str = ""`, `iyzico_base_url: str = "https://sandbox-api.iyzipay.com"`, `iyzico_callback_url`, `iyzico_webhook_url` — hepsi default boş; mevcut `anthropic_api_key = ""` deseni). `backend/.env.example` örnek satırlar.
- **Karar:** Key boşken `checkout`/`webhook` 503 "ödeme yapılandırılmamış" döner (Aşama 1 etkilenmez, opt-in).
- **Delege:** `backend-expert` + `devops` (prod secret → SealedSecret).

### Adım 2.2 — Kredi paketleri sabit tablosu

- **Oluştur:** `backend/app/core/credit_packages.py` — `CREDIT_PACKAGES` dict (doc 06 §2): `starter` (50 kredi / 29₺), `standard` (150 / 69₺), `professional` (500 / 199₺). Tek doğruluk kaynağı; checkout amount + weblook credit miktarı buradan. **Fiyat backend'de sabit** — frontend'den amount asla kabul edilmez (manipülasyon koruması).
- **Delege:** `finance-expert` (fiyat/KDV) + `backend-expert`.

### Adım 2.3 — iyzico servis wrapper

- **Oluştur:** `backend/app/services/iyzico.py` — `httpx` ile REST (doc 06 §7.3: SDK sync-only, REST önerilir). `BaseIntegration` deseni gerekmez (ödeme sağlayıcısı, veri kaynağı değil) ama async + tek sorumluluk. `initialize_checkout(package, conversation_id, callback_url)` → checkout URL; HMAC imza üretimi (auth header) doc 06 §8.2 deseni.
- **Delege:** `backend-expert` + `security-expert` (HMAC + TLS).

### Adım 2.4 — `POST /credits/checkout`

- **Dokunulacak:** `backend/app/api/v1/credits.py` (Aşama 1'de oluşturuldu).
- **Ne yapılacak:** `package` + `idempotency_key` (UUID v4, client üretir) al. Paket doğrula (geçersiz → 400). Aynı `idempotency_key` ile `credit_transactions`'da kayıt varsa 409. iyzico `initialize_checkout` → `{checkout_url, conversation_id, expires_at}`. **Bu aşamada ledger'a HENÜZ yazılmaz** — kredi yalnızca webhook `success`'te eklenir (ödeme onayı). İsteğe bağlı: `pending` durumu için ayrı tablo yerine idempotency_key kontrolünü webhook'ta yapmak yeterli (doc 06 §8.1 — basit tutuldu).
- **Rate limit:** `@limiter.limit("3/minute")` (doc 06 §6.2, ödeme spam).
- **Delege:** `backend-expert`.

### Adım 2.5 — `POST /credits/webhook` (public, HMAC)

- **Dokunulacak:** `backend/app/api/v1/credits.py`.
- **Ne yapılacak:** Auth YOK (iyzico çağırır) ama:
  1. HMAC imza doğrula (`X-IYZ-SIGNATURE`, `verify_iyzico_signature`, doc 06 §8.2) — fail → 401 (ama iyzico retry'ı için dikkatli; geçersiz imza gerçekten reddedilmeli).
  2. **Idempotency:** `conversation_id` (= `idempotency_key`) ile `credit_transactions` kontrol — zaten varsa no-op, `{"received": true}` 200 (çift-teslimat). Bu kontrol `add_credits(idempotency_key=...)` içine gömülü (Adım 1.4) → tek yerde.
  3. `status == "success"` → `add_credits(db, user_id, amount=<paket kredisi>, reason="purchase", reference_id=<iyzico paymentId>, idempotency_key=conversation_id, extra={"package": ..., "amount_tl": ..., "iyzico_status": ...})` → **tek transaction** commit (ledger + balance birlikte; tutarlılık garantisi Aşama 1 helper'ından gelir).
  4. `status == "failure"` → log + `{"received": true}` (kredi eklenmez).
  5. **Daima 200 döndür** (imza fail hariç) — iyzico retry fırtınasını durdurmak için (doc 06 §6.3).
- **Risk (idempotency ↔ tutarlılık):** `idempotency_key UNIQUE` + `add_credits` içindeki ön-SELECT, çift webhook'ta çift kredi vermeyi engeller. Yarış (iki webhook eşzamanlı) → `INSERT` UNIQUE ihlali → `IntegrityError` yakala → rollback + "zaten işlendi" kabul (advice.py refresh-token rotation'daki `IntegrityError` idempotent deseni gibi). `user_id`'yi webhook'tan değil, checkout'ta kaydedilen `conversation_id → user` eşleşmesinden çöz — webhook gövdesindeki user'a güvenme.
  - **Eşleşme sorunu:** checkout'ta ledger'a yazmıyorsak `conversation_id → user_id` nereden? **Karar:** checkout'ta `credit_transactions`'a `amount=0, reason="checkout_pending"` placeholder satır (idempotency_key + user_id + paket extra) yaz; webhook `success`'te bu satırı bulup `amount`'ı paket kredisine güncelle + bakiye ekle. Alternatif: ayrı `pending_payments` tablosu (daha temiz ama +1 migration). **Öneri:** placeholder satır (migration yok, basit) — ama `GET /credits` listesinde `amount=0` satırları filtrele (`reason != "checkout_pending"` ya da `amount != 0`). Bu inceyi Aşama 2 başında `dba` + `backend-expert` netleştirir; iki seçenek de geçerli.
- **Delege:** `security-expert` (HMAC + public endpoint sertleştirme) + `backend-expert`.

### Adım 2.6 — Webhook testleri

- **Oluştur:** `backend/tests/integration/test_credits_webhook.py`
- **Strateji:** iyzico HTTP mock'la. Geçerli imza + `success` → kredi eklendi (1 kez). Çift webhook (aynı conversation_id) → kredi 1 kez (idempotency). Geçersiz imza → 401, kredi eklenmedi. `failure` status → kredi yok. Eşzamanlı webhook (`IntegrityError`) → idempotent.
- **Delege:** `test-expert`.

### Adım 2.7 — Frontend

- **Oluştur/dokunulacak:**
  - `frontend/lib/api/credits.ts` (veya `lib/api.ts`'e ekleme) — `getCredits()`, `checkout(package, idempotencyKey)` API client (mevcut `authedFetch` 401→refresh deseni reuse).
  - `frontend/app/dashboard/credits/page.tsx` — satın alma sayfası (3 paket kartı, doc 06 §2) + kredi geçmişi tablosu (doc 06 §9.3, paginated).
  - `frontend/app/dashboard/layout.tsx` (dokunulacak) — header'a bakiye göstergesi `💰 N kredi` (doc 06 §9.1); `< 10` kırmızı badge (§9.4).
  - `frontend/app/_components/InsufficientCreditsModal.tsx` (yeni) — yetersiz bakiye modal (doc 06 §9.2); mevcut `ConfirmDialog`/`useFocusTrap` (A11Y-001) desenini reuse, 402 yanıtında tetiklenir.
  - i18n: `app/_i18n/dictionaries/{tr,en}.json` — `credits.*` anahtarları (tr+en parite zorunlu, i18n-002 kuralı).
- **Akış:** checkout → `checkout_url`'e redirect → iyzico → callback URL geri dönüş → `GET /credits` ile güncel bakiye.
- **Delege:** `frontend-expert`.

### Adım 2.8 — Uyumluluk (KVKK/TTK/6502)

- e-Arşiv fatura (doc 06 §10.3), cayma hakkı 14 gün (6502, §9.5), KDV %20 (§8.5). **Faz 4'e ertelenebilir** ama yasal zorunlu olanlar (e-Arşiv) production satış öncesi `compliance-expert` ile netleştirilmeli — Aşama 2 teknik akışını bloklamaz, satışı bloklar.
- **Delege:** `compliance-expert`.

---

## Cross-Cutting Standartlar (mimar kararı — tüm ajanlar uygular)

- **Ledger ↔ balance tutarlılığı:** Her bakiye değişikliği **tek transaction**'da hem `credit_transactions` insert hem `users.credit_balance` update içermeli. Helper commit etmez; commit caller'da. İstisna yok.
- **Pydantic v2:** `model_config = ConfigDict(...)`, `@field_validator + classmethod`. `class Config` yasak (DEPS-001).
- **IDOR:** Her `GET`/list `current_user.id` filtresi.
- **Audit:** `log_audit` best-effort, ana commit'ten önce.
- **Test izolasyonu:** TRUNCATE autouse, `make_user` fixture, `age_confirmed=True`.
- **Naming:** kod İngilizce, doküman/commit Türkçe.
- **Doc senkron:** `metadata`→`extra` kolon adı + `PaginatedResponse[T]` hizalaması doc 06'da güncellenmeli (`doc-expert`, push öncesi).

## Risk Özeti

| Risk | Etki | Önlem |
|------|------|-------|
| advice.py refactor davranış kayması | AI fail'de kredi düşme regresyonu | Mevcut advice testleri değişmeden geçmeli; deduct AI çağrısından SONRA |
| SELECT FOR UPDATE async tuzağı | Kilit etkisiz / deadlock | Helper tek transaction içinde flush-only; commit caller'da |
| Webhook çift kredi | Para/kredi tutarsızlığı | `idempotency_key UNIQUE` + ön-SELECT + IntegrityError idempotent |
| Webhook'ta user spoofing | Yanlış kullanıcıya kredi | user_id checkout eşleşmesinden, webhook gövdesinden DEĞİL |
| Frontend amount manipülasyonu | Ucuza çok kredi | Fiyat backend `CREDIT_PACKAGES`'tan, client'tan amount alınmaz |
| `metadata` SQLAlchemy çakışması | Model import hatası | Kolon/attribute `extra` |

## Migration Doğrulaması

Head **`e2f3a4b5c6d7`** (`add_user_totp_columns`) — bu hash'ten zincirlenen başka migration yok (teyit edildi). Yeni migration: `down_revision = "e2f3a4b5c6d7"`. Aşama 1'de tek migration (`credit_transactions`). Aşama 2'de placeholder-satır yaklaşımı seçilirse ek migration GEREKMEZ; ayrı `pending_payments` tablosu seçilirse +1 migration (`down_revision` = Aşama 1 migration'ı).
