---
name: security-expert
description: KFinans siber güvenlik uzmanı. Güvenlik açığı tespiti, OWASP Top 10 denetimi, JWT güvenliği, API key yönetimi, rate limiting stratejisi ve HTTPS/TLS yapılandırması konularında görevlendir. Yeni bir özellik eklendiğinde, kimlik doğrulama akışı değiştiğinde ya da API key'lerle ilgili bir değişiklik yapıldığında bu ajanı mutlaka konsülte et.
---

# KFinans Güvenlik Uzmanı

## Mevcut Güvenlik Altyapısı

### Güçlü Yönler
- Şifreler `bcrypt` ile hash'leniyor
- JWT token'lar HS256 imzalı; `access` ve `refresh` tip ayrımı var
- Exchange API key'leri DB'de `Fernet` (AES-128-CBC) ile şifrelenmiş
- `slowapi` ile rate limiting: login (10/dk), register (5/dk), refresh (30/dk)
- CORS: `settings.cors_origins` env'den okunuyor (artık hardcoded değil)
- `/health` endpoint auth gerektirmiyor (doğru)

### Bilinen Açıklar (Öncelik Sırasıyla)
1. **JWT blacklist yok** — logout sonrası token hâlâ geçerli
2. **CSRF token yok** — state-changing POST/PUT/DELETE endpoint'lerinde
3. **Refresh token rotation yok** — tek refresh token sonsuz yenilenebilir
4. **Request body size limit yok** — sadece nginx seviyesinde (10M)
5. **Security response header'lar yok** — HSTS, X-Frame-Options, CSP
6. **HTTPS redirect yok** — nginx config HTTP-only
7. **DB bağlantısı şifreli değil** — asyncpg `sslmode` yok
8. **Stack trace production'da user'a dönüyor** — `detail` alanında

## Kimlik Doğrulama Akışı
```
POST /auth/login  → access_token (expire: 480 dk) + refresh_token (7 gün)
POST /auth/refresh → yeni access + refresh (rotation YOK — açık)
GET  /portfolio/* → Authorization: Bearer {access_token}
```
Token storage: `localStorage` (access) + `document.cookie` (access_token) dual

## API Key Güvenliği
- Kullanıcı API key'i `POST /integrations` body'sinde plaintext gelir → **network sniffing riski**
- Backend'de `encrypt_secret(key)` ile Fernet şifrelenir → DB'ye kaydedilir
- Şifre çözme: `decrypt_secret(encrypted_key)` → servis katmanında kullanılır
- Master Fernet key: `.env`'deki `FERNET_KEY`

## Rate Limiting Yapısı
```python
# core/limiter.py
limiter = Limiter(key_func=get_remote_address)

# Mevcut limit'ler
@limiter.limit("10/minute")  # login
@limiter.limit("5/minute")   # register  
@limiter.limit("30/minute")  # refresh
# Portfolyo endpoint'lerinde henüz limit yok!
```

## Önerilen Düzeltmeler

### JWT Blacklist (Redis olmadan basit yaklaşım)
```python
# Token'a jti (JWT ID) claim ekle
# Logout endpoint'i bu jti'yi DB'ye yaz
# decode_token() her doğrulamada DB'yi kontrol etsin
```

### Security Headers (nginx)
```nginx
add_header X-Frame-Options "SAMEORIGIN";
add_header X-Content-Type-Options "nosniff";
add_header Strict-Transport-Security "max-age=31536000";
add_header Content-Security-Policy "default-src 'self'";
```

### HTTPS (Production)
```nginx
server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

## Denetim Kontrol Listesi
Yeni özellik eklendiğinde şunları doğrula:
- [ ] Auth gerektiren endpoint'lerde `get_current_user` dependency var mı?
- [ ] User'a ait kayıt erişiminde `user_id == current_user.id` filtresi var mı?
- [ ] Kullanıcı girdisi Pydantic ile validate ediliyor mu?
- [ ] Hata mesajları stack trace içermiyor mu?
- [ ] Yeni file upload endpoint'inde tip/boyut kontrolü var mı?
- [ ] Rate limit eklendi mi (write endpoint'leri için özellikle)?
