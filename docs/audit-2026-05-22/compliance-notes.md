# Compliance Audit Notları — 2026-05-22

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

**Bağlam:** 2026-05-21 büyük fix turu sonrası rc7 production'da. KVKK + GDPR + SPK uyumluluk durumu.
**Sahip ajan:** `compliance-expert`
**Kapsam:** Production hazırlık + KVKK placeholder + data lifecycle + üçüncü taraf aktarım.
**İlgili belgeler:** [08-uyumluluk-kvkk.md](../08-uyumluluk-kvkk.md), [legal/incident-response-plan.md](../legal/incident-response-plan.md), [production-deploy-checklist.md](../production-deploy-checklist.md)

---

## ✓ Mevcut Pozitif

| Bileşen | Durum | Kanıt |
|---------|-------|-------|
| Soft-delete + 30 gün hard-delete cron | Aktif | `_hard_delete_expired_users_job` günlük 04:00 Europe/Istanbul (COMP-004) |
| audit_logs 365 gün retention + purge cron | Aktif | `_purge_old_audit_logs_job` günlük 04:30 (COMP-022, KVKK m.7) |
| audit_logs.user_id ON DELETE SET NULL | Aktif | Forensic için kullanıcı silinse bile log anonim korunur |
| 18+ age_confirmed zorunlu | Aktif | `schemas/auth.py` register + 12 test |
| KVKK m.11 data-export endpoint | Aktif | `GET /api/v1/user/data-export` JSON, encrypted_key hariç (BACK-013 maskeleme aktif) |
| Anthropic özel açık rıza akışı | Aktif | `users.anthropic_consent_at` + `/user/anthropic-consent` POST/DELETE + `/advice/generate` 403 fallback |
| KVKK consent revoke endpoint | Aktif | `POST /user/consent/revoke` + audit log `kvkk.anthropic_consent_revoke` |
| Email change endpoint + rate limit | Aktif | 3/dk slowapi |
| Wallet xpub Fernet şifreleme | Aktif | FAZ C1 `address_encrypted` + `address_fingerprint` |
| JWT refresh rotation + blacklist cleanup | Aktif | FAZ C4 + C5 |
| 4 yasal sayfa yayında | Aktif | `/legal/{kvkk,privacy,terms,cookies}` (2026-05-02) |
| Incident response plan | Aktif | ISO 27035 esinli, KEP/KVKK Kurulu şablonları (COMP-021) |
| Yurt dışı aktarım rıza (Anthropic ABD) | Aktif | Register ayrı checkbox + privacy madde 5 |

---

## ⚠ Çelişki / Düzeltme Notları (öncelik sırasıyla)

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | **P0** | `legal/kvkk/page.tsx` 4 placeholder hâlâ açık: `[TİCARİ ÜNVAN]`, `[KEP_ADRESI]` (2x), `[TEBLİGAT_ADRESİ]` (sat 19-99) | Veri sorumlusu tanımsız → KVKK m.10 ihlali; KEP yoksa Kurul'a 72 saat bildirim yapılamaz | **Production blocker.** Mayotek ticari unvan netleşmeden public launch yapılmamalı; KEP başvurusu PTT'den ~3 iş günü |
| 2 | **P0** | `legal/terms/page.tsx` satır 103 `[İSTANBUL/MERKEZ]` yetkili mahkeme placeholder | Uyuşmazlık halinde yetkili mahkeme tanımsız → sözleşme şartı geçersiz sayılabilir | Mayotek vergi dairesi merkezine göre doldur (büyük olasılıkla İstanbul) |
| 3 | **P0** | `privacy@kfinans.app`, `kvkk@kfinans.app`, `security@kfinans.app` mailbox'ları kurulmadı | KVKK m.11 başvuruları + ihlal raporları ulaşılamaz; SECURITY.md zafiyet bildirimi kanalsız | Cloudflare Email Routing veya Zoho Mail (ücretsiz tier) ile 3 alias kur; SPF/DKIM/DMARC zorunlu |
| 4 | **P0** | VERBİS kayıt durumu belirsiz — KVKK m.16 eşiği altıyız ama "ana faaliyet finansal veri" yorumu Kurul yorumuna açık | Kurul denetiminde "kayıt yapmadın" cezası riski | Kullanıcı sayısı 100'ü geçince proaktif gönüllü VERBİS kayıt başlat |
| 5 | **P1** | Cookie consent banner UI yok; `/legal/cookies` dokümante ama sadece `access_token` zorunlu çerez var | Şu an analytics yok → GDPR/ePrivacy ihlali yok; analytics eklenirse 1 gün içinde banner şart | Faz I'da Plausible (cookieless) tercih et; eklenirse `cookie-banner` component'i hazırla (TR+EN dictionary kapsamlı) |
| 6 | **P1** | DPA (Data Processing Agreement) Anthropic + Resend + Hetzner Cloud ile imzalanmadı | Kurul denetiminde "yurt dışı aktarımın yasal zemini" sorulduğunda sadece açık rıza var; SCC eksik | Anthropic DPA self-serve form mevcut; Resend DPA email talep; Hetzner Cloud DPA (AVV/GDPR) console'dan indirilir — 1 hafta iş |
| 7 | **P1** | GDPR Art.33 72 saat bildirim → incident-response-plan §4 `T+2-72 saat` akışı yazılmış AMA AB veri koruma otoritesi (LSA) belirlenmedi | AB kullanıcısı olduğunda hangi otorite? Şu an AB hedefi yok → düşük risk | AB launch öncesi Irish DPC ya da AB temsilcisi (Art.27) atanmalı |
| 8 | **P1** | `revoke_anthropic_consent` audit log atıyor ama mevcut sohbet geçmişi (`advice_history`) silinmiyor — rıza geri çekildiğinde tarihi tavsiye verileri DB'de kalır | KVKK m.7/2 "rızanın geri çekilmesi → veri silinmesi" yorumuna aykırı | `revoke_anthropic_consent` içinde `DELETE FROM advice_history WHERE user_id = current_user.id` ekle veya kullanıcıya 2 seçenek sun (rıza+veri silme / sadece rıza geri çek) |
| 9 | **P2** | SPK uyarı banner'ı `/advice` sayfasında sticky değil — kullanıcı scroll edince kaybolur | SPK m.35 "bağlayıcı yatırım tavsiyesi değil" ifadesi sürekli görünür olmalı | `_ensure_disclaimer` zaten footer'a ekliyor; ek olarak frontend'de `position: sticky` üst banner |
| 10 | **P2** | `users.anthropic_consent_at` timezone-aware ama gizlilik politikası madde 4.2 "rızanızı her an geri çekebilirsiniz" — UI'da revoke butonu hangi sayfada? Settings sayfasında var mı doğrulanmadı | Kullanıcı revoke yapamazsa KVKK m.11/1.e ihlali | `/dashboard/settings` sayfasında "AI tavsiye rızasını geri çek" butonu olduğunu manuel verifikasyon |
| 11 | **P2** | İncident response plan §2 "yedek süreç eklenmesi Faz I item" — tek kişilik takım, IC 4 saat ulaşılamazsa kim? | Severity Critical durumda 30dk containment hedefi tutmaz | Hukuk danışmanı / dış SOC sözleşmesi (en azından ad-hoc) Faz I'a çek |
| 12 | **P2** | `data-export` endpoint Excel format vermiyor — kullanıcı tercih hatırlatması (PDF + Excel her zaman iki format) | Kullanıcı feedback'i "raporlar her zaman iki formatta" — KVKK m.11/1.b "taşınabilirlik" JSON yeterli ama tutarsızlık | `GET /user/data-export?format=xlsx` ekle (1 sprint) |
| 13 | **P3** | Resend (e-posta servisi) ABD merkezli — privacy.tsx Anthropic'i anıyor ama Resend yurt dışı aktarımı vurgulanmamış olabilir | Kullanıcı verify mail için ABD aktarımdan haberdar olmayabilir | Privacy madde 5.1 tablosuna Resend (ABD, e-posta adresi) satırı eklendi mi kontrol et |
| 14 | **P3** | TTK m.82 10 yıl ticari defter saklama → `credit_transactions` saklama süresi 10 yıl ama users CASCADE delete varsa credit_transactions da silinir mi? | Hard-delete cron çalıştığında TTK ihlali olasılığı | Migration ile `credit_transactions.user_id` ON DELETE SET NULL'a çek + `legacy_email_hash` kolonu ekle (anonim ama yasal arşiv) |

---

## Best Practice / Reusability / Portability

### KVKK metinlerinin reusability (multi-tenant SaaS template)
Mevcut 4 sayfa Mayotek-spesifik hard-coded. Faz 3'te SaaS multi-tenant model gelirse her tenant kendi unvan/KEP/adresini doldurmak isteyecek. **Öneri:** `frontend/app/legal/_data/legal-config.ts` ile `{ tradeName, kepAddress, postalAddress, court }` central config; sayfalar interpolation kullansın. Şu anki placeholder'lar zaten string match — refactor 2 saat. Çıkış: aynı template'i `mayotek-other-product` veya white-label müşteri için yeniden kullanabilir.

### GDPR Art.33 72 saat bildirim → incident-response-plan uyum
`legal/incident-response-plan.md §4` "T+2-72 saat Recovery + Bildirim" akışı GDPR Art.33 ile **uyumlu** — KVKK m.12/5 "gecikmeksizin" daha sıkı (KVKK Kurul yorumu 72 saatten kısa, "ihlal tespitinden 72 saat içinde" pratiği yerleşik). Plan **iki rejime de hizmet ediyor**. Eksik: §2 "AB kullanıcısı varsa LSA bildirim" satırı genel; Irish DPC veya Hollanda AP gibi spesifik otorite Faz 4 international launch'ta seçilmeli.

### Cookie consent banner durumu
**Doküman:** `/legal/cookies` sayfası mevcut, sadece zorunlu `access_token` çerezi sayıyor.
**UI:** Banner component **YOK** (grep'le `CookieBanner|cookie-consent` 0 sonuç).
**Risk düşük:** Şu an sadece zorunlu çerez var → ePrivacy Directive m.5/3 "strictly necessary" istisnası geçerli, banner gerekmiyor.
**Tetikleyici:** Plausible/GA/Sentry browser SDK eklendiği gün banner şart. Foundation hazır olsun: `app/_components/CookieBanner.tsx` skeleton (tümünü kabul / sadece zorunlu / tercihleri yönet — 3 buton; GDPR uyumlu kapatmak da kabul kadar kolay olmalı).

### Reusable consent infrastructure
Anthropic consent için `users.anthropic_consent_at` + audit log pattern mevcut. **Generalize et:** `user_consents` tablosu (`user_id`, `consent_type`, `granted_at`, `revoked_at`, `ip_address`, `user_agent`) — marketing, analytics, cookies, AI provider'lar için aynı altyapı. Faz 4'te yeni rıza her geldiğinde migration yerine row insert. Audit trail bonusta var.

### Portability — KVKK'dan GDPR'a köprü
Mevcut data-export JSON format'ı KVKK m.11 ve GDPR Art.20 (right to data portability) ortak gereksinimleri karşılıyor. Format adı `kfinans-data-export-v1` versiyonlu — schema değişirse v2 backward-compat. **Bonus:** "machine-readable, structured" GDPR şartı sağlanıyor; CSV ya da Excel ek format eklemek opsiyonel.

---

## Production Blocker Özet

P0 maddeler 1-4 birlikte **rc7 → public launch** önünde son engel. Sıra:
1. Mayotek ticari unvan + adres dolduğu an `legal/kvkk` + `legal/terms` placeholder replace
2. PTT KEP başvurusu (3 iş günü)
3. Cloudflare Email Routing ile 3 alias (`privacy@`, `kvkk@`, `security@`)
4. VERBİS gönüllü kayıt (opsiyonel ama tavsiye edilir)

Bu 4 madde tamamlanmadan rc7 sadece "private beta" konumunda olabilir — kayıt formunda "beta — Mayotek hesabı dışı kullanım için iletişime geçin" notu ekleyerek hukuki riski azaltabiliriz.
