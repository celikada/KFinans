# KFinans Reusability Patterns

> **Amaç:** Yeni geliştiriciler ve yeni feature için kullanılabilir kod pattern'leri kataloğu.
> **İlgili:** [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md) §2 Yeniden Kullanılabilirlik

**Durum:** Taslak — pattern listesi mevcut + eksik abstraction backlog. Sprint 3'te genişler.

## 1. Mevcut Reusable Pattern'ler

### 1.1 `BaseIntegration` (kanıtlanmış pattern)

`app/services/base.py::BaseIntegration` 13 servis (3 exchange + 10 blockchain) tarafından tutarlı kullanılır.

```python
class BaseIntegration(ABC):
    @abstractmethod
    async def fetch(self) -> list[AssetData]:
        """Kullanıcı için tüm asset'leri çek + AssetData listesi döndür."""
```

Yeni exchange/blockchain ekleme effort: ~150 LOC.

### 1.2 `AssetData` uniform return

Tüm `fetch()` aynı dataclass döner:
```python
@dataclass
class AssetData:
    asset_type: str  # "crypto" | "staked_crypto" | "fund" | "stock" | ...
    symbol: str
    name: str
    quantity: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
    provider: str
    # ...
```

### 1.3 `masking.py` — PII helper'lar

```python
from app.core.masking import mask_email, hash_email, mask_address
mask_email("celikada@gmail.com")  # → "c******a@gmail.com"
hash_email("celikada@gmail.com")  # → "a1b2c3d4" (SHA-256 first 8)
mask_address("0xABC...XYZ")       # → "0xABCD...WXYZ" (ilk 6 + son 4)
```

**Kullanım:** Logger PII filter, audit log extra, JSON response serializer.

### 1.4 `MultiFernet` key rotation

`app/core/security.py::encrypt_secret/decrypt_secret` zero-downtime key rotation destekler:

```bash
# Rotation prosedür:
# 1. Yeni key üret: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# 2. FERNET_KEYS_SECONDARY=["<eski_primary>"] env'e ekle, restart
# 3. FERNET_KEY=<yeni> env'i güncelle, restart
# 4. Background job tüm row'ları re-encrypt edinceye kadar bekle
# 5. Tamamlanınca secondary'leri kaldır
```

### 1.5 `audit_log` Enum-driven pattern

```python
from app.services.audit import log_audit, AuditAction
await log_audit(
    db,
    request,
    action=AuditAction.WALLET_ADD,
    user_id=user.id,
    extra={"chain": "ethereum", "address_fp": fp},  # PII-safe, mask_email kullan
)
```

Best-effort (try/except yutar — endpoint bozulmaz).

### 1.6 `PaginatedResponse[T]` (PERF-001)

```python
from app.schemas.pagination import PaginatedResponse
@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
async def list_audit_logs(limit: int = 50, offset: int = 0, ...):
    return PaginatedResponse(items=..., total_count=..., has_next=...)
```

### 1.7 Frontend `lib/format.ts` + `useUsdRate`

```tsx
import { TLValue, formatCurrency } from "@/lib/format";
// TL/USD toggle: <TLValue value={tlAmount} /> — kullanıcı seçimine göre
```

### 1.8 `ConfirmDialog` (FE-013)

```tsx
import { useConfirm } from "@/app/_components/ConfirmDialog";
const confirm = useConfirm();
if (!(await confirm("Silinsin mi?", { destructive: true }))) return;
```

### 1.9 conftest fixture — Test isolation

```python
# tests/conftest.py
make_user(client, "test@example.com")  # auth + verify email + login → headers dict
```

**Marker pattern:**
```python
@pytest.mark.password_policy_enabled  # default bypass; explicit testlerde aktive
```

### 1.10 Frontend i18n hook

```tsx
import { useTranslation } from "@/app/_i18n/I18nProvider";
const { t } = useTranslation();
return <h1>{t("auth.loginTitle")}</h1>;
```

Cookie-based, sayfa reload yok.

---

## 2. Eksik Abstraction'lar (Backlog — Sprint 3+)

### 2.1 `AsyncTTLCache` (~200 satır dedup)

5 blockchain servisinde (`bitcoin`, `solana`, `polkadot`, `litecoin`, `avalanche`) `_BALANCE_CACHE` + `_INFLIGHT` + `_cache_lock` global'leri birebir kopyalanmış.

**Önerilen:**
```python
# app/core/cache.py
class AsyncTTLCache:
    def __init__(self, ttl_seconds: int): ...
    async def get_or_fetch(self, key: str, fetcher: Callable) -> Any:
        """Single-flight pattern + TTL cache"""
```

### 2.2 `EVMService` + `BinanceCompatibleService` base'leri

- Ethereum + Avalanche C-Chain `evm_tokens.py` multi-RPC fallback aynı pattern
- BinanceService + BinanceTRService %80 ortak earn pagination kodu

### 2.3 `BaseLLMProvider` Protocol (Anthropic SPOF)

`advisor.py` Anthropic SDK direkt import + 7 Anthropic-spesifik exception. SOFP:

```python
class BaseLLMProvider(Protocol):
    async def generate(self, system: str, user: str, max_tokens: int) -> LLMResponse: ...

# Adapters: AnthropicProvider, OpenAIProvider, GeminiProvider
# Fallback chain: settings.llm_providers = ["anthropic", "openai"]
```

### 2.4 `BaseEmailProvider`

Resend SDK doğrudan import — SendGrid/Mailgun fallback için adapter pattern.

### 2.5 `services/db_lock.py` — PostgreSQL `pg_try_advisory_lock` abstraction

`scheduler.py` Postgres-spesifik. SQLite test'lerde fail. Abstraction:

```python
async def try_advisory_lock(db: AsyncSession, key: int) -> bool:
    """PostgreSQL pg_try_advisory_lock; SQLite fallback (sentinel row)"""
```

### 2.6 Frontend `Card` + `PageShell` + `EmptyState` primitive'leri

Tailwind class duplikasyonu 68 yerde:
```tsx
// MEVCUT — copy-paste 68 yer
<div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">...</div>

// ÖNERİLEN
<Card>...</Card>
<PageShell title="..." actions={...}>...</PageShell>
<EmptyState icon="..." message="..." />
```

### 2.7 `lib/api.ts` modüler split (1511 satır → ~150 satır × 10)

```
lib/api/
├── client.ts        # request() + auth + 401 redirect
├── auth.ts          # login, register, mfa
├── portfolio.ts     # snapshot, breakdown, wallets
├── tefas.ts
├── stocks.ts
├── expenses.ts
├── ...
```

### 2.8 `tests/_mocks/external.py` factory'ler

```python
def mock_tefas_export(fund_code: str, rows: list[dict]) -> respx.Route: ...
def mock_hibp_clean(prefix: str) -> respx.Route: ...
def mock_glacier_balance(p_address: str, balance: dict) -> respx.Route: ...
```

### 2.9 Playwright fixture'lar (login + MFA setup)

```ts
// playwright/fixtures.ts
export const loggedInPage = test.extend({
  page: async ({ page }, use) => {
    await page.goto('/login');
    await page.fill(...);
    await use(page);
  },
});
```

### 2.10 `audit.py::tenant_id` (multi-tenant SaaS hazırlık)

audit_logs tablosuna `tenant_id` kolonu — multi-tenant ayrım için. Şu an tek-tenant olduğu için NULL default.

### 2.11 GitLab CI shared templates

`mayotek/gitlab-ci-templates` shared project:
- `.kaniko-build.yml` template
- `.python-pytest.yml` template
- `.k8s-deploy.yml` template

KFinans `.gitlab-ci.yml` 257 → 40 satır.

### 2.12 `lib/branding.ts` central config (white-label hazırlık)

```ts
export const BRAND = {
  name: "KFinans",
  productOf: "Mayotek",
  domain: process.env.NEXT_PUBLIC_DOMAIN ?? "kfinans.app",
  supportEmail: "iletisim@kfinans.app",
  // logo, colors, ...
};
```

## 3. Referans

- [`../audits/2026-05-22-master-audit.md`](../audits/2026-05-22-master-audit.md) §2
- [`../audit-2026-05-22/backend-notes.md`](../audit-2026-05-22/backend-notes.md) §Reusability
- [`../audit-2026-05-22/frontend-notes.md`](../audit-2026-05-22/frontend-notes.md)
- [`../audit-2026-05-22/test-notes.md`](../audit-2026-05-22/test-notes.md)
