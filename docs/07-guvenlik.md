# Güvenlik Mimarisi

**Sahip ajan:** `security-expert`
**İlgili:** [uyumluluk-kvkk.md](./uyumluluk-kvkk.md), [api-referansi.md](./api-referansi.md)

---

## 1. Mevcut Fonksiyonel Gereksinimler (Aktif Korumalar)

| Koruma | Uygulama | Durum |
|--------|----------|-------|
| Şifre hash | bcrypt | ✅ Aktif |
| **Şifre politikası** (audit #5) | `core/password_policy.py` — zxcvbn (offline strength score) + HIBP k-anonymity (sızmış parola red); `hibp_check_enabled` env; register + reset akışında uygulanır | ✅ Aktif |
| **Hesap kilitleme (account lockout)** (SEC-002) | 10 ardışık başarısız login → 15 dk kilit (423 + `Retry-After`); `users.failed_login_count` + `users.locked_until`; başarılı login / şifre sıfırlama sayacı sıfırlar | ✅ Aktif |
| JWT imza | HS256 | ✅ Aktif |
| Token tipi ayrımı | `access` (type claim YOK) / `refresh` / `pre_mfa` | ✅ Aktif |
| **MFA — TOTP** (audit #5) | `api/v1/mfa.py` (pyotp, RFC 6238); `user.totp_secret` Fernet ciphertext + `totp_enabled` + `totp_recovery_codes` (bcrypt-hash, JSON list, tek kullanımlık); login 2-adımlı (`pre_mfa_token` 15 dk → `/mfa/verify`); `valid_window=1` (±30 sn) | ✅ Aktif |
| Exchange API key encryption | Fernet (AES-128-CBC) | ✅ Aktif |
| **Fernet key rotation** (SEC-012) | `core/security.py::_build_fernet` MultiFernet — encrypt primary (`FERNET_KEY`) ile, decrypt primary + `FERNET_KEYS_SECONDARY` (decrypt-only) listesini dolaşır; zero-downtime rotation | ✅ Aktif |
| **Şifre sıfırlama akışı** (SEC-001) | `POST /auth/forgot-password` + `/auth/reset-password`; `secrets.token_urlsafe(32)` reset token (1 saat TTL); anti-enumeration (generic 202); tek kullanımlık | ✅ Aktif |
| **Wallet adresi (xpub) encryption** (FAZ C1) | Fernet ciphertext + SHA-256 fingerprint lookup; `WalletAddress.address` hybrid_property transparent encrypt/decrypt | ✅ Aktif |
| CORS allowlist | `settings.cors_origins` (env'den) | ✅ Aktif |
| **TrustedHostMiddleware** (FAZ C3) | `settings.allowed_hosts` env'den; prod'da `["kfinans.app","www.kfinans.app","api.kfinans.app"]`; Host header injection koruması | ✅ Aktif |
| **SecurityHeadersMiddleware** (FAZ C2) | HSTS (1 yıl + preload) + X-Frame-Options DENY + X-Content-Type-Options + Referrer-Policy + CSP (default-src 'none') + Permissions-Policy + COOP + CORP + Server maskeleme | ✅ Aktif |
| **Frontend güvenlik header'ları** (FAZ C2) | `next.config.ts` async `headers()`; HSTS + CSP + X-Frame + Permissions-Policy + COOP HTML response'larında | ✅ Aktif |
| Rate limiting (auth endpoint'leri) | slowapi — `settings.redis_url` set ise Redis backend (multi-replica güvenli), yoksa MemoryStorage (`replicas=1`) | ✅ Aktif |
| **PII log filter** (SEC-010) | `core/log_filter.py::PIIFilter` root logger handler'larına eklenir (`install_pii_filter`, `main.py` import-time); email / IPv4 / JWT / Bearer token / kredi kartı PAN → maskelenir (3. parti kütüphane log sızıntısı defence-in-depth) | ✅ Aktif |
| **Request timing middleware** (PERF-004) | `core/middleware.py::RequestTimingMiddleware` — `X-Response-Time` header + slow request WARNING log + per-route p50/p95/p99 metrics; `/metrics/performance` `X-Metrics-Token` korumalı (token boş → 404) | ✅ Aktif |
| **File upload validation** (SEC-009) | `core/upload_validation.py::validate_excel_upload` 10 Excel import endpoint'inde; uzantı + boyut (`max_upload_size_mb`, default 5MB → 413) + magic byte (xlsx `PK\x03\x04` / xls OLE2 → polyglot 422) | ✅ Aktif |
| **Adres maskeleme (JSON response)** (BACK-013) | `core/masking.py::mask_address` Pydantic `field_serializer`; `WalletOut.address` / `WalletPositionOut.address` ilk 6 + son 4; full xpub yalnız audit'li opt-in Excel export | ✅ Aktif |
| **Exception sanitization** (SEC-007 + BACK-008) | `main.py` generic handler'lar (IntegrityError→409, SQLAlchemyError→500, Exception→500) `{detail, code, request_id}`; SEC-007 yakalanan 5 noktada `detail=f"...{e}"` kaldırıldı → `logger.exception` + generic mesaj | ✅ Aktif |
| **Swagger UI / OpenAPI prod'da kapalı** (P0 #7) | `settings.expose_swagger=False` default → `/docs`, `/redoc`, `/openapi.json` 404; endpoint enumeration vektörü kapatıldı | ✅ Aktif |
| **E-posta doğrulama zorunluluğu** | `email_verified=False` ise login 403 hard block | ✅ Aktif |
| **Doğrulama token'ı (TTL'li)** | `secrets.token_urlsafe(32)`, `verify_token_expires_at` (24 saat) | ✅ Aktif |
| **Account enumeration koruması** | `POST /auth/resend-verification` her zaman 202 döner | ✅ Aktif |
| **JWT blacklist + logout** | `revoked_tokens` tablosu (jti PK); `POST /auth/logout`; `get_current_user` ve `/auth/refresh` jti kontrolü | ✅ Aktif |
| **`jti` claim** | `create_access_token` ve `create_refresh_token` her token'a `uuid4.hex` jti ekler | ✅ Aktif |
| **Refresh token rotation** (FAZ C4) | `/auth/refresh` her çağrıda eski refresh `jti`'sini blacklist'e atar + yeni refresh üretir; sızan token ikinci kez kullanılamaz | ✅ Aktif |
| **`revoked_tokens` cleanup cron** (FAZ C5) | APScheduler her gün 03:00 Europe/Istanbul; `expires_at < now` kayıtları siler; DB sonsuz şişme koruması | ✅ Aktif |
| **Audit log** (FAZ C6) | `audit_logs` tablosu (user_id, action, resource, ip_address, user_agent, extra JSONB); kritik eylemler hook'lu (auth login/logout/register/password_reset, MFA, wallet/integration add/delete/export, snapshot.delete, account.soft_delete, consent, data_export — tam liste `AuditAction` enum); `GET /api/v1/audit-logs` endpoint (paginated, IDOR korumalı). IP kaynağı SEC-004 ile `request.client.host` | ✅ Aktif |
| **JWT TTL prod env override** (FAZ C4) | `ACCESS_TOKEN_EXPIRE_MINUTES=30` prod'da; dev=480 (8 saat) | ✅ Aktif |
| Health endpoint (auth gerektirmez) | `/health` | ✅ Aktif |
| Auth gerektiren endpoint'ler | `Depends(get_current_user)` | ✅ Aktif |
| User izolasyonu | `WHERE user_id == current_user.id` | ✅ Aktif |
| Pydantic input validation | Tüm request body'ler | ✅ Aktif |
| Servis katmanı logging | 9 servis dosyasında module-level logger | ✅ Aktif |
| **422 JSON serialize fix** (FAZ C1 bonus) | `RequestValidationError` handler'da `jsonable_encoder` ile ValueError → str (Pydantic 2 ctx serialize bug fix) | ✅ Aktif |
| Test kapsama (regresyon koruma) | IDOR (5 endpoint), security primitives (22 test), integrations leak (5 test), auth flow (21 test), **xpub encryption (7), security headers (7), refresh rotation (3), cleanup cron (2), audit log (9)** = 33 yeni FAZ C testi | ✅ Aktif |
| Soft delete altyapısı | `users.deleted_at` kolonu hazır (cron Faz 3) | ✅ Şema hazır |
| `users.credit_balance` (CHECK >= 0) | DB seviyesinde negatif bakiye koruması | ✅ Aktif |
| **CI/CD secret tarama** (FAZ B4) | gitleaks (her PR/push) + Trivy fs (deps + IaC HIGH/CRITICAL) + pip-audit (osv strict) + npm-audit (high) + CodeQL (Python + TS SAST) | ✅ Aktif |
| **Container image vulnerability scan** | `.gitlab-ci.yml` `scan` stage (`trivy-image-scan`, 2026-06-01) — build sonrası, **deploy öncesi gate**; tag image'ları HIGH/CRITICAL `--ignore-unfixed` → fail | ✅ Aktif |
| **Post-deploy smoke gate** | `.gitlab-ci.yml` `smoke` stage (`smoke-test`, 2026-06-01) — deploy sonrası 4-adımlı curl gate (HTTPS+cert, /health, bogus login→401, HSTS); prod bozuksa pipeline kırmızı | ✅ Aktif |
| **Startup secret görünürlüğü** | `app/core/startup_checks.py` (2026-06-01) — format/varlık kontrolü + opt-in canlı Resend probu (`VERIFY_RESEND_ON_STARTUP`); geçersiz key sessiz başarısızlığını yakalar | ✅ Aktif |
| **SonarQube quality gate (blocking)** | Yeni kod (new code) için violation + security hotspot review gate; gate fail → CI fail. `new_security_hotspots_reviewed=%100` zorunlu | ✅ Aktif |
| **GitOps secret yönetimi (SealedSecrets)** | bitnami sealed-secrets; `encryptedData` asimetrik şifreli, sadece cluster private key açar → repo'ya commit güvenli (`k8s/sealed-secrets.yaml`) | ✅ Aktif |
| **Branch protection** | GitHub `develop`+`main` (force-push + delete engelli); GitLab `develop`/`main` push=No one (MR-only) | ✅ Aktif |
| **DB TLS (transit şifreleme)** | asyncpg `connect_args` ssl; prod `require` (hostname + cert chain doğrulama AÇIK), cluster-içi `prefer` (self-signed defence-in-depth) — bkz. §14 | ✅ Aktif |

**Bu korumalar regresyon kabul etmez** — production'a çıkmadan önce düşürülemez. CI'da `test_idor.py`, `test_security.py`, `test_integrations_api.py` testleri bunları otomatik doğrular.

---

## 2. Tehdit Modeli

### 2.1 Saldırgan Profilleri

| Profil | Motivasyon | Hedef |
|--------|------------|-------|
| **Otomatik tarayıcı (bot)** | Toplu credential stuffing, kayıt spam | `/auth/login`, `/auth/register` |
| **Hesap hırsızı** | Bireysel kullanıcı hesabını ele geçirme | XSS, phishing, weak password |
| **API key hırsızı** | Kripto borsa fonlarına erişim | DB sızıntısı, Fernet key sızıntısı |
| **Yetkisiz veri erişimi** | Diğer kullanıcıların portföyü | IDOR (Insecure Direct Object Reference) |
| **DDoS** | Servis kesintisi | Tüm endpoint'ler |
| **Tedarik zinciri** | Bağımlılık yoluyla kod injekte | pip/npm paket güncellemeleri |

### 2.2 Veri Sınıflandırması

| Veri | Kritiklik | Şifreleme | Erişim |
|------|-----------|-----------|--------|
| Şifre | 🔴 Kritik | bcrypt (one-way hash) | Sadece login doğrulamasında |
| Exchange API key | 🔴 Kritik | Fernet (reversible) | Sadece pozisyon çekiminde decrypt |
| Binance TR session token | 🔴 Kritik | Fernet | Sadece TR earn fetch'te |
| JWT secret + Fernet master key | 🔴 Kritik | k8s Secret + sealed-secrets | Sadece backend pod |
| **Cüzdan adresleri (xpub dahil)** | 🔴 Kritik (FAZ C1'de yeniden sınıflandırıldı) | **Fernet (reversible)** + SHA-256 fingerprint lookup | Sadece blockchain pozisyon çekiminde decrypt |
| **Audit log IP/User-Agent** | 🟡 Orta | – | User kendi log'ları + (gelecek) admin |
| Portföy snapshot | 🟡 Orta | – | User izolasyonu |
| AI tavsiye içeriği | 🟢 Düşük | – | User izolasyonu |
| Email | 🟡 Orta | – | KVKK kapsamında |

> **Not (FAZ C1):** Wallet adresleri 🟡 Orta'dan 🔴 Kritik'e yükseltildi çünkü Bitcoin xpub formatından **tüm child public key'ler türetilebilir** (BIP-32 deterministic derivation). DB sızıntısında saldırgan kullanıcının BTC bakiye geçmişini blockchain'den görebilirdi. Migration `b3c4d5e6f7a8` ile Fernet şifreleme eklendi.

---

## 3. Kimlik Doğrulama (Authentication)

### 3.1 Kayıt → Doğrulama → Giriş → Yenileme Akışı

```
POST /auth/register {email, password, risk_profile}
  ↓ bcrypt(password)
  ↓ secrets.token_urlsafe(32) → verify_token (24 saat TTL)
  ↓ INSERT users (email_verified=False, verify_token, verify_token_expires_at)
  ↓ services/email.py::send_verification_email() (Resend)
  ↓ 201 Created (mail fail olsa bile user oluşur — kullanıcı bloklanmaz)

GET /auth/verify-email?token=...
  ↓ SELECT users WHERE verify_token=? AND verify_token_expires_at > now()
  ↓ UPDATE users SET email_verified=True, verify_token=NULL, verify_token_expires_at=NULL
  ↓ 200 OK (geçersiz/süresi dolmuş token → 400)

POST /auth/resend-verification {email}
  ↓ SELECT users WHERE email=?
  ↓ Eğer mevcut + doğrulanmamış: yeni token üret + mail gönder
  ↓ Aksi halde sessizce yut
  ↓ HER ZAMAN 202 (account enumeration koruması)

POST /auth/login
  ↓ _raise_if_locked() — locked_until > now → 423 Locked (Retry-After) (SEC-002)
  ↓ verify_password(password, hash) → fail: failed_login_count++ (10'da kilit) + 401
  ↓ user.email_verified == False → 403 hard block
  ↓ failed_login_count / locked_until sıfırla
  ↓ user.totp_enabled == True → {mfa_required, pre_mfa_token (15 dk), expires_in_seconds} (MFA adım 1)
  ↓ aksi halde:
  ↓ create_access_token(user.id, exp=480 dk dev / 30 dk prod)
  ↓ create_refresh_token(user.id, exp=7 gün)

POST /mfa/verify {pre_mfa_token, totp_code | recovery_code}   (MFA adım 2)
  ↓ decode pre_mfa_token (type=pre_mfa kontrol)
  ↓ pyotp.TOTP(secret).verify(valid_window=1)  veya  recovery code (tek kullanımlık)
  ↓ create_access_token + create_refresh_token

GET /portfolio/*
  ↓ Authorization: Bearer {access}
  ↓ decode_token() — type kontrolü YOK (access type claim taşımaz)
  ↓ jti varsa revoked_tokens blacklist kontrolü
  ↓ get_current_user() — DB lookup + user.deleted_at IS NULL kontrolü
  ↓ endpoint çalışır

POST /auth/refresh (access expired)
  ↓ decode_token() — type == "refresh" kontrolü
  ↓ jti revoked_tokens blacklist kontrolü → varsa 401 "Token iptal edilmiş"
  ↓ DB lookup (user hala var mı?)
  ↓ eski refresh jti'sini blacklist'e at (rotation, FAZ C4)
  ↓ yeni access + refresh
```

### 3.1.1 E-posta Doğrulama — Tehdit Modeli

| Tehdit | Mitigation |
|--------|------------|
| Token brute force (32 byte URL-safe = ~256 bit) | İstatistiksel olarak imkansız |
| Token expire edilmemesi | `verify_token_expires_at` (default 24 saat) |
| Eski token'ın yeniden kullanılması | Doğrulama sonrası `verify_token=NULL` |
| Account enumeration `/resend-verification` üzerinden | Her zaman 202 — yanıttan kullanıcının var olup olmadığı çıkarılamaz |
| Doğrulanmamış hesapla giriş | `/auth/login` 403 hard block |
| Mail gönderim fail → kullanıcı sıkışır | Kullanıcı `/resend-verification` ile yeni link talep edebilir; mail fail kayıt blokeleyici değil |

**TODO (gelecek):** `verify_token` plaintext yerine hash'lenmiş saklansın (DB sızıntısında token kullanılamasın) — düşük öncelik (token zaten kısa ömürlü).

### 3.2 JWT Yapısı
```python
# Header (HS256)
{ "alg": "HS256", "typ": "JWT" }

# Payload (access)  — DİKKAT: access token'da "type" ve "iat" claim YOK
{
  "sub":  "user-uuid",
  "exp":  unix_timestamp,
  "jti":  "uuid4.hex"   # selective revocation için (Faz 2 — eklendi)
}

# Payload (refresh)
{
  "sub":  "user-uuid",
  "exp":  unix_timestamp,
  "type": "refresh",
  "jti":  "uuid4.hex"
}

# Payload (pre_mfa)  — login adım 1 sonrası, sadece /mfa/verify'da geçerli (15 dk)
{
  "sub":  "user-uuid",
  "exp":  unix_timestamp,
  "type": "pre_mfa",
  "jti":  "uuid4.hex"   # kısa ömürlü; blacklist'e atılmaz, exp ile doğal expire
}
```

> **Not (kod gerçeği):** `create_access_token` yalnızca `sub` + `exp` + `jti` yazar — access token'da `type` claim **yoktur**. Token tipi ayrımı yalnızca refresh (`type=refresh`) ve pre_mfa (`type=pre_mfa`) için yapılır; access, type alanının yokluğuyla ayırt edilir. `iat` claim de set edilmiyor (`exp` yeterli). 

> Eski (jti'siz) tokenlar için geriye dönük uyumluluk: `get_current_user` ve `/auth/refresh` payload'da `jti` yoksa blacklist kontrolünü atlar. Bu, deploy anında elinde geçerli token olan kullanıcıların 401 almamasını sağlar. Tüm yeni tokenlar jti ile üretilir.

### 3.3 Token Süreleri
| Token | Süre (Dev, default) | Süre (Prod) |
|-------|---------------------|-------------|
| Access | 480 dk (8 saat) | 30 dk (`ACCESS_TOKEN_EXPIRE_MINUTES=30` env) |
| Refresh | 7 gün | 7 gün |
| pre_mfa | 15 dk | 15 dk (sabit, `PRE_MFA_TOKEN_TTL_SECONDS`) |

> `config.py` default'u **480 dk**; prod'da env ile 30 dk'ya çekilir. OWASP ASVS ≤15 dk önerir — security-notes #3 default'un 30 dk yapılmasını öneriyor (backlog). Refresh rotation aktif olduğu için kısa access penceresi acil değil.

### 3.4 Logout / Token İptali (Faz 2 — Tamamlandı)

```
POST /auth/logout {refresh_token?}   (Authorization: Bearer <access>)
  ↓ get_current_user(access) — token zaten doğrulandı
  ↓ INSERT revoked_tokens (jti, user_id, token_type='access', expires_at)
  ↓ Body'de refresh varsa + sub eşleşiyorsa: refresh jti'sini de blacklist'e al
  ↓ PK çakışması → rollback (idempotent — sessiz)
  ↓ Bozuk/geçersiz refresh → sessizce yutulur (bilgi sızdırma yok)
  ↓ 200 OK
```

**Bileşenler:**
- `models/revoked_token.py` — `RevokedToken(jti TEXT PK, user_id UUID, token_type TEXT, expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ)`. Migration `2a3b4c5d6e7f`. `expires_at` üzerinde index — Faz 3 cleanup cron için.
- `core/security.py` — `create_access_token` ve `create_refresh_token` `jti=uuid.uuid4().hex` ekler.
- `core/deps.py::get_current_user` — decode sonrası `RevokedToken.jti` sorgular; bulduysa 401. `jti` payload'da yoksa kontrol atlanır (geriye dönük uyumluluk).
- `api/v1/auth.py::POST /auth/refresh` — refresh token'ın `jti`'si blacklist'teyse 401 "Token iptal edilmiş".

**Test kapsamı:** `tests/integration/test_logout.py` — 8 test (200 OK, access blacklist sonrası 401, refresh blacklist sonrası 401, sadece access logout → refresh hala çalışır, auth gerektirir, idempotent, bozuk refresh yutulur, kullanıcı izolasyonu).

### 3.5 Bilinen Açıklar (Güncel)
1. ~~**JWT blacklist YOK**~~ ✅ Çözüldü (Faz 2 — `revoked_tokens` + `/auth/logout`)
2. ~~**`jti` (JWT ID) claim YOK**~~ ✅ Çözüldü (Faz 2 — tüm yeni tokenlar `jti` taşır)
3. ~~**Refresh token rotation YOK**~~ ✅ Çözüldü (FAZ C4 — `/auth/refresh` her çağrıda eski refresh `jti`'sini blacklist'e atar; sızan token ikinci kez kullanılamaz)
4. **Tek device "tüm cihazlardan çık" yok** — kullanıcının tüm aktif tokenlarını toplu iptal etme akışı yok (Faz 3 — `revoked_tokens`'a `user_id+token_type` toplu insert ile çözülebilir)
5. **Frontend refresh saklamıyor** — `localStorage` sadece access tutuyor; logout'ta refresh blacklist'e alınmıyor. Refresh akışı eklendiğinde düzeltilmeli (frontend teknik borç)
6. ~~**`revoked_tokens` cleanup yok**~~ ✅ Çözüldü (FAZ C5 — APScheduler her gün 03:00 Europe/Istanbul `expires_at < now` kayıtları siler)

---

## 4. Yetkilendirme (Authorization)

### 4.1 Mevcut Pattern: User-Owned Resources
Her endpoint'te kayıt erişimi `user_id == current_user.id` filtresiyle korunur. **IDOR ataklarına karşı tek savunma hattı bu.**

```python
# ✅ DOĞRU
result = await db.execute(
    select(WalletAddress).where(
        WalletAddress.id == wallet_id,
        WalletAddress.user_id == current_user.id   # ← kritik
    )
)

# ❌ YANLIŞ — IDOR açığı
result = await db.execute(select(WalletAddress).where(WalletAddress.id == wallet_id))
```

### 4.2 Rol Tabanlı Erişim (Faz 4)
Şu an tek rol var (kullanıcı). Faz 4'te admin paneli için:
```python
class UserRole(str, Enum):
    USER = "user"
    SUPPORT = "support"   # Sadece read-only
    ADMIN = "admin"       # Tam erişim

# Dependency
def require_role(*allowed: UserRole):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in allowed:
            raise HTTPException(403, "Yetersiz yetki")
        return user
    return checker

@router.get("/admin/users")
async def list_users(_: User = Depends(require_role(UserRole.ADMIN))):
    ...
```

---

## 5. API Key Şifreleme (Fernet)

### 5.1 Çalışma Şekli
```python
# config.py
fernet_key: str  # .env'den, openssl-üretimli 32 byte URL-safe base64

# core/security.py — MultiFernet (SEC-012): primary encrypt + decrypt, secondary decrypt-only
from cryptography.fernet import Fernet, MultiFernet

def _build_fernet() -> MultiFernet:
    primary = Fernet(settings.fernet_key.encode())
    secondaries = [Fernet(k.encode()) for k in settings.fernet_keys_secondary if k]
    return MultiFernet([primary, *secondaries])

_fernet = _build_fernet()

def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()   # her zaman primary key ile

def decrypt_secret(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()  # primary + secondary listesini dolaşır
```

### 5.2 Kullanım
- `POST /integrations` body'si plaintext alır → `encrypt_secret()` ile şifreler → DB
- Pozisyon çekimi sırasında `decrypt_secret()` ile açar → exchange'e gönderir
- API yanıtlarında **asla** decrypt edilmiş key dönülmez

### 5.3 Kritik: Master Key Yönetimi + Rotation (SEC-012)
- `FERNET_KEY` tek başına değişirse, **eski ciphertext'ler okunamaz hale gelir** — bu yüzden MultiFernet rotation kullanılır
- Production'da **SealedSecrets** ile GitOps uyumlu secret yönetimi aktif (bkz. §5.4)
- **Zero-downtime rotation (MultiFernet, kod içi aktif):**
  1. Yeni anahtar üret: `Fernet.generate_key().decode()`
  2. `FERNET_KEYS_SECONDARY=["<eski-primary>"]` env'e ekle, restart (decrypt-only)
  3. `FERNET_KEY=<yeni>` güncelle, restart → yeni encrypt yeni key ile, eski ciphertext secondary ile hâlâ decrypt edilir
  4. Re-encrypt background job tüm row'ları yeni primary'e taşıyana kadar bekle
  5. Tamamlanınca secondary'leri kaldır
- `FERNET_KEYS_SECONDARY` boş (default) → eski tek-key davranışı (backward compat). Rotation runbook'u devops alanında dokümante edilir.

### 5.4 K8s Secrets Yerleşimi (Mevcut — SealedSecrets, GitOps-safe)
- Tüm hassas env (`DATABASE_URL`, `SECRET_KEY`, `FERNET_KEY`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `POSTGRES_PASSWORD`) `kfinans-secrets` adlı Kubernetes Secret'ında
- **SealedSecrets (bitnami):** `k8s/sealed-secrets.yaml` içindeki `encryptedData` **asimetrik şifreli** ciphertext'tir — yalnızca cluster'daki sealed-secrets controller'ın private key'i açabilir. Bu nedenle dosya repo'ya **commit edilmek için** vardır; plaintext secret değil. gitleaks bu yolu allowlist'e alır (§9.3)
- **Rotasyon prosedürü (bu oturumda uygulandı — RESEND_API_KEY):**
  1. Yeni geçerli key alınır (sağlayıcıdan)
  2. Canlı Secret'a patch: `kubectl patch secret kfinans-secrets -n kfinans` (anlık etki)
  3. GitOps tutarlılığı için `kubeseal` ile yeniden mühürlenip `k8s/sealed-secrets.yaml`'a yazılır → commit
  4. Eski key revoke edilir; yeni key `.credentials.local.md` (gitignored) yedeğine kaydedilir
- `k8s/secrets.example.yaml` şablon olarak versiyon kontrolünde; ham `k8s/secrets.yaml` `.gitignore` korumalı
- **Faz 4 hedefi (opsiyonel):** External Secrets Operator (HashiCorp Vault) — SealedSecrets yeterli olduğu sürece şart değil

---

## 6. Rate Limiting

### 6.1 Backend (slowapi — Redis veya MemoryStorage)
`core/limiter.py::_build_limiter`: `settings.redis_url` set ise Redis backend (tüm replica'lar tek key üzerinde sayar), yoksa MemoryStorage (her pod ayrı sayar → `replicas=1` zorunlu) — SEC-003.

| Endpoint | Limit | Gerekçe |
|----------|-------|---------|
| `POST /auth/login` | 10/dk | Brute force koruması (+ SEC-002 account lockout) |
| `POST /auth/register` | 5/dk | Spam kayıt önleme |
| `POST /auth/refresh` | 30/dk | Normal kullanım toleransı |
| `GET /auth/verify-email` | 20/dk | Token brute force toleransı |
| `POST /auth/resend-verification` | 3/dk | Mail spam önleme |
| `POST /auth/forgot-password` | 3/dk | Mail spam + enumeration |
| `POST /auth/reset-password` | 5/dk | Token brute force |
| `POST /mfa/setup` · `POST /mfa/disable` | 3/dk | TOTP brute force koruması |
| `POST /mfa/enable` · `POST /mfa/verify` | 5/dk | TOTP brute force koruması |

> Diğer pahalı/spam'a açık endpoint'lerin limitleri (advice generate 5/saat, snapshot 6/saat, stocks/tefas preview 30/dk, data export 5/saat, email change 3/dk, anthropic consent 10/saat) `docs/03-api-referansi.md §1.4`'te tablolanır.

### 6.2 Production'a Geçişte
- MemoryStorage → **Redis** (multi-replica için zorunlu; env zinciri hazır)
- IP bazlı + user bazlı kombinasyon (giriş yapmış user için daha cömert limit) — gelecek iyileştirme

---

## 7. CORS

### 7.1 Mevcut Konfigürasyon
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # env'den
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 7.2 Production Ayarı
```bash
CORS_ORIGINS=["https://kfinans.app","https://www.kfinans.app"]
```
**Asla `["*"]` yapma** — `allow_credentials=True` ile birlikte tarayıcı reddedecek, ayrıca CSRF açığı.

---

## 8. Eksik Korumalar (Production'a Kadar Yapılacak)

### 8.1 CSRF Token (Yapılacak)
State-changing endpoint'lerde (POST/PUT/DELETE) cookie-based auth kullanılırsa CSRF zorunlu. Bearer token kullandığımız için **şu an düşük risk**, ama frontend httpOnly cookie'ye geçerse zorunlu olur.

### 8.2 Security Response Headers ✅ TAMAMLANDI (FAZ C2)
`backend/app/core/middleware.py::SecurityHeadersMiddleware` her response'a şu header'ları ekler:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'
Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-site
Server: kfinans
```

Frontend (`frontend/next.config.ts` async `headers()`) HTML response'larında ek olarak CSP'ye `script-src 'unsafe-inline' 'unsafe-eval'` (Next.js inline runtime için, nonce stratejisi gelecek sürümde) ve `connect-src https://kfinans.app` ekler.

**.app TLD HSTS preload listesinde** — tarayıcı `kfinans.app`'e DNS sorgusu yapmadan zorla HTTPS kullanır. Defence-in-depth için manuel HSTS header da ayarlandı.

### 8.3 HTTPS Zorunluluğu (FAZ D1'de yapılacak)
- nginx-ingress + cert-manager (Let's Encrypt) — Oracle Cloud K3s'e provision edilecek
- HTTP → HTTPS redirect (`force-ssl-redirect: true` ingress annotation, mevcut)
- HSTS preload: `.app` TLD zaten preload listesinde (otomatik)

### 8.4 Request Size / Upload Validation ✅ TAMAMLANDI (SEC-009)
- nginx-ingress: `proxy-body-size` annotation (`k8s/ingress.yaml`)
- `core/upload_validation.py::validate_excel_upload` — 10 Excel import endpoint'inde 3 katmanlı: (1) uzantı `.xlsx|.xls`, (2) boyut `settings.max_upload_size_mb` (default 5MB → 413), (3) magic byte (xlsx ZIP `PK\x03\x04`, xls OLE2 `\xD0\xCF\x11\xE0...`; yanlış → 422 polyglot koruması)

### 8.5 SQL Injection
- ✅ Tüm sorgular SQLAlchemy ORM/parametrize — güvende
- ✅ Raw SQL yok (audit_logs migration `bind.execute(text(...))` parametrize)
- ⚠️ String concatenation ile sorgu yazılırsa risk — code review'de yakalanmalı

### 8.6 XSS Koruması
- React/Next.js otomatik HTML escape ✅
- `dangerouslySetInnerHTML` kullanımı YOK (review edilmeli)
- AI tavsiye Markdown render: `react-markdown` + `rehype-sanitize` zorunlu (Faz 3)
- **CSP `default-src 'none'`** (FAZ C2) backend için XSS surface'ini sıfıra indirir

### 8.7 Host Header Injection ✅ TAMAMLANDI (FAZ C3)
`TrustedHostMiddleware` ile `settings.allowed_hosts` env'den (prod'da `["kfinans.app","www.kfinans.app","api.kfinans.app"]`); yanlış Host header → 400.

---

## 9. Bağımlılık Güvenliği

### 9.1 Mevcut
- `pip install -e .` — `>=` versiyon kullanılıyor (lock file yok)
- `npm ci` — `package-lock.json` mevcut

### 9.2 Yapılacak
- [x] `pip-audit` CI'da çalışıyor (FAZ B4 — `.github/workflows/security.yml`, strict mode + osv vulnerability service)
- [x] `npm audit` CI'da çalışıyor (FAZ B4 — `--audit-level=high`, fail on threshold)
- [x] Trivy ile container image vulnerability scan (`.gitlab-ci.yml::trivy-image-scan`, `scan` stage — build sonrası/deploy öncesi gate; HIGH/CRITICAL `--ignore-unfixed` → fail). GitHub `release.yml::trivy-scan` dormant referans.
- [x] Trivy filesystem scan (FAZ B4 — `.github/workflows/security.yml::trivy-fs`; deps + IaC)
- [x] Dependabot aktif (FAZ A4 — `.github/dependabot.yml`; pip + npm + actions + docker, haftalık)
- [x] CodeQL Python + TypeScript SAST (FAZ B4 — security-and-quality query suite)
- [x] Gitleaks secret tarama (FAZ B4 — `.gitleaks.toml` allowlist'li; her PR/push)
- [x] SonarQube quality gate (blocking) — code smell + bug + vulnerability + security hotspot (§9.4)
- [ ] `pip-tools` ile `requirements.lock` üretimi (Faz 3)

> **Not (CI platform gerçeği):** `develop`/`main` artık **GitLab primary** (self-hosted), GitHub mirror. GitHub Actions hesap flag (#4360519, 2026-06-01 itibarıyla hâlâ aktif) nedeniyle çalışmadığından gate'ler GitLab CI üzerinde yürütülür. Workflow dosya isimleri tarihsel referans amaçlı korunur; aynı kontroller (`.gitlab-ci.yml`) GitLab pipeline'ında koşar.

### 9.3 Gitleaks Allowlist Mantığı

`.gitleaks.toml` allowlist'i yalnızca **kanıtlanmış zararsız** değerleri kapsar — gerçek secret asla allowlist'e alınmaz:

| Allowlist girdisi | Neden zararsız |
|-------------------|----------------|
| `k8s/sealed-secrets.yaml` (path) | `encryptedData` asimetrik şifreli; commit edilmek için var, plaintext değil |
| CI-only test `SECRET_KEY` / `FERNET_KEY` (regex) | `.gitlab-ci.yml` throwaway değerleri; prod secret CI Variables'tan gelir, bu key'ler hiçbir prod sisteme erişim sağlamaz |
| `wrong-pass-123` (regex) | smoke testi bogus login şifresi (kasıtlı 401 üretir) |
| `Sifre123!` / `guclu-sifre-123` (regex) | backend/frontend test fixture şifreleri (geçici test DB user'ı) |
| `curl -u "$TOKEN:"` (regex) | dokümandaki env-var placeholder — gerçek token değil |
| `backend/tests/`, `playwright/`, `.env*.example` (path) | sahte örnek/fixture değerleri |

**Tam-geçmiş taraması (274 commit, bu oturum):** 14 bulgunun **tamamı** zararsız doğrulandı (commit diff + working tree + full history). **Gerçek secret sızıntısı YOK.** Allowlist bu denetim sonrası SealedSecrets + CI test key + curl placeholder girdileriyle genişletildi.

### 9.4 SonarQube Quality Gate (Blocking)

- **Konum:** `.gitlab-ci.yml` SonarQube tarama job'u; quality gate fail → pipeline fail (blocking).
- **Yeni kod (new code) odaklı:** gate yeni eklenen/değişen kodda 0 yeni bug + 0 yeni vulnerability + 0 yeni security hotspot (review edilmemiş) bekler.
- **Security hotspot review akışı:** Her hotspot manuel incelenir → `SAFE` / `FIXED` / `ACKNOWLEDGED` işaretlenir. `new_security_hotspots_reviewed=%100` zorunlu.
  - Örnek (bu oturum): `password_policy.py` HIBP entegrasyonunun SHA-1 kullanımı hotspot olarak işaretlendi → **SAFE**. Gerekçe: HIBP **k-anonymity** modeli — şifrenin SHA-1 hash'inin yalnızca ilk 5 karakteri (prefix) ağa gönderilir; plaintext veya tam hash hiçbir zaman ağa çıkmaz.

#### NOSONAR — Gerekçeli İstisnalar (bu oturum, 26 violation kapanışı)

26 violation: **21 gerçek fix + 5 gerekçeli `NOSONAR`/`noqa`**. NOSONAR yalnızca kasıtlı/false-positive durumlarda, kod yorumuyla gerekçelendirilerek kullanılır — yeni açık eklenmedi:

| Dosya | Kural | Gerekçe |
|-------|-------|---------|
| `core/log_filter.py` | S3516 (her zaman aynı değer döner) | `logging.Filter.filter()` sözleşmesi gereği her zaman `True` döner (kayıt geçirilir; filtre maskeleme yapar, drop etmez) |
| `core/password_policy.py` | S7483 (timeout) | `httpx` native timeout idiomatik kullanım — SonarQube generic flag'liyor |
| `database.py` | S5527 ×2 (hostname/cert doğrulama) | `prefer` modu self-signed cluster cert için **bilinçli** olarak `check_hostname=False` + `CERT_NONE`; **prod `require` modu hostname + cert chain doğrulamasını AÇIK tutar** (bkz. §14) |

> **Kritik ayrım:** `database.py` NOSONAR yalnızca cluster-içi `prefer` dalını kapsar. Production trafiği `require` modunda akar ve **TLS hostname + sertifika zinciri doğrulaması tam açıktır** — gevşetilen kontrol yalnızca public CA'sı olmayan cluster-içi defence-in-depth fallback dalındadır.

---

## 10. Loglama ve Audit Trail

### 10.1 Mevcut Application Log
- Login success/fail loglanıyor
- API entegrasyon hataları loglanıyor
- Scheduler events loglanıyor

### 10.2 Audit Trail ✅ TAMAMLANDI (FAZ C6)

`audit_logs` tablosu (migration `c4d5e6f7a8b9`):
```sql
audit_logs
  id                 UUID PK
  user_id            UUID FK ON DELETE SET NULL    -- user silinince log korunur (forensic)
  action             VARCHAR(64) NOT NULL          -- "auth.login", "wallet.add", "integration.delete"
  resource           VARCHAR(128)                  -- "wallet:<uuid>", "integration:binance"
  ip_address         VARCHAR(45)                   -- X-Forwarded-For > client.host (IPv6 max 45)
  user_agent         VARCHAR(512)                  -- truncated
  extra              JSONB                         -- ek context (chain, email, vs.)
  created_at         TIMESTAMPTZ DEFAULT now()
  -- Index'ler:
  --   ix_audit_logs_user_created   (user_id, created_at DESC)
  --   ix_audit_logs_action_created (action, created_at DESC)
```

**Hook'lanmış 8+ eylem:**

| Action | Hook konumu | Kayıt detayı |
|--------|-------------|--------------|
| `auth.login` | `auth.py::login` | success → user_id |
| `auth.login_failed` | `auth.py::login` | user_id (varsa) + extra.email |
| `auth.logout` | `auth.py::logout` | user_id |
| `auth.register` | `auth.py::register` | user_id + extra.email + extra.risk_profile |
| `auth.password_change` | `user.py::change_password` | user_id |
| `wallet.add` | `wallets.py::add_wallet` | resource=wallet:{id} + extra.chain + extra.label |
| `wallet.delete` | `wallets.py::remove_wallet` | resource=wallet:{id} + extra.chain |
| `integration.add` | `integrations.py::add_integration` | resource=integration:{provider} + extra.updated |
| `integration.delete` | `integrations.py::remove_integration` | resource=integration:{provider} |
| `snapshot.delete` | `portfolio.py::delete_snapshot` | resource=snapshot:{date} |
| `account.soft_delete` | `user.py::delete_me` | resource=user:{id} |
| `auth.password_reset_request` / `auth.password_reset_complete` | `auth.py::forgot_password` / `reset_password` | SEC-001 reset akışı (success flag + reason) |
| `auth.mfa.setup` / `.enabled` / `.disabled` / `.verify_success` / `.verify_failed` / `.recovery_used` / `auth.login_mfa_required` | `mfa.py` + `auth.py::login` | MFA TOTP akışı (audit #5) |
| `user.email_change_request` / `.email_change_complete` | `user.py` | COMP-029 e-posta değiştirme |
| `user.consent_revoke` | `user.py` | COMP-006 açık rıza geri çekme |
| `kvkk.anthropic_consent_grant` / `.revoke` | advice akışı | AI-005 KVKK m.9 özel rıza |
| `user.data_export` | KVKK veri taşınabilirliği | COMP-003 |
| `wallet.export` / `integration.export` | xpub / API key plaintext dışa aktarımı (şifre doğrulamalı, forensic) | COMP-024 |
| `advice.generate` | `advisor` akışı | AI-004 kredi tüketimli |

> Tam liste `services/audit.py::AuditAction` enum'unda.

**Endpoint:** `GET /api/v1/audit-logs?action_prefix=&limit=&offset=` — kullanıcı sadece kendi log'larını görür (IDOR korumalı); `PaginatedResponse[T]` (PERF-001).

**Servis:** `app/services/audit.py::log_audit()` — best-effort (try/except yutar, ana endpoint bozulmaz). **IP kaynağı (SEC-004):** yalnızca `request.client.host` okunur — ham `X-Forwarded-For` artık güvenilmiyor (spoofing riski). Gerçek istemci IP'si için uvicorn `--proxy-headers --forwarded-allow-ips=...` ile trusted-proxy zincirinden normalize edilen değer kullanılır.

**Test:** `tests/integration/test_audit_logs.py` — 9 test: 5 hook regression + 4 endpoint (IDOR + filter + auth).

**Kalan loglanacak eylemler (gelecek):**
- `auth.email_verified` — enum'da tanımlı; explicit hook eklenebilir (zaten log seviyesinde info kaydı var)

> **Not (backlog):** SEC-004 sonrası `_client_ip` sadece `request.client.host` okur; ingress'te uvicorn `--forwarded-allow-ips` set edilmemişse audit log'ta gerçek kullanıcı IP'si yerine ingress IP'si görünür (security-notes #8, devops backlog). Audit yazma silent fail'i Sentry'ye forward edilmiyor (security-notes #12, backlog).

---

## 11. OWASP Top 10 — KFinans Durumu

| OWASP 2021 | Durum | Not |
|------------|-------|-----|
| A01: Broken Access Control | ✅ | User izolasyonu (5 IDOR test); audit log endpoint de IDOR korumalı |
| A02: Cryptographic Failures | ✅ | bcrypt (şifre) + Fernet (API key + xpub FAZ C1, MultiFernet rotation SEC-012) + DB TLS require (§14) + HTTPS (Oracle ingress + cert-manager) + .app TLD HSTS preload |
| A03: Injection | ✅ | ORM only; raw SQL yok; migration'da `text()` parametrize |
| A04: Insecure Design | ✅ | Logout + JWT blacklist + refresh rotation (FAZ C4) |
| A05: Security Misconfiguration | ✅ | SecurityHeaders + TrustedHost (FAZ C2/C3); env'den allowed_hosts override |
| A06: Vulnerable Components | ✅ | pip-audit + npm-audit + Trivy fs + Trivy image + Dependabot + CodeQL (FAZ A4 + B3 + B4) |
| A07: Identification & Auth Failures | ✅ | Logout + blacklist + refresh rotation (FAZ C4) + email verify hard block + MFA TOTP (audit #5) + account lockout (SEC-002) + şifre politikası zxcvbn/HIBP |
| A08: Software & Data Integrity | ⚠️ | Image signing (cosign) yok — Faz 3 |
| A09: Security Logging & Monitoring | ✅ | audit_logs tablosu + 8 hook + endpoint (FAZ C6) |
| A10: Server-Side Request Forgery | ✅ | Dış URL kullanıcı girişiyle oluşmuyor; Ethplorer/CoinGecko sabit URL'ler |

---

## 12. Güvenlik Kontrol Listesi (Yeni Özellik İçin)

Her yeni endpoint için doğrula:
- [ ] Auth gerektirir mi? `Depends(get_current_user)` var mı?
- [ ] Kayıt erişiminde `user_id == current_user.id` filtresi var mı?
- [ ] Pydantic ile input validation tam mı?
- [ ] Hata mesajları stack trace içermiyor mu?
- [ ] File upload varsa: tip + boyut kontrolü?
- [ ] Write endpoint mı? Rate limit eklendi mi?
- [ ] Sensitive output filtrelendi mi (encrypted_key dönmez)?
- [ ] Audit log kaydı eklendi mi?

---

## 13. Olay Müdahale (Incident Response)

### 13.1 Veri İhlali Senaryosu
KVKK m.12 + Veri İhlali Yönetmeliği — **72 saat içinde** Kişisel Verileri Koruma Kurumu'na bildirim zorunlu.

### 13.2 Müdahale Adımları
1. **Tespit:** Sentry/log alarmı veya kullanıcı şikayeti
2. **İzole et:** Etkilenen pod/servisi durdur
3. **Kapsam belirle:** Hangi user'lar, hangi veriler etkilendi?
4. **Düzelt:** Açığı kapat, deploy et
5. **Bildir:** KVKK kuruluna 72 saat içinde + etkilenen kullanıcılara
6. **Post-mortem:** Tekrar olmaması için süreç güncellemesi

> Detaylı KVKK gereksinimleri: [uyumluluk-kvkk.md](./uyumluluk-kvkk.md)

---

## 14. DB TLS (Transit Şifreleme)

`backend/app/database.py` asyncpg `connect_args.ssl` değerini `settings.database_ssl_mode`'a göre kurar:

| Mod | `ssl` ayarı | Hostname + Cert doğrulama | Kullanım |
|-----|-------------|---------------------------|----------|
| `disable` | `False` | – | Eski/dev davranış (geriye uyumlu) |
| `prefer` | self-signed SSLContext | **KAPALI** (`check_hostname=False`, `CERT_NONE`) | Cluster-içi defence-in-depth; public CA'sı olmayan self-signed Postgres cert kabul edilir |
| `require` | CA bundle'lı SSLContext | **AÇIK** (`check_hostname=True`, `CERT_REQUIRED`) | **Production** — cert-manager `postgres-tls` Secret backend pod'a `/etc/postgres-ca/ca.crt` olarak mount edilir |

- **Production `require` modunda** hem hostname hem sertifika zinciri doğrulaması açıktır; MITM koruması tamdır. CA bundle yoksa asyncpg default `CERT_REQUIRED` context'e (sistem PKI) düşer.
- `prefer` modundaki gevşetme **yalnızca** node compromise senaryosunda in-flight veri sızıntısını engellemek için (encrypt-in-transit) cluster-içi fallback'tir. SonarQube S5527/S4830 bu dalda `NOSONAR` ile gerekçelendirilmiştir (§9.4).
- **Geçmiş not:** 3 başarısız "DB TLS handshake fail" denemesi aslında DNS resolution hatasıymış; NetworkPolicy DNS egress fix (a8496ca) ile kapandı, ardından `require` prod'da aktive edildi.

---

## 15. HTTP Yanıt Header'larında Non-ASCII (öğrenilen ders)

**Bug:** `GET /portfolio/wallets/export.xlsx` `Content-Disposition: attachment; filename=...` header'ında Türkçe `ı` (U+0131) karakteri vardı. ASGI/uvicorn HTTP header'larını **latin-1** ile encode eder; non-ASCII karakter `UnicodeEncodeError` → 500 üretti (production'da yakalandı).

**Fix:** Dosya adı ASCII'ye çekildi → `blockchain-cuzdanlari.xlsx` (`backend/app/api/v1/wallets.py:189`).

**Kural:** HTTP yanıt header değerleri **yalnızca ASCII** olmalıdır. Türkçe karakter içeren dosya adı gerekiyorsa RFC 5987 `filename*=UTF-8''...` (percent-encoded) sözdizimi kullanılmalı; ham UTF-8 header'a yazılmamalıdır. Yeni download endpoint'lerinde gözden geçir.
