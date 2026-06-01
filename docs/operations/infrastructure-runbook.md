# KFinans Altyapı Runbook

> **Amaç:** Production altyapısının (DNS, email, K3s, sertifika) kurulum kayıtları, periyodik bakım işleri ve acil durum komutları. Onboarding ve operasyonel referans olarak korunur.

**Son güncelleme:** 2026-05-14

---

## 1. DNS — Namecheap (`kfinans.app`)

### 1.1 Aktif DNS Kayıtları

Namecheap "Advanced DNS" panelinde tanımlı kayıtlar (durum: 2026-05-14):

| # | Type | Host | Value | TTL | Eklendi | Amaç |
|---|------|------|-------|-----|---------|------|
| 1 | A | `@` | `141.144.243.54` | 5 min | 2026-05-14 | Apex → Oracle Cloud VM |
| 2 | CNAME | `www` | `kfinans.app.` | 5 min | 2026-05-14 | `www` subdomain → apex (IP değişirse otomatik takip) |
| 3 | TXT | `resend._domainkey` | `p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCrKScSobLvf9cW9/8O7Qj6AKanEvf0SZ9TwV4a/P7UjZ/3L6Vm47mZZ94IhuGLEDBH84dRktAvMqY6mdJpeFqO6PHL2/q8WX1uKDfk+g4AiRu/I3u5ggK/FvViUx25mHFVzcvHGAEYwz1cLzHut+W8C7N9FhHovxXjq+3kjbxbTwIDAQAB` | Auto | 2026-05-14 | Resend DKIM (domain ownership doğrulaması) |
| 4 | MX | `send` | `feedback-smtp.ap-northeast-1.amazonses.com` (priority `10`) | Auto | 2026-05-14 | Resend bounce/feedback return-path (Tokyo region) |
| 5 | TXT | `send` | `v=spf1 include:amazonses.com ~all` | Auto | 2026-05-14 | Resend SPF (gönderim yetkisi) |
| 6 | TXT | `_dmarc` | `v=DMARC1; p=none;` | Auto | 2026-05-14 | DMARC monitoring (spoofing koruması ileride `p=quarantine`) |

### 1.2 Propagasyon Doğrulama

```powershell
# Local DNS cache bypass — Google public resolver
nslookup kfinans.app 8.8.8.8
nslookup www.kfinans.app 8.8.8.8
nslookup -type=TXT resend._domainkey.kfinans.app 8.8.8.8
nslookup -type=MX send.kfinans.app 8.8.8.8
nslookup -type=TXT send.kfinans.app 8.8.8.8
nslookup -type=TXT _dmarc.kfinans.app 8.8.8.8
```

Beklenen çıktılar:
- `kfinans.app` → `141.144.243.54`
- `www.kfinans.app` → CNAME `kfinans.app` → `141.144.243.54`
- Diğerleri Resend dashboard'unda "Verified ✓" işaretlenmeli (5-15 dk propagasyon)

### 1.3 Namecheap Hesap Güvenliği

| Item | Durum | Hatırlatma |
|------|-------|------------|
| Hesap 2FA | ⏳ Faz D3'te aktif edilecek | Authenticator app + recovery code |
| Whois Privacy | ⏳ Faz D3'te aktif edilecek | Namecheap ücretsiz `.app` için sağlıyor |
| Auto-renew | ✅ Açık | Expire: **2027-05-06** |
| Registrar lock | ✅ Açık | Transfer lock (default) |

### 1.4 DNS Değişiklik Prosedürü

DNS panelinde değişiklik yapmadan önce:
1. **Mevcut kayıdın screenshot'ını** al (rollback için).
2. Değişikliği uygula, "Save" bas.
3. Propagasyon kontrolü: `nslookup ... 8.8.8.8` 5-15 dk sonra.
4. Bu dosyada §1.1 tablosunu güncelle (tarih + neyin değiştiği).
5. `git commit` ile bu dosyayı versiyonla.

---

## 2. Email Gönderimi — Resend

### 2.1 Hesap Bilgisi

| Bilgi | Değer |
|-------|-------|
| Servis | https://resend.com |
| Plan | Free (3.000 mail/ay, 100/gün) |
| Hesap | `celikada@gmail.com` üzerinden açıldı |
| Domain | `kfinans.app` |
| Region | `ap-northeast-1` (Tokyo) — domain ekleme sırasında bu seçildi; değiştirmek için domain'i silip yeniden eklemek gerek |
| API Key | `RESEND_API_KEY` — bkz. `.credentials.local.md` §4.1 (commit edilmez) |
| EMAIL_FROM | `KFinans <noreply@kfinans.app>` — ConfigMap'te (`k8s/configmap.yaml`) |

### 2.2 Domain Doğrulama Süreci (2026-05-14 tarihinde yapılan)

1. **Resend dashboard → Domains → Add Domain** → `kfinans.app`, region `ap-northeast-1` seçildi.
2. Resend 3 zorunlu + 1 opsiyonel DNS kaydı verdi:
   - DKIM (TXT `resend._domainkey`) — zorunlu
   - SPF MX (MX `send` → `feedback-smtp.ap-northeast-1.amazonses.com`) — zorunlu
   - SPF TXT (TXT `send` → `v=spf1 include:amazonses.com ~all`) — zorunlu
   - DMARC (TXT `_dmarc` → `v=DMARC1; p=none;`) — opsiyonel ama eklendi
3. Bu 4 kayıt Namecheap "Advanced DNS"e eklendi (bkz. §1.1).
4. Resend dashboard'da **"Verify DNS Records"** butonuna basıldı → DKIM doğrulanınca domain "Verified ✓".
5. API Key `Resend → API Keys → Create API Key` ile üretildi, `.credentials.local.md` §4.1'e kaydedildi.

### 2.3 Email Gönderim Akışı (Backend)

```
Backend → Resend API (HTTPS POST /emails)
       → Resend Tokyo region (ap-northeast-1)
       → Amazon SES (Resend'in altyapı sağlayıcısı)
       → DKIM imza (resend._domainkey TXT'deki public key ile doğrulanır)
       → Return-Path: bounce@send.kfinans.app
       → Kullanıcı inbox
```

Backend kod yolu:
- `backend/app/services/email.py` — `send_verification_email()`, `send_password_reset_email()`
- ConfigMap: `EMAIL_FROM=KFinans <noreply@kfinans.app>`, `FRONTEND_URL=https://kfinans.app`
- Secret: `RESEND_API_KEY`

### 2.4 API Key Rotation / Secret Fix (yeniden kullanılabilir runbook)

> **‼️ Kritik ders (2026-06-01, RESEND_API_KEY canlı fix):** `kfinans-secrets` Opaque secret tek bir secret nesnesidir; içindeki **tek bir key**'i `kubectl create secret ... | apply` ile güncellersen **diğer tüm key'leri ezersin** (DATABASE_URL, FERNET_KEY vb. kaybolur). Tek key değiştirmek için **`kubectl patch --type=merge`** kullan.
>
> **‼️ İkinci ders:** `deploy-production` job'u sadece `kubectl set image` yapar — secret/configmap **apply ETMEZ**. Canlı `kubectl patch` ile yaptığın değişiklik kalıcı **değildir**; bir sonraki `kubectl apply -k k8s/` veya GitOps reconcile, `k8s/sealed-secrets.yaml`'daki **eski** değeri geri getirir. Bu yüzden canlı fix'i **her zaman** SealedSecret güncellemesiyle eşle.

**Aşama A — Canlı düzeltme (anlık etki):**
```bash
# 1. (Rotation ise) Resend dashboard → API Keys → eski "Revoke" → "Create API Key" → re_xxx
# 2. Lokal: .credentials.local.md §4.1 güncelle
# 3. SADECE ilgili key'i merge-patch et (diğer key'leri korur):
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 "
  sudo kubectl patch secret kfinans-secrets -n kfinans --type=merge \
    -p '{\"stringData\":{\"RESEND_API_KEY\":\"re_YENI_KEY\"}}'
"
# 4. Backend pod'larını yeniden başlat (secret env'i yeniden okunsun):
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
  "sudo kubectl rollout restart deployment/backend -n kfinans"
```

**Aşama B — Kalıcılık (GitOps reconcile geri getirmesin):**
```bash
# 5. Yeni değeri SADECE bu key için strict-scope mühürle (kubeseal --raw):
echo -n 're_YENI_KEY' | kubeseal --raw \
  --scope strict \
  --namespace kfinans \
  --name kfinans-secrets \
  --cert <controller-pub-cert.pem>
# 6. Çıktıyı k8s/sealed-secrets.yaml içinde spec.encryptedData.RESEND_API_KEY'e yaz
# 7. MR aç (örn. MR #15 RESEND fix) → develop'a merge
```

> **Neden `--scope strict`?** Strict scope, ciphertext'i `namespace + name` çiftine kilitler; başka bir namespace/secret adıyla decrypt edilemez. `--raw` tek key'i mühürler — tüm secret'ı yeniden seal etmek gerekmez.

### 2.5 Fernet Key Rotation (önerilen: yıllık + kompromize halinde acil)

Fernet `FERNET_KEY` — DB'deki şifrelenmiş kolonları (wallet xpub, integration API key, MFA TOTP secret) korur. `MultiFernet` ile primary + secondary key'ler destekleniyor — rotation downtime'sız yapılabilir. Implementation: [`app/core/security.py::_build_fernet`](../../backend/app/core/security.py). CLI: [`backend/scripts/rotate_fernet.py`](../../backend/scripts/rotate_fernet.py). Test: `tests/unit/test_security.py::TestMultiFernetKeyRotation` (5 case).

**5 aşamalı prosedür:**

1. **Yeni key üret + güvenli yedek:**
   ```bash
   py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   # Çıktı: aBcDeFgHi...= (44 karakter URL-safe base64)
   ```
   Yeni key'i `.credentials.local.md` + Bitwarden/USB'ye kaydet (3-2-1 yedekleme).

2. **Secondary key olarak ESKİ primary'yi ekle (read fallback):**
   ```bash
   ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
     "sudo kubectl set env deployment/backend -n kfinans \
       FERNET_KEYS_SECONDARY='[\"<eski-primary-key>\"]'"
   # Backend pod restart tetiklenir; eski + yeni key birlikte aktif olur (decrypt için).
   ```

3. **Primary key'i YENİ ile değiştir (write artık yeni key ile):**
   ```bash
   # merge-patch — diğer key'leri (DATABASE_URL, SECRET_KEY ...) ezme! (bkz. §2.4 ders)
   ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 "
     sudo kubectl patch secret kfinans-secrets -n kfinans --type=merge \
       -p '{\"stringData\":{\"FERNET_KEY\":\"<yeni-primary-key>\"}}'
     sudo kubectl rollout restart deployment/backend -n kfinans
   "
   ```
   Bu noktada **yeni encrypt'ler yeni key ile, eski encrypt'ler hâlâ eski key ile**. Yeni key olmadan eski veriler okunamaz, eski key olmadan yeni veriler okunamaz — `MultiFernet` her ikisini de saklar.
   > Kalıcılık için `FERNET_KEY`'i de `kubeseal --raw --scope strict` ile mühürleyip `k8s/sealed-secrets.yaml`'a yaz (bkz. §2.4 Aşama B) — aksi halde GitOps reconcile eski key'i geri getirir.

4. **Re-encrypt CLI ile tüm row'ları yeni key'e taşı:**
   ```bash
   # Önce dry-run — decrypt başarısı kontrolü, DB'ye yazma yok:
   ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
     "sudo kubectl exec -n kfinans deploy/backend -- py -m scripts.rotate_fernet --dry-run"
   # Hata yoksa gerçek rotate:
   ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
     "sudo kubectl exec -n kfinans deploy/backend -- py -m scripts.rotate_fernet"
   ```
   Çıktıda `başarı: N, hata: 0` görmen lazım. Hata varsa: 4. adımdaki secondary key listesinde eksik bir eski key var demektir — geri dön + ekle.

5. **Secondary key'i kaldır (eski key kullanımdan çıkar):**
   ```bash
   ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
     "sudo kubectl set env deployment/backend -n kfinans FERNET_KEYS_SECONDARY='[]'"
   ```
   Eski key artık DB'de hiçbir yerde gerekmiyor — kaldırılabilir. Yedek olarak Bitwarden'da en az 1 yıl daha tut (audit/forensik için).

**Etkilenen kolonlar (CLI bunları gezer):**
- `wallet_addresses.address_encrypted` — blockchain xpub/adres
- `integrations.encrypted_key`, `integrations.encrypted_secret` — Binance/iCrypex API key + secret
- `users.totp_secret` — MFA TOTP base32 secret (sadece MFA aktif kullanıcılar)

**Rollback (4. adım sırasında sorun):**
Re-encrypt'in tamamı atomik değil — script her batch'te commit yapar. Kısmen rotate edilmiş satırlar yeni key ile encrypt'lenmiştir, geri kalanlar eski. Her iki key de aktif olduğu sürece (secondary ekliyse) sistem çalışmaya devam eder. Sorun çözüldükten sonra script'i yeniden çalıştır — idempotent (rotate edilmiş bir token'ı tekrar rotate etmek sorunsuz, yeni primary ile encrypt'lenmiş ciphertext değişir ama içerik aynı).

### 2.6 DKIM Key Rotation (önerilen: yıllık)

DKIM private key Resend tarafında saklanır, biz sadece public key'i DNS'e yazıyoruz. Rotation Resend dashboard'undan tetiklenir:

1. Resend → Domains → kfinans.app → "Rotate DKIM"
2. Resend yeni `resend._domainkey` TXT değeri verir.
3. **Eski TXT'yi hemen silme** — eski key'le imzalanmış mail'ler in-transit olabilir. 48 saat eski + yeni key bir arada tutulur.
4. 48 saat sonra eski TXT silinir.
5. Bu dosyada §1.1 tablosundaki DKIM value güncellenir + commit.

### 2.7 Yaygın Email Hataları

| Sorun | Tanı | Çözüm |
|-------|------|-------|
| `403 You can only send to verified addresses` | Domain doğrulanmadı | Resend dashboard "Verified ✓" mı kontrol; DKIM TXT propagasyon |
| Mail spam klasörüne düşüyor | SPF/DKIM/DMARC eksik veya yanlış | `dig TXT _dmarc.kfinans.app`, `mail-tester.com` skorla |
| Resend rate limit (429) | Plan limiti aşıldı | Resend dashboard usage → plan upgrade veya dağıtık gönderim |
| `Email_from invalid` | EMAIL_FROM domain doğrulanmamış | ConfigMap'te `EMAIL_FROM` doğru, domain "Verified ✓" mı |

---

## 3. Oracle Cloud VM + K3s

### 3.1 Bağlantı

```powershell
ssh -i C:\Users\celik\Projects\oracleCloud\ssh-key-2026-03-24.key ubuntu@141.144.243.54
```

| Bilgi | Değer |
|-------|-------|
| Sağlayıcı | Oracle Cloud Always Free Tier |
| VM IP | `141.144.243.54` |
| SSH User | `ubuntu` |
| OS | Ubuntu 22.04 LTS ARM (free tier sağlar AMD64'e geçiş yapıldı veya hala ARM kontrol gerekli) |
| Cluster | K3s |
| Namespace | `kfinans` |
| Repo path | `~/kfinans` (git clone) |

### 3.2 Sık Kullanılan Komutlar

```bash
# Pod durumu
sudo kubectl get pods -n kfinans -o wide

# Pod log (canlı)
sudo kubectl logs -f deployment/backend -n kfinans
sudo kubectl logs -f deployment/frontend -n kfinans
sudo kubectl logs -f statefulset/postgres -n kfinans

# Secret listele (içerik göstermez)
sudo kubectl get secret kfinans-secrets -n kfinans -o jsonpath='{.data}' | jq 'keys'

# Configmap incele
sudo kubectl get configmap kfinans-config -n kfinans -o yaml

# Deployment restart (secret/configmap değişikliği sonrası)
sudo kubectl rollout restart deployment/backend -n kfinans

# Image versiyonu kontrol
sudo kubectl get pods -n kfinans -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

# Ingress + cert durumu
sudo kubectl get ingress -n kfinans
sudo kubectl get certificate -n kfinans
sudo kubectl describe certificate kfinans-tls -n kfinans  # cert-manager log
```

### 3.3 Cert-Manager (Let's Encrypt)

`kfinans.app` ve `www.kfinans.app` için Let's Encrypt HTTP-01 challenge ile sertifika alır:

```bash
# Cert listesi
sudo kubectl get certificate -A
sudo kubectl get certificaterequest -n kfinans
sudo kubectl get order -n kfinans  # ACME order durumu

# Cert renewal kontrolü (cert-manager otomatik 30 gün önce yeniler)
sudo kubectl describe certificate kfinans-tls -n kfinans | grep -A 5 "Renewal Time\|Not After"

# Manuel renewal tetikleme (acil)
sudo kubectl cert-manager renew kfinans-tls -n kfinans
```

---

## 4. Periyodik Bakım

| Sıklık | İş | Komut |
|--------|----|-----|
| Otomatik (Pazar 23:00 Europe/Istanbul) | Weekly snapshot | `kubectl logs -n kfinans deployment/backend | grep snapshot` |
| Otomatik (her gün 03:00) | revoked_tokens cleanup | Scheduler log kontrol |
| Otomatik (her gün 04:00) | hard-delete expired users | KVKK m.7, 30 gün geçmiş soft-delete |
| Otomatik (her gün 04:30) | audit_logs retention | KVKK m.7, 365 gün'den eski log silinir |
| **Aylık** | Postgres backup integrity check | `kubectl exec -n kfinans postgres-0 -- pg_dump kfinans > /tmp/backup.sql` |
| **Aylık** | Pod restart count + log review | `kubectl get pods -n kfinans` (`RESTARTS` kolonu > 0 ise log incele) |
| **Aylık** | DNS propagasyon kontrol | `nslookup kfinans.app 8.8.8.8` (kayıt değişmediyse OK) |
| **Aylık** | Resend usage check | Resend dashboard → Usage |
| **Aylık** | Sentry error rate review | Sentry dashboard (SENTRY_DSN set ise) |
| **3 aylık** | Cert-manager renewal log | `kubectl get certificate -A` (Not After > 30 gün) |
| **Yıllık** | RESEND_API_KEY rotate | bkz. §2.4 |
| **Yıllık** | DKIM key rotate | bkz. §2.5 |
| **Yıllık** | Domain renewal (Namecheap) | Expire 2027-05-06 — auto-renew açık ama 30 gün önce email gelir |
| **Yıllık** | ORACLE_SSH_KEY rotate | yeni keygen + authorized_keys + GitHub secret update (bkz. `.credentials.local.md` §🚨) |

---

## 5. Acil Durum

### 5.1 Site Down (5xx veya bağlanamıyor)

```bash
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54

# 1. Pod sağlık
sudo kubectl get pods -n kfinans
# Backend CrashLoopBackOff mı? → log kontrol
sudo kubectl logs -n kfinans deployment/backend --tail=100

# 2. Cluster sağlık
sudo kubectl get nodes
sudo kubectl top nodes  # CPU/memory

# 3. Geri alma (en hızlı rollback)
sudo kubectl rollout undo deployment/backend -n kfinans
sudo kubectl rollout undo deployment/frontend -n kfinans

# 4. Eski versiyona dönüş
sudo kubectl rollout history deployment/backend -n kfinans
sudo kubectl rollout undo deployment/backend --to-revision=N -n kfinans
```

### 5.2 SSL Cert Süresi Doluyor

```bash
# Cert-manager otomatik yeniler, ama acilse:
sudo kubectl delete certificate kfinans-tls -n kfinans
sudo kubectl apply -k ~/kfinans/k8s/  # cert-manager yeniden oluşturur
```

### 5.3 Database Crash

```bash
# Postgres pod restart
sudo kubectl rollout restart statefulset/postgres -n kfinans

# Pod log
sudo kubectl logs statefulset/postgres -n kfinans --tail=200

# Disk doldu mu?
sudo kubectl exec -n kfinans postgres-0 -- df -h /var/lib/postgresql/data

# Backup'tan restore (acil — kullanıcı verisi kaybı uyarısı):
# k8s/backup-cronjob.yaml günlük backup alıyor
sudo kubectl get cronjob -n kfinans
```

### 5.4 DNS Yanlış (yeni IP'ye geçiş)

Namecheap'e gir, `@` ve gerekirse `www` A kaydını yeni IP'ye güncelle. Propagasyon 5 dk (TTL).

### 5.5 Email Gitmiyor

```bash
# 1. Resend API key valid mi?
ssh -i ~/.ssh/oracle.key ubuntu@141.144.243.54 \
  "sudo kubectl get secret kfinans-secrets -n kfinans -o jsonpath='{.data.RESEND_API_KEY}' | base64 -d | head -c 10"

# 2. Backend log
sudo kubectl logs deployment/backend -n kfinans | grep -i "resend\|email"

# 3. Resend dashboard → Logs (son 7 gün gönderim listesi + delivery status)

# 4. Domain hala "Verified" mı? Resend dashboard kontrol.

# 5. DKIM TXT hala doğru mu?
nslookup -type=TXT resend._domainkey.kfinans.app 8.8.8.8
```

---

## 6. Bağlantılı Dosyalar

- `.credentials.local.md` — gerçek secret değerleri (gitignore'da, asla commit edilmez)
- `docs/production-deploy-checklist.md` — ilk prod deploy checklist
- `docs/09-altyapi-test.md` — altyapı + CI/CD stratejisi
- `k8s/` — Kubernetes manifest'leri (namespace, configmap, secrets.example, **sealed-secrets.yaml**, postgres, postgres-cert, backend, frontend, ingress, backup-cronjob, kustomization)
- `.gitlab-ci.yml` — **primary CI/CD**: lint → test → quality (blocking SonarQube) → build (Kaniko → Docker Hub) → deploy-production (semver tag, `when: manual`)
- `.github/workflows/release.yml` — **çalışmıyor** (GitHub flag #4360519); repoda kalıyor ama 0 run

---

## 7. Değişiklik Geçmişi

| Tarih | Değişiklik |
|-------|-----------|
| 2026-05-14 | İlk versiyon: DNS (A `@` + CNAME `www` + Resend 4 TXT/MX), Resend domain doğrulama, bakım periyodikleri, acil durum komutları |
| 2026-06-01 | §2.4 yeniden yazıldı: secret fix `kubectl patch --type=merge` (tek key ezme dersi) + SealedSecret kalıcılık (`kubeseal --raw --scope strict`) iki aşamalı runbook. §2.5 Fernet rotation step 3 patch-merge'e çevrildi. §6 GitLab CI referansları. RESEND_API_KEY canlı fix retrospektifi. |
