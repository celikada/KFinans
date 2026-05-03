# KVKK ve Regülasyon Uyumluluğu

**Sahip ajan:** `compliance-expert`
**İlgili:** [guvenlik.md](./guvenlik.md), [kredi-sistemi.md](./kredi-sistemi.md)

---

## 1. Yasal Çerçeve

### 1.1 Birincil Mevzuat
- **6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK)** — Türkiye
- **GDPR (Regulation 2016/679)** — yurt dışı kullanıcılar veya AB'ye veri transferi olursa
- **6362 sayılı Sermaye Piyasası Kanunu** — yatırım danışmanlığı sınırı
- **6493 sayılı Ödeme ve Menkul Kıymet Mutabakat Sistemleri Kanunu** — ödeme aracılığı
- **6502 sayılı Tüketicinin Korunması Hakkında Kanun** — mesafeli sözleşme, cayma hakkı
- **5651 sayılı İnternet Ortamında Yapılan Yayınların Düzenlenmesi Kanunu** — log saklama (1-2 yıl)

### 1.2 KFinans'ın Konumu
- **Veri Sorumlusu:** Mayotek (KFinans operatörü)
- **Yatırım Danışmanlığı:** ❌ DEĞİL — bilgilendirme amaçlı içerik üretir, bağlayıcı tavsiye sağlamaz
- **Ödeme Aracılığı:** ❌ DEĞİL — kullanıcının kendi exchange hesaplarını okur, fon hareket ettirmez
- **Hizmet Modeli:** SaaS (kişisel finans yönetim aracı)

---

## 2. KVKK Açısından İşlenen Veriler

| Veri | Kategori | Yasal Zemin (KVKK m.5) | Saklama |
|------|----------|------------------------|---------|
| E-posta + şifre hash | Kimlik bilgisi | Sözleşme ifası | Hesap silinene + 30 gün |
| Exchange API key (Fernet şifreli) | Mali bilgi (özel nitelik dışı) | **Açık rıza zorunlu** | Hesap silinene + 30 gün |
| Cüzdan adresleri | Finansal | Açık rıza | Hesap silinene + 30 gün |
| Portföy snapshot (haftalık) | Finansal | Sözleşme ifası | Hesap silinene + 30 gün |
| AI tavsiye içeriği | Türev veri | Sözleşme ifası | Hesap silinene + 30 gün |
| IP adresi (rate limiter, log) | Kimlik bilgisi | Meşru menfaat (m.5/2-f) | 1-2 yıl (5651 yasal arşiv) |
| User-Agent | Cihaz bilgisi | Meşru menfaat | 1-2 yıl |
| Kredi/ödeme kayıtları | Mali bilgi | Sözleşme ifası + yasal yükümlülük (TTK) | 10 yıl |

### 2.1 Özel Nitelikli Veri YOK
KFinans **şifrelenmiş kişisel veri** içermez (sağlık, etnik köken, biyometrik vb.). Ancak finansal varlık bilgileri **hassas** kabul edilmeli.

---

## 3. Yasal Belgeler

### 3.1 Kullanıcı Görünür Belgeler
- [x] **KVKK Aydınlatma Metni** — `/legal/kvkk` (2026-05-02) — register'da "okudum" onayı zorunlu
- [x] **Gizlilik Politikası** — `/legal/privacy` (2026-05-02) — register'da kabul onayı zorunlu, footer linki
- [x] **Kullanım Şartları** — `/legal/terms` (2026-05-02) — register'da kabul onayı zorunlu
- [x] **Çerez Politikası** — `/legal/cookies` (2026-05-02) — şu an sadece zorunlu oturum çerezi
- [x] **Açık Rıza — Yurt Dışı Aktarım** — register'da Anthropic/Resend (ABD) için ayrı checkbox (KVKK m.9)
- [ ] **Mesafeli Sözleşme** — kredi paketi satın alma öncesi (Faz 3 — 6502 sayılı Kanun)

> **Doldurulması gereken placeholder'lar** (yasal metinlerde işaretli):
> - `[TİCARİ ÜNVAN]`, `[KEP_ADRESI]`, `[TEBLİGAT_ADRESİ]` — `legal/kvkk/page.tsx`
> - `[İSTANBUL/MERKEZ]` — `legal/terms/page.tsx`
> - `kvkk@kfinans.app` ve `privacy@kfinans.app` mailbox'ları kurulmalı

### 3.2 Operasyonel Belgeler (İç Kullanım)
- [ ] Kişisel Veri İşleme Envanteri (VERBİS kaydı için — şu an eşik altı, gerekli değil)
- [ ] Veri saklama ve imha politikası — KVKK metni Bölüm 5'te kullanıcı görünür özet var
- [x] Veri ihlali müdahale planı (72 saat bildirim) — KVKK metni Bölüm 8 ve gizlilik politikası taahhüt ediyor; iç süreç dokümanı Faz 3
- [ ] Personel gizlilik taahhütnameleri (şirket büyüdüğünde)
- [ ] Üçüncü taraf veri işleme sözleşmeleri (Anthropic, iyzico, AWS) — SCC imzalanmalı

### 3.3 VERBİS Kaydı
KVKK m.16 — Veri Sorumluları Sicili (VERBİS) kaydı şu eşiklerde zorunlu:
- Yıllık çalışan sayısı 50+ **VEYA**
- Yıllık mali bilanço 25M ₺+ **VEYA**
- Ana faaliyeti özel nitelikli veri işleme

KFinans bu eşikleri aşmasa da, **kullanıcı sayısı 1000+ olunca gönüllü kayıt yaptırılması önerilir** (güven sinyali).

---

## 4. Kullanıcı Hakları (KVKK m.11)

Backend'de implement edilmesi gereken endpoint'ler:

### 4.1 Veri Erişim ve Taşınabilirlik (Yapılacak)
```
GET /api/v1/me/data-export
```
Kullanıcının tüm kişisel verisini JSON olarak indirmesi:
```json
{
  "user":         { "email": "...", "created_at": "...", "risk_profile": "..." },
  "integrations": [{ "provider": "binance", "is_active": true, ... }],
  "wallets":      [{ "chain": "sonic", "address": "0x...", ... }],
  "tefas_holdings": [...],
  "stock_holdings": [...],
  "snapshots":      [...],
  "advice_history": [...],
  "credit_transactions": [...]
}
```
**Encrypted_key alanları DAHİL EDİLMEZ** — şifrelenmiş içerik kullanıcıya yarar sağlamaz, ifşa riski oluşturur.

### 4.2 Düzeltme (Yapılacak)
```
PATCH /api/v1/me
{ "email": "yeni@x.com", "risk_profile": "balanced" }
```

### 4.3 Silme — "Unutulma Hakkı" (Yapılacak)
```
DELETE /api/v1/me/account
```
**Yumuşak silme akışı (30 gün cayma süresi):**
```
1. soft delete: users.deleted_at = now()
2. tüm aktif session'lar iptal (refresh token blacklist)
3. integrations.is_active = false (API key'leri kullanma)
4. 30 gün sonra (cron job): hard delete
   - PII alanları anonimleştir veya SİL
   - email → '<deleted-{uuid}>'
   - encrypted_key, encrypted_secret, encrypted_extra → NULL
   - wallet_addresses, holdings, integrations CASCADE silinir
   - portfolio_snapshots, asset_positions, advice → KORUNUR (anonim) — istatistik için
   - credit_transactions → KORUNUR (TTK m.82, 10 yıl)
```

### 4.4 İşleme İtiraz / Kısıtlama (Yapılacak)
```
POST /api/v1/me/data-processing/object
{ "purpose": "marketing" }
```
Pazarlama, AI eğitim verisi gibi opsiyonel kullanımları durdurur (Faz 4).

### 4.5 Açık Rıza Geri Çekme (Yapılacak)
Exchange API key, blockchain adres gibi **açık rıza ile alınan** verilerin silinmesi:
```
DELETE /api/v1/integrations/{id}
DELETE /api/v1/wallets/{id}
```
✅ Bu endpoint'ler zaten mevcut. KVKK uyumlu.

---

## 5. Üçüncü Taraf Veri Aktarımı

### 5.1 Mevcut Aktarımlar

| Üçüncü Taraf | Aktarılan Veri | Lokasyon | Yasal Zemin | Açık Rıza |
|--------------|----------------|----------|-------------|-----------|
| **Anthropic (Claude API)** | Anonimleştirilmiş portföy özeti (yüzde, top varlık sembolü) | ABD | Sözleşme ifası | ⚠️ **Yurt dışı aktarım — açık rıza zorunlu** |
| Binance, iCrypex | Yok (kullanıcı kendi hesabını okur) | – | – | – |
| Yahoo Finance | Yok (sadece public ticker) | ABD | – | – |
| TEFAS | Yok | TR | – | – |
| Blockchain RPC'ler | Public adres | Çeşitli | Public veri | – |
| iyzico (Faz 3) | Ödeme bilgileri (ad, email, kart token) | TR | Sözleşme ifası + yasal yükümlülük | – |

### 5.2 Yurt Dışı Aktarım (KVKK m.9)
**Anthropic ABD merkezli** ve KVKK Kurulu'nun "yeterli koruma sağlayan ülkeler" listesinde **yer almıyor**. Bu nedenle:
- Açık rıza zorunlu (kullanıcı AI tavsiye almak istediğinde onay vermeli)
- Gizlilik politikasında açıkça belirtilmeli
- Veri minimizasyonu: sadece **anonim** portföy verisi gönderilmeli (şu an `advisor.py` symbol döndürüyor — kabul edilebilir, ama email/ID aslagönderilmemeli)

### 5.3 GDPR Hatırlatması (Yurt Dışı Kullanıcı)
Faz 4'te uluslararası açılım planlanıyorsa:
- AB kullanıcıları için ayrı consent flow (GDPR m.6, m.49)
- Veri Standart Sözleşmesi (Standard Contractual Clauses) Anthropic, AWS gibi taraflarla
- DPO (Data Protection Officer) ataması (250+ AB kullanıcısı varsa)

---

## 6. Çerez Politikası

### 6.1 Mevcut Çerez Kullanımı
| Çerez | Tip | Amaç | Rıza Gerekli? |
|-------|-----|------|---------------|
| `access_token` | Auth | Oturum doğrulama (proxy.ts) | ❌ Hayır (zorunlu — strictly necessary) |

### 6.2 Eklendiğinde Rıza Gerekenler
- Analytics (Plausible, Google Analytics)
- Pazarlama / remarketing pixel
- Üçüncü taraf gömülü içerik (YouTube, Twitter widget)

### 6.3 Cookie Banner Gereksinimleri (Eklendiğinde)
- "Tümünü kabul et" + "Sadece zorunlu" + "Tercihleri yönet" seçenekleri
- Reddetme kabul ile aynı kolaylıkta olmalı (GDPR ihlali olmaması için)
- Tercih bilgisi 6 ay saklanır
- Önceden tercih varsa banner gösterilmez

---

## 7. SPK Yatırım Danışmanlığı Sınırı

### 7.1 Yasal Sınır
SPK Madde 35: Yatırım danışmanlığı **lisans gerektiren** bir faaliyettir. Lisanssız kişiler bağlayıcı yatırım tavsiyesi veremez.

### 7.2 KFinans'ın Pozisyonu
- AI tavsiyeleri **bilgilendirme amaçlıdır**, bağlayıcı değildir
- Her tavsiye sayfasında **zorunlu uyarı**:

```
⚠️ ÖNEMLİ UYARI
Bu içerik bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.
Yatırım kararlarınızı SPK lisanslı bir yatırım danışmanına
danışarak vermeniz önerilir. Mayotek/KFinans bu içerikten
doğacak yatırım kararlarınızdan sorumlu değildir.
```

### 7.3 Yapılacak (Frontend)
- AI tavsiye sayfasında uyarıyı sticky banner olarak göster
- Kullanım Şartları'nda madde olarak yer al
- AI çıktısının başında veya sonunda Markdown'a otomatik ekle

---

## 8. Kripto Düzenlemesi (TR — 2026)

### 8.1 KFinans'ın Kapsam Dışılığı
KFinans:
- ❌ Kripto borsa **DEĞİL** (Crypto Asset Service Provider — CASP listesi dışı)
- ❌ Kripto saklama hizmeti **DEĞİL** (custody yapmıyor)
- ✅ Sadece **bilgi okuyan** ve görselleştiren bir araç

### 8.2 Read-Only API Key Zorunluluğu
Kullanıcıya integrations sayfasında belirgin uyarı:
```
⚠️ Binance/iCrypex API key'inizi oluştururken sadece "Enable Reading"
iznini açın. "Enable Spot & Margin Trading" veya "Enable Withdrawals"
kesinlikle KAPALI olmalıdır.

KFinans hiçbir koşulda fonlarınızı hareket ettirmez. Withdrawals açık
bir API key oluşturmuş olsanız bile, KFinans bu izni kullanmaz —
ancak güvenliğiniz için kapalı tutmanız gerekir.
```

### 8.3 Cüzdan Adresi
- KFinans **public adres** alır, **özel anahtar/seed phrase ASLA** istemez
- Frontend'de bu net gösterilmeli: "Adresinizi yapıştırın (0x ile başlayan, 40 karakter)"
- Phishing riski: kullanıcı yanlışlıkla seed phrase yapıştırırsa → form submit edilmemeli (uzunluk + karakter validation)

---

## 9. Veri İhlali Müdahale Planı

### 9.1 KVKK m.12 Bildirim Yükümlülüğü
**Veri ihlali tespit edildikten sonra 72 saat içinde** Kişisel Verileri Koruma Kurumu'na (KVKK Kurulu) ve etkilenen kullanıcılara bildirim zorunludur.

### 9.2 Müdahale Adımları
```
1. TESPIT
   ↓ Sentry/log alarmı, kullanıcı şikayeti, dış taraf bildirimi

2. İZOLE ET (5-30 dk)
   ↓ Etkilenen pod/servis durdur, IP block, session iptal

3. KAPSAM BELIRLE (1-12 saat)
   ↓ Hangi user'lar etkilendi? Hangi veri sızdı? Logları incele.

4. DÜZELT (12-48 saat)
   ↓ Açığı kapat, deploy et, retroactive audit

5. BİLDİR (72 saat içinde — KVKK m.12)
   ↓ KVKK Kurulu (online form: kvkk.gov.tr/Anasayfa/IhlalBildirimi)
   ↓ Etkilenen kullanıcılara e-posta + uygulama içi bildirim
   ↓ Mahalli savcılığa (suç şüphesi varsa)

6. POST-MORTEM (1-2 hafta)
   ↓ Süreç güncellemesi, yeni güvenlik kontrolleri, audit log
```

### 9.3 Bildirim Şablonu (Kullanıcıya)
```
Konu: Hesabınızı ilgilendiren önemli güvenlik bilgilendirmesi

Sayın [Ad],

[TARIH] tarihinde sistemimizde tespit ettiğimiz bir güvenlik
olayı sebebiyle, hesabınızla ilişkili [VERİ TÜRÜ] bilgilerinin
yetkisiz erişime maruz kalmış olabileceği değerlendirilmektedir.

Etkilenen veriler:
- ...

Sizin için önerdiğimiz adımlar:
- Şifrenizi değiştirin
- Exchange API key'lerinizi yenileyin
- ...

Detaylı bilgi: https://kfinans.app/incident/{incident-id}
İletişim: privacy@mayotek.com
```

---

## 10. Audit ve Sertifikasyon (Faz 4-5)

### 10.1 İlerleyen Aşamalarda Düşünülmesi Gerekenler
- **ISO 27001** — Bilgi güvenliği yönetim sistemi
- **SOC 2 Type II** — ABD/AB B2B müşteriler için
- **PCI DSS** — Kart verisi işleniyorsa (iyzico aracılığı varsa kapsam dışı)
- **TS EN ISO/IEC 27701** — KVKK uyum sertifikasyonu (Türkiye)

### 10.2 Yıllık Sızma Testi
Production'a çıktıktan sonra yıllık penetration testing önerilir (TÜBİTAK BİLGEM veya bağımsız firma).

---

## 11. Uyumluluk Kontrol Listesi

### Yeni Özellik / Veri Kaynağı Eklendiğinde
- [ ] Yeni kişisel veri toplanıyor mu? Aydınlatma metnine eklendi mi?
- [ ] Yasal zemin nedir? (sözleşme, açık rıza, meşru menfaat, yasal yükümlülük)
- [ ] Açık rıza gerekiyorsa frontend'de checkbox + zaman damgası kayıt edildi mi?
- [ ] Yurt dışı aktarım var mı? Gizlilik politikasında belirtildi mi?
- [ ] Saklama süresi tanımlandı mı? Otomatik silme cron'u var mı?
- [ ] Veri minimize edildi mi (sadece gerekli alanlar)?
- [ ] Audit log eklendi mi?

### Periyodik Kontroller (Yıllık)
- [ ] Gizlilik politikası güncel mi?
- [ ] Üçüncü taraf listesi değişti mi?
- [ ] Personel KVKK eğitimi (varsa)
- [ ] VERBİS kaydı güncel mi?
- [ ] Veri ihlali müdahale planı drill edildi mi?

---

## 12. İletişim

- **Veri Sorumlusu:** Mayotek
- **Veri Sorumlusu Temsilcisi:** [İsim, e-posta — Faz 2'de atanacak]
- **Privacy e-posta:** privacy@mayotek.com (kurulacak)
- **KVKK başvuru e-posta:** kvkk@kfinans.app (kurulacak)
- **DPO (Data Protection Officer):** Faz 4'te atanacak (uluslararası açılımla)

---

## 13. Eksik / Eklenecek (TODO)

### Faz 2 (SaaS hazırlık)
- [ ] Gizlilik Politikası, Kullanım Şartları, KVKK Aydınlatma Metni hazırla
- [ ] Kayıt formuna "Kullanım şartlarını okudum, kabul ediyorum" checkbox
- [ ] Frontend cookie banner (sadece analytics eklenirse aktif)
- [ ] AI tavsiye sayfasında SPK uyarısı banner

### Faz 3 (Kredi sistemi öncesi)
- [ ] `users.deleted_at` kolonu + soft delete migration
- [ ] `GET /me/data-export` endpoint
- [ ] `DELETE /me/account` endpoint (30 gün cayma + cron)
- [ ] `audit_logs` tablosu + tüm sensitive eylemlerde kayıt
- [ ] Veri ihlali müdahale planı operasyonel doküman
- [ ] Anthropic için açık rıza akışı (AI tavsiye'ye ilk girişte modal)

### Faz 4 (Uluslararası)
- [ ] GDPR uyum (AB kullanıcıları)
- [ ] DPO ataması veya dış danışmanlık
- [ ] ISO 27001 sertifikasyon süreci
- [ ] Bağımsız sızma testi (yıllık)
