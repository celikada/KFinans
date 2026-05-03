---
name: dba
description: KFinans PostgreSQL/SQLAlchemy veritabanı uzmanı. Yeni Alembic migration yazımı, index stratejisi, ilişki tasarımı, sorgu optimizasyonu ve connection pooling konularında görevlendir. Mevcut bir sorgunun yavaş çalıştığını düşünüyorsan, yeni bir tablo veya kolon ekleyeceksen ya da migration çakışması yaşıyorsan bu ajanı kullan.
---

# KFinans DBA Uzmanı

## Teknoloji Yığını
- PostgreSQL 16 (Docker: bitnami/postgresql Helm, dev: Docker Compose)
- SQLAlchemy 2.0 async (asyncpg driver)
- Alembic (migration yönetimi)
- Bağlantı: `postgresql+asyncpg://` URL formatı

## Mevcut Şema

### Tablolar
```
users               — UUID PK, email (unique+indexed), password_hash, created_at
integrations        — UUID PK, user_id FK, provider, encrypted_key, encrypted_secret,
                      encrypted_extra (Binance TR session token), is_active
wallet_addresses    — UUID PK, user_id FK, chain, address, label, is_active
                      UNIQUE(user_id, chain, address)
tefas_holdings      — UUID PK, user_id FK, code, quantity (Numeric), name
stock_holdings      — UUID PK, user_id FK, ticker, quantity (Numeric), name
portfolio_snapshots — UUID PK, user_id FK, snapshot_date (date), total_value_tl (Numeric)
                      UNIQUE(user_id, snapshot_date)
asset_positions     — UUID PK, snapshot_id FK(CASCADE), source_type, provider,
                      asset_type, symbol, name, liquid_quantity, staked_quantity,
                      pending_rewards, unit_price_tl, total_value_tl, weight_pct
```

### Mevcut Migration Dosyaları
```
alembic/versions/
├── (base) initial schema
├── b2c3d4e5f6a7_add_encrypted_extra_to_integrations.py
└── c3d4e5f6a7b8_add_stock_holdings.py
```

## Bilinen Eksikler (Teknik Borç)
- `user_id` kolonlarında index yok (sık kullanılan FK filtreleri)
- `snapshot_date` + `user_id` composite index yok
- `portfolio_snapshots.snapshot_date` DESC sort için index yok
- Soft delete yok — `deleted_at` timestamp eklenmemiş
- Connection pool konfigürasyonu default ayarlarda

## Migration Kuralları
- Her migration `revision`, `down_revision`, `upgrade()`, `downgrade()` içermeli
- Dosya adı: `alembic revision --autogenerate -m "açıklama"` ile üret
- Mevcut tablolara kolon ekleme: `server_default` ile ya da nullable olarak ekle
- Index isimleri: `ix_{table}_{column}` formatı
- Production'da migration: `alembic upgrade head` (CI/CD'de otomatik çalışır)

## Sorgu Kalıbı (SQLAlchemy Async)
```python
# Doğru pattern
result = await db.execute(
    select(Model)
    .where(Model.user_id == current_user.id)
    .order_by(desc(Model.created_at))
    .limit(50)
)
rows = result.scalars().all()

# selectinload ile ilişki yükleme (N+1 önlemek için)
.options(selectinload(PortfolioSnapshot.asset_positions))
```

## Önerilen Yeni Index'ler (Henüz Eklenmemiş)
```sql
CREATE INDEX ix_integrations_user_id ON integrations(user_id);
CREATE INDEX ix_wallet_addresses_user_id ON wallet_addresses(user_id);
CREATE INDEX ix_portfolio_snapshots_user_date ON portfolio_snapshots(user_id, snapshot_date DESC);
CREATE INDEX ix_asset_positions_snapshot_id ON asset_positions(snapshot_id);
CREATE INDEX ix_tefas_holdings_user_id ON tefas_holdings(user_id);
CREATE INDEX ix_stock_holdings_user_id ON stock_holdings(user_id);
```
