# KFinans — Veri İhlali Müdahale Planı (ISO 27035 esinli)

**Versiyon:** 1.0
**Tarih:** 2026-05-10
**Sahip:** Mayotek (KFinans veri sorumlusu)
**Yıllık tatbikat:** Ocak ayı (table-top)
**Sahip ajan:** `compliance-expert`, `security-expert`

> **DOC reference:** `docs/08-uyumluluk-kvkk.md` Bölüm 9 yüksek seviye akışı
> bu belgede operasyonel hale getirilmiştir. KVKK m.12/5 (gecikmeksizin
> Kurul'a bildirim) ve GDPR Art.33 (72 saat) uyumlu.

---

## 1. Kapsam

KFinans uygulamasında **kişisel veri ihlali** sayılan olaylara müdahale eder:

- DB/replica sızıntısı (kullanıcı tablosu, wallet adresleri, snapshot'lar)
- API key/secret sızıntısı (Fernet master key, JWT secret, Anthropic API key)
- Auth bypass / yetkisiz erişim
- Saldırı sonucu kullanıcı verisi şifrelenmesi (ransomware)
- Üçüncü taraf hizmet (Anthropic, Resend, Hetzner Cloud, GitLab/GitHub, self-hosted SonarQube) ihlali

**Kapsam dışı:** Bireysel kullanıcı hesabının kendi sosyal mühendislik ile
ele geçirilmesi (kullanıcı sorumluluğu).

---

## 2. Roller ve Sorumluluklar

| Rol | Kişi (2026-05-10) | Sorumluluk |
|-----|-------------------|------------|
| **İhlal Komutanı (IC)** | Mayotek kurucusu (Ada Çelik) | Müdahalenin tüm aşamasını koordine eder, son söz |
| **Teknik Lead** | celikada@gmail.com | Teknik mitigasyon (rotate secrets, revoke tokens, rollback) |
| **KVKK İrtibat** | Mayotek kurucusu | Kurul bildirimi, kullanıcı tebligatı, KEP gönderimi |
| **Hukuk** | (Boş — gerektiğinde dış danışman) | Yasal yorum, basın açıklaması taslak |
| **İletişim** | Mayotek kurucusu | Kullanıcı e-postası, sosyal medya, GitHub Discussions |

**Yedek (ana kişi ulaşılamadığında):** ana kişi 4 saat yanıt vermezse
otomatik IC bayrağı ekipte 2. seviye geçer (şu an tek kişilik takım — yedek
süreç eklenmesi Faz I item).

---

## 3. Tetikleyiciler (Detection)

İhlal şüphesi şu kanallardan gelebilir:

1. **Otomatik:** Sentry alert (500 spike), audit_logs anormal pattern (login_failed >100/dk),
   CodeQL/Trivy CVE kritik, gitleaks pre-commit/CI fail, self-hosted SonarQube hotspot
2. **Manuel:** Kullanıcı raporu (security@kfinans.app — Faz F SECURITY.md),
   GitHub Discussions, sosyal medya
3. **Üçüncü taraf:** Anthropic/Resend/GitHub/Hetzner Cloud güvenlik bildirimi

**İlk doğrulama:** IC olayın gerçek mi false-positive mi olduğunu **30 dakika
içinde** karara bağlar; gerçekse §4 başlatılır.

---

## 4. Müdahale Akışı (Timeline)

### T+0 — İhlal Doğrulaması (0-30 dakika)
- IC olay açıklamasını yazılı kayda alır (`incidents/YYYY-MM-DD-slug.md`)
- Severity sınıflandırması: Critical / High / Medium / Low
- Aşağıdaki sorular cevaplanır:
  1. Etkilenen veri türü? (auth, finansal, identifier, log)
  2. Etkilenen kullanıcı sayısı? (1 / 10-100 / >100 / tüm DB)
  3. Saldırgan hâlâ erişimde mi? (containment önceliği)

### T+30dk — Containment (Kapsama)
- **DB sızıntısı şüphesi:** Postgres `REVOKE`/`pg_terminate_backend` ile aktif
  bağlantıları kes. Replica varsa promote'u durdur.
- **API key sızıntısı:** Anthropic (console.anthropic.com), Resend, Hetzner Cloud,
  GitHub PAT, Fernet master key — **derhal rotate**.
- **JWT sızıntısı:** `SECRET_KEY` rotate edilince **tüm aktif token geçersiz**;
  kullanıcılar yeniden login. revoked_tokens tablosu da sıfırlanır.
- **Auth bypass:** Sızan endpoint'i geçici olarak feature flag ile kapat
  (Faz I — şu an manuel deploy ile rollback).

### T+1 saat — Eradication (Temizleme)
- Saldırgan persistence kontrolü: cron jobs, webhook'lar, eklenmiş users.
- Backup'tan rollback gerekli mi karar (RPO 24 saat — Pazar 23:00 öncesi).
- CVE'siz kalmak için: `pip install --upgrade <vulnerable-package>` +
  release.

### T+2-72 saat — Recovery + Bildirim
- **Kullanıcı bildirimi (KVKK m.12/5 + GDPR Art.34):**
  - Doğrudan etkilenen kullanıcılara e-posta + uygulama içi banner
  - Şablon: §6 (Bildirim E-postası Şablonu)
- **KVKK Kurulu bildirimi (KVKK m.12/5):** **gecikmeksizin** Veri İhlali
  Bildirim Formu doldurulur (kvkk.gov.tr), KEP ile gönderilir.
  - KEP adresi: (Mayotek henüz açmadı — `project_kvkk_placeholders` memo'su)
  - Şablon: §7
- **GDPR (yurt dışı kullanıcı varsa) Art.33:** 72 saat içinde ilgili AB
  veri koruma otoritesine bildirim.

### T+1 hafta — Lessons Learned
- IC retrospektif yazar: kök neden, neyi yakaladık, ne kaçırdık.
- Action item'lar GitHub issue olarak açılır (label: `incident-followup`).
- Yıllık tatbikat planına eklenir (table-top egzersiz Ocak ayı).

---

## 5. Severity Matrisi

| Severity | Kriter | Hedef Süre (T+0'dan) |
|----------|--------|----------------------|
| **Critical** | DB komple sızıntısı / Fernet master key sızıntısı / aktif sömürü | Containment 30dk, Kurul bildirim 6 saat |
| **High** | Tek kullanıcı verisi sızıntısı / API key (3rd party) sızıntısı | Containment 2 saat, Kurul bildirim 24 saat |
| **Medium** | Audit log sızıntısı (PII içermeyen) / hata mesajı sızıntısı | Containment 1 gün, Kurul bildirim 72 saat |
| **Low** | Public bilgi sızıntısı (zaten açık endpoint hata) | Mitigasyon 1 hafta, bildirim opsiyonel |

---

## 6. Bildirim E-postası Şablonu (Kullanıcı)

```
Konu: KFinans — Önemli Güvenlik Bildirimi

Sayın {{user_name or "Kullanıcı"}},

{{ihlal_tarihi}} tarihinde KFinans sistemlerimizde bir güvenlik
olayı yaşandığını üzülerek bildiriyoruz. Olayı tespit ettiğimizde derhal
müdahale ettik ve şu anda altyapımız güvende.

**Etkilenen veriler:** {{etkilenen_veri_kategorileri}}
**Etkilenmediği teyit edilen veriler:** Şifreniz (bcrypt hash; plaintext
sızmamıştır); cüzdan adresleriniz (Fernet ile DB'de şifreli); exchange API
key'leriniz (Fernet ile DB'de şifreli).

**Sizden ricamız:**
- Şifrenizi değiştirin: https://kfinans.app/dashboard/settings
- Hesabınızı 2FA (TOTP) ile koruyun: https://kfinans.app/dashboard/settings
- Şüpheli bir aktivite gözlemlerseniz security@kfinans.app'e bildirin

KVKK Kurulu'na bu olayı KVKK m.12/5 uyarınca bildirdik. Tam olay raporu:
https://kfinans.app/legal/incidents/{{slug}}

Bu olay nedeniyle yaşadığınız endişe için özür dileriz.

Saygılarımızla,
KFinans Ekibi (Mayotek)
```

---

## 7. KVKK Kurul Bildirim Formu — Doldurma Şablonu

Form: `kvkk.gov.tr/Veri-Ihlali-Bildirim-Formu`. KEP ile gönderilir.

**1. Veri Sorumlusu Bilgileri**
- Tüzel ünvan: {{COMP-001'de doldurulacak}}
- KEP adresi: {{COMP-002'de açılacak}}
- VERBİS sicil no: {{KVKK kayıt sonrası}}
- Tebligat adresi: {{COMP-001}}

**2. Olay Bilgileri**
- Olay tarihi: {{YYYY-MM-DD HH:MM TR saati}}
- Tespit tarihi: {{tarih + saat}}
- Müdahale tarihi: {{tarih + saat}}
- Olay açıklaması: {{1-2 paragraf — saldırı vektörü, içerik}}

**3. Etkilenen Kişi Sayısı ve Veri Kategorileri**
- Doğrudan etkilenen kullanıcı sayısı: {{N}}
- Veri kategorileri: kimlik (e-posta), finansal (portföy değeri), tanımlayıcı
  (UUID), iletişim (e-posta)
- Hassas özel nitelikli veri var mı: HAYIR (KFinans sağlık/cinsel/biyometrik
  veri toplamaz)

**4. Olası Sonuçlar**
- Kullanıcının maddi/manevi zararı: {{değerlendirme}}
- Riski azaltacak teknik önlemler: Fernet şifreleme, bcrypt hash, JWT
  blacklist, audit log forensic.

**5. Alınan ve Alınacak Önlemler**
- Containment: {{ne yapıldı}}
- Eradication: {{ne yapıldı}}
- Kullanıcı bildirimi: {{tarih, kanal: e-posta + banner}}

---

## 8. Basın Açıklaması Taslağı (>100 kullanıcı etkilenmişse)

> **KFinans Güvenlik Bildirimi**
>
> KFinans, {{tarih}} itibarıyla yaşanan güvenlik olayını tespit etmiş ve
> derhal müdahale etmiştir. Etkilenen tüm kullanıcılarımıza ayrıntılı bilgi
> e-posta ile gönderilmiş; KVKK Kurulu'na yasal süre içinde bildirim
> yapılmıştır.
>
> Şifreniz, cüzdan adresleriniz ve exchange API key'leriniz veri tabanımızda
> şifreli saklandığından bu kategorilerdeki veriler korunmuştur.
>
> Detaylı şeffaflık raporu: https://kfinans.app/legal/incidents/{{slug}}

---

## 9. Yıllık Tatbikat Programı

**Ocak ayı, 2 saatlik table-top egzersiz:**
- Senaryo: simüle DB sızıntısı (örn. pg_dump leak)
- Katılımcılar: IC + Teknik Lead + KVKK İrtibat
- Çıktı: bu doc'taki süre hedefleri ne kadar gerçekçi? Hangi rol darboğaz?
- Aksiyon: tüm gap'ler GitHub issue açılır, Şubat sonuna kadar kapatılır.

**İlk tatbikat tarihi:** 2027-01 (production launch sonrası ilk yıl).

---

## 10. Bağlantılar

- KVKK Veri İhlali Bildirim Formu: https://www.kvkk.gov.tr/Icerik/5444/Veri-Ihlali-Bildirim-Formu
- KVKK Veri İhlali Bildirim Kararı: https://www.kvkk.gov.tr/Icerik/5331/Kisisel-Veri-Ihlali-Bildirim-Karari
- GDPR Art.33 (Notification of personal data breach): https://gdpr-info.eu/art-33-gdpr/
- ISO/IEC 27035-1:2023 Information security incident management
- KFinans audit_logs altyapısı: `docs/02-mimari.md` §5.2 audit_logs
- KFinans güvenlik politikası: `docs/07-guvenlik.md`
- Bekleyen yasal placeholder'lar: `project_kvkk_placeholders` (private memo)
