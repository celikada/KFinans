# Güvenlik Mimarisi

**Sahip ajan:** `security-expert`
**İlgili:** [uyumluluk-kvkk.md](./uyumluluk-kvkk.md), [api-referansi.md](./api-referansi.md)

---

## 1. Mevcut Fonksiyonel Gereksinimler (Aktif Korumalar)

| Koruma | Uygulama | Durum |
|--------|----------|-------|
| Şifre hash | bcrypt | ✅ Aktif |
| JWT imza | HS256 | ✅ Aktif |
| Token tipi ayrımı | `access` / `refresh` | ✅ Aktif |
| Exchange API key encryption | Fernet (AES-128-CBC) | ✅ Aktif |
| CORS allowlist | `settings.cors_origins` (env'den) | ✅ Aktif |
| Rate limiting (auth endpoint'leri) | slowapi (in-memory) | ✅ Aktif |
| **E-posta doğrulama zorunluluğu** | `email_verified=False` ise login 403 hard block | ✅ Aktif |
| **Doğrulama token'ı (TTL'li)** | `secrets.token_urlsafe(32)`, `verify_token_expires_at` (24 saat) | ✅ Aktif |
| **Account enumeration koruması** | `POST /auth/resend-verification` her zaman 202 döner | ✅ Aktif |
| Health endpoint (auth gerektirmez) | `/health` | ✅ Aktif |
| Auth gerektiren endpoint'ler | `Depends(get_current_user)` | ✅ Aktif |
| User izolasyonu | `WHERE user_id == current_user.id` | ✅ Aktif |
| Pydantic input validation | Tüm request body'ler | ✅ Aktif |
| Servis katmanı logging | 9 servis dosyasında module-level logger | ✅ Aktif |
| Test kapsama (regresyon koruma) | IDOR (5 endpoint), security primitives (22 test), integrations leak (5 test), auth flow (21 test) | ✅ Aktif |
| Soft delete altyapısı | `users.deleted_at` kolonu hazır (cron Faz 3) | ✅ Şema hazır |
| `users.credit_balance` (CHECK >= 0) | DB seviyesinde negatif bakiye koruması | ✅ Aktif |

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
| Cüzdan adresleri | 🟡 Orta | – (public key) | User izolasyonu yeterli |
| Portföy snapshot | 🟡 Orta | – | User izolasyonu |
| AI tavsiye içeriği | 🟢 Düşük | – | User izolasyonu |
| Email | 🟡 Orta | – | KVKK kapsamında |

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
  ↓ verify_password(password, hash)
  ↓ user.email_verified == False → 403 hard block
  ↓ create_access_token(user.id, exp=480 dk)
  ↓ create_refresh_token(user.id, exp=7 gün)

GET /portfolio/*
  ↓ Authorization: Bearer {access}
  ↓ decode_token() — type kontrol (access)
  ↓ get_current_user() — DB lookup
  ↓ endpoint çalışır

POST /auth/refresh (access expired)
  ↓ decode_token() — type kontrol (refresh)
  ↓ DB lookup (user hala var mı?)
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

# Payload (access)
{
  "sub":  "user-uuid",
  "exp":  unix_timestamp,
  "iat":  unix_timestamp,
  "type": "access"
}

# Payload (refresh)
{
  "sub":  "user-uuid",
  "exp":  unix_timestamp,
  "iat":  unix_timestamp,
  "type": "refresh"
}
```

### 3.3 Token Süreleri
| Token | Süre (Dev) | Süre (Prod, Hedef) |
|-------|-----------|---------------------|
| Access | 480 dk (8 saat) | 15 dk |
| Refresh | 7 gün | 7 gün |

### 3.4 Bilinen Açıklar
1. **JWT blacklist YOK** — logout sonrası token hâlâ geçerli (refresh süresi dolana kadar)
2. **Refresh token rotation YOK** — aynı refresh token defalarca kullanılabilir
3. **Tek device session yönetimi YOK** — user tüm device'larında otomatik çıkış yapamıyor
4. **`jti` (JWT ID) claim YOK** — selective revocation imkansız

#### Düzeltme Planı (Faz 3)
```python
# 1. jti ekle
payload["jti"] = str(uuid.uuid4())

# 2. revoked_tokens tablosu
class RevokedToken(Base):
    jti: Mapped[str] = mapped_column(primary_key=True)
    revoked_at: Mapped[datetime]
    expires_at: Mapped[datetime]  # cleanup için

# 3. decode_token() içinde kontrol
if await db.execute(select(RevokedToken).where(RevokedToken.jti == jti)).scalar_one_or_none():
    raise HTTPException(401, "Token iptal edildi")

# 4. POST /auth/logout endpoint'i
async def logout(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    db.add(RevokedToken(jti=payload["jti"], expires_at=...))
```

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

# core/security.py
from cryptography.fernet import Fernet
_fernet = Fernet(settings.fernet_key.encode())

def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
```

### 5.2 Kullanım
- `POST /integrations` body'si plaintext alır → `encrypt_secret()` ile şifreler → DB
- Pozisyon çekimi sırasında `decrypt_secret()` ile açar → exchange'e gönderir
- API yanıtlarında **asla** decrypt edilmiş key dönülmez

### 5.3 Kritik: Master Key Yönetimi
- `FERNET_KEY` değişirse, **tüm mevcut encrypted_key'ler okunamaz hale gelir**
- Production'da **Kubernetes Secret + sealed-secrets** veya **External Secrets Operator** zorunlu
- Key rotasyonu: yeni key + dual-decrypt + re-encrypt migration (kritik operasyon, prosedür yazılmalı)

---

## 6. Rate Limiting

### 6.1 Mevcut Limitler (slowapi, in-memory)
| Endpoint | Limit | Gerekçe |
|----------|-------|---------|
| `POST /auth/login` | 10/dk | Brute force koruması |
| `POST /auth/register` | 5/dk | Spam kayıt önleme |
| `POST /auth/refresh` | 30/dk | Normal kullanım toleransı |

### 6.2 Eklenecek Limitler (Faz 3)
| Endpoint | Limit |
|----------|-------|
| `POST /advice/generate` | 5/dk (kredi varsa bile) |
| `POST /portfolio/tefas/preview` | 30/dk (TEFAS API'sini koru) |
| `POST /portfolio/stocks/preview` | 30/dk (Yahoo Finance) |
| `POST /credits/checkout` | 3/dk (ödeme spam) |
| `POST /credits/webhook` | 100/dk (idempotency yine kontrol et) |

### 6.3 Production'a Geçişte
- In-memory store → **Redis** (multi-replica için zorunlu)
- IP bazlı + user bazlı kombinasyon (giriş yapmış user için daha cömert limit)

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
CORS_ORIGINS=["https://app.kfinans.com","https://kfinans.com"]
```
**Asla `["*"]` yapma** — `allow_credentials=True` ile birlikte tarayıcı reddedecek, ayrıca CSRF açığı.

---

## 8. Eksik Korumalar (Production'a Kadar Yapılacak)

### 8.1 CSRF Token (Yapılacak)
State-changing endpoint'lerde (POST/PUT/DELETE) cookie-based auth kullanılırsa CSRF zorunlu. Bearer token kullandığımız için **şu an düşük risk**, ama frontend httpOnly cookie'ye geçerse zorunlu olur.

### 8.2 Security Response Headers (Yapılacak)
nginx-ingress veya middleware seviyesinde:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; script-src 'self'; ...
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

### 8.3 HTTPS Zorunluluğu (Yapılacak)
- nginx-ingress + cert-manager (Let's Encrypt)
- HTTP → HTTPS redirect (301)
- HSTS preload (Chrome HSTS list'e ekleme)

### 8.4 Request Size Limit (Yapılacak)
- nginx: `client_max_body_size 10m;`
- FastAPI: file upload endpoint'lerde Pydantic + content-length kontrol

### 8.5 SQL Injection
- ✅ Tüm sorgular SQLAlchemy ORM/parametrize — güvende
- ✅ Raw SQL yok
- ⚠️ String concatenation ile sorgu yazılırsa risk — code review'de yakalanmalı

### 8.6 XSS Koruması
- React/Next.js otomatik HTML escape ✅
- `dangerouslySetInnerHTML` kullanımı YOK (review edilmeli)
- AI tavsiye Markdown render: `react-markdown` + `rehype-sanitize` zorunlu (Faz 3)

---

## 9. Bağımlılık Güvenliği

### 9.1 Mevcut
- `pip install -e .` — `>=` versiyon kullanılıyor (lock file yok)
- `npm ci` — `package-lock.json` mevcut

### 9.2 Yapılacak
- [ ] `pip-audit` veya `safety` CI'da çalışsın
- [ ] `npm audit` CI'da çalışsın
- [ ] Trivy ile container image vulnerability scan
- [ ] Dependabot aktif et (mevcutta? — kontrol edilmeli)
- [ ] `pip-tools` ile `requirements.lock` üretimi

---

## 10. Loglama ve Audit Trail

### 10.1 Mevcut
- Login success/fail loglanıyor
- API entegrasyon hataları loglanıyor
- Scheduler events loglanıyor

### 10.2 Yapılacak (Faz 3)
Audit trail tablosu:
```sql
audit_logs
  id          UUID PK
  user_id     UUID FK NULL          -- anonim eylemler için NULL
  action      TEXT                  -- 'login', 'add_integration', 'delete_wallet'
  resource    TEXT                  -- 'wallet:{uuid}'
  ip_address  TEXT
  user_agent  TEXT
  metadata    JSONB                 -- ek context
  created_at  TIMESTAMPTZ
```

Loglanacak eylemler:
- Tüm auth eylemleri (login, logout, password change)
- API key ekleme/silme
- Cüzdan ekleme/silme
- Kredi satın alma
- AI tavsiye üretimi
- Veri export (KVKK için)

---

## 11. OWASP Top 10 — KFinans Durumu

| OWASP 2021 | Durum | Not |
|------------|-------|-----|
| A01: Broken Access Control | ✅ | User izolasyonu var; IDOR riski code review ile |
| A02: Cryptographic Failures | ⚠️ | bcrypt + Fernet ✅; HTTPS ❌ (prod'da olacak) |
| A03: Injection | ✅ | ORM only; raw SQL yok |
| A04: Insecure Design | ⚠️ | Logout/blacklist eksik (Faz 3) |
| A05: Security Misconfiguration | ⚠️ | Security headers eksik (prod'da eklenecek) |
| A06: Vulnerable Components | ❌ | Audit/scan yok (yapılacak) |
| A07: Identification & Auth Failures | ⚠️ | Refresh rotation yok (Faz 3) |
| A08: Software & Data Integrity | ⚠️ | Image signing yok |
| A09: Security Logging & Monitoring | ❌ | Audit log yok (Faz 3) |
| A10: Server-Side Request Forgery | ✅ | Dış URL kullanıcı girişiyle oluşmuyor |

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
