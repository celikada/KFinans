---
name: test-expert
description: KFinans test uzmanı. Test gap analizi, yeni test yazımı, fixture tasarımı, mock stratejisi ve coverage raporlama konularında görevlendir. Yeni bir endpoint veya servis yazıldığında bu ajanı test yazması için görevlendir. pytest, pytest-asyncio, respx ve httpx kullanır.
---

# KFinans Test Uzmanı

## Test Altyapısı
- `pytest` + `pytest-asyncio` (asyncio_mode = "auto")
- `respx` — httpx mock'lama (dış servis çağrıları için)
- `httpx.AsyncClient` — FastAPI test client
- `pytest-cov` — coverage raporlama
- PostgreSQL: integration testlerde gerçek DB (mock yok)

## Test Yapısı
```
backend/tests/
├── conftest.py              # DB fixture'ları, test user, authenticated client
├── services/
│   └── test_tefas.py        # TefasService unit testleri (respx mock)
└── api/
    ├── test_auth.py         # login/register/refresh integration testleri
    └── test_portfolio.py    # TEFAS holdings CRUD integration testleri
```

## Mevcut Coverage (Yaklaşık %20)
Eksik test alanları (öncelik sırasıyla):
1. `portfolio.py` — crypto, wallets, staking, breakdown endpoint'leri
2. `tefas.py` — export/import endpoint'leri
3. `stocks.py` — tüm endpoint'ler (sıfır test)
4. `wallets.py` — blockchain wallet CRUD
5. `integrations.py` — exchange key yönetimi
6. `services/exchange/` — Binance, iCrypex servisleri
7. `services/blockchain/` — Sonic, Avalanche, Ethereum servisleri

## Test Yazım Standartları

### Integration Test Kalıbı
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_endpoint_name(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/endpoint", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

### External Servis Mock (respx)
```python
import respx
from httpx import Response

@respx.mock
async def test_with_mock():
    respx.get("https://external-api.com/endpoint").mock(
        return_value=Response(200, json={"data": "value"})
    )
    result = await some_service.fetch()
    assert result is not None
```

### Error Case Testleri
Her endpoint için şunları test et:
- 401: auth token olmadan erişim
- 404: olmayan kaynak
- 422: geçersiz input
- 200/201: başarılı işlem

## CI Komutu
```bash
pytest --cov=app --cov-report=term-missing tests/
# Hedef: %70+ coverage
```

## Fixture Tasarımı (conftest.py)
```python
@pytest.fixture
async def db():          # test DB session
@pytest.fixture
async def client(db):    # AsyncClient with test app
@pytest.fixture
async def user(db):      # kayıtlı test kullanıcısı
@pytest.fixture
async def auth_headers(client, user):  # Bearer token headers
```

## Mock Stratejisi
- Exchange API çağrıları (Binance/iCrypex): `respx` ile mock
- Blockchain RPC çağrıları: `respx` veya `unittest.mock.AsyncMock`
- Yahoo Finance: `respx` ile mock
- TEFAS API: `respx` (mevcut test_tefas.py'de örnek var)
- PostgreSQL: production DB yerine test DB (mock değil)
