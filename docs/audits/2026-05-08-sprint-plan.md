# Sprint Plan — FAZ G Audit Sonrası (2026-05-08)

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

> 11 uzman ajan paralel sistem analizinden çıkan **240 bulgu** önceliklendirildi.
> 63 critical+high GitHub Issue olarak açıldı; 175 medium+low [`audit-2026-05-08-summary.md`](./audit-2026-05-08-summary.md) içinde.

## Özet İstatistik

| Seviye | Sayı | Yer | Durum |
|--------|------|-----|-------|
| 🔴 Critical | 17 | GitHub Issues #3-#19 | Açık |
| 🟠 High | 46 | GitHub Issues #20-#65 | Açık |
| 🟡 Medium | 98 | `audit-2026-05-08-summary.md` | Backlog |
| 🟢 Low/Info | 77 | `audit-2026-05-08-summary.md` | Backlog |
| **Toplam** | **240** | | |

> Not: GitHub flag (Ticket #4360519) kalkıncaya kadar issue'lar anonim ziyaretçi için görünmez. Sürdürücü `gh issue list` ile her zaman erişebilir.

---

## P0 — Production Blocker (Faz D1 öncesi şart)

Bu maddeler **production deploy'dan ÖNCE** kapatılmalı. Tahmini süre: **2-3 gün**.

### Kod Düzeyi (1 saat içinde fix)
| Issue | Başlık | Süre |
|-------|--------|------|
| [#3](https://github.com/celikada/KFinans/issues/3) | BACK-007: manual_crypto.py logger NameError 500 | 5 dk |
| [#4](https://github.com/celikada/KFinans/issues/4) | FE-001: getToken() 19 yerde undefined | 30 dk |
| [#5](https://github.com/celikada/KFinans/issues/5) | TEST-009: release.yml @smoke 0 senaryo | 15 dk |

### Altyapı (1 gün)
| Issue | Başlık | Süre |
|-------|--------|------|
| [#6](https://github.com/celikada/KFinans/issues/6) | DEVOPS-009: Postgres backup cron yok | 4 saat |
| [#14](https://github.com/celikada/KFinans/issues/14) | DEVOPS-001: K8s :latest tag | 2 saat |
| [#15](https://github.com/celikada/KFinans/issues/15) | DEVOPS-002: Backend root user | 1 saat |
| [#50](https://github.com/celikada/KFinans/issues/50) | DEVOPS-018: ConfigMap CORS misconfig | 30 dk |

### Yasal (sizin yapacağınız)
| Issue | Başlık | Süre |
|-------|--------|------|
| [#11](https://github.com/celikada/KFinans/issues/11) | COMP-001: KVKK Aydınlatma placeholder doldur | 2 saat |
| [#12](https://github.com/celikada/KFinans/issues/12) | COMP-002: kvkk@ + privacy@ mailbox kur | 1 saat |
| [#13](https://github.com/celikada/KFinans/issues/13) | COMP-005: DPA imzaları (Anthropic+Resend+Hetzner) | 1-2 hafta |

### Doc Güncellemesi (3-4 saat)
| Issue | Başlık | Süre |
|-------|--------|------|
| [#16](https://github.com/celikada/KFinans/issues/16) | DOC-001: CLAUDE.md sayım drift | 30 dk |
| [#17](https://github.com/celikada/KFinans/issues/17) | DOC-002: Router listesi 5 router eksik | 30 dk |
| [#18](https://github.com/celikada/KFinans/issues/18) | DOC-003: API ref 7 endpoint grubu eksik | 2-3 saat |

---

## P1 — Production Ready (1-2 hafta sonra)

48 high issue (#20-#65) — sprint 1+2'ye dağıtılacak.

### Sprint 1 (1 hafta) — Güvenlik + Compliance
- **SEC-001 → #27** Password reset endpoint
- **SEC-002 → #28** Brute-force koruması (account lockout)
- **SEC-004 → #30** X-Forwarded-For spoofing fix
- **AI-005 → #9** Anthropic açık rıza akışı
- **AI-008 → #10** SPK disclaimer (system prompt + post-process)
- **COMP-003 → #38** Veri taşınabilirliği endpoint
- **COMP-004 → #39** 30g hard-delete cron
- **COMP-009 → #41** SPK uyarısı UI
- **COMP-010 → #42** 18+ yaş checkbox

### Sprint 2 (1 hafta) — Mimari + Backend
- **ARC-006 → #22** Genel exception handler
- **ARC-001 → #20** Service → API import fix
- **BACK-008 → #25** Generic exception handler
- **BACK-013 → #26** Wallet xpub response truncation
- **DBA-001 → #31** FK ondelete CASCADE migration
- **DBA-004 → #33** Connection pool config

---

## P2 — Sprint 3+ (Production sonrası)

98 medium issue. Detay için `audit-2026-05-08-summary.md`.

Tema bazlı gruplar:
- **Event-driven taşıma** (ARC-007, ARC-003): Snapshot/audit/AI tavsiye fire-and-forget pattern → Celery+Redis
- **Observability** (DEVOPS-023, 024, 025): Loki + Prometheus + Sentry
- **Test coverage** (TEST-001, 011, 015): 18 servis modülü için unit test, paralel execution
- **Frontend modernization** (FE-006, 008, 014): React Query + dark mode + storage event sync
- **DB optimizasyon** (DBA-002, 010, 016): Index sırası + email partial unique + snapshot upsert race
- **Decimal precision** (FIN-018, 022): Numeric(28, 10) + JSON string serialization

---

## P3 — Backlog (77 low/info)

Kozmetik, opsiyonel iyileştirmeler. `audit-2026-05-08-summary.md` içinde.

---

## İlerleme Takibi

```bash
# Açık critical issue sayısı
gh issue list --repo celikada/KFinans --label "priority:critical" --state open

# P0 ilerlemesi
gh issue list --repo celikada/KFinans --label "audit:2026-05-08" --label "priority:critical" --state closed

# Sprint 1 ilerlemesi
gh issue list --repo celikada/KFinans --label "audit:2026-05-08" --label "priority:high" --state closed
```

---

## Teslim Kriterleri (P0 Bitince)

- [ ] 17 critical issue **closed**
- [ ] CI'da `npm run typecheck` step'i (FE-001 düzeltmesi)
- [ ] Backup CronJob deployed + 1 başarılı restore drill
- [ ] K3s manifest'leri semver-tagged image kullanıyor
- [ ] Backend non-root user (CIS Docker Benchmark 4.1 ✓)
- [ ] KVKK Aydınlatma Metni'nde Mayotek tüzel bilgileri canlı
- [ ] DPA'lar imzalı (`docs/legal/dpa/`)
- [ ] Mailbox `kvkk@kfinans.app` + `privacy@kfinans.app` aktif
- [ ] `docs/01-tasarim`, `docs/03-api-ref`, `CLAUDE.md` senkron

**Tarih hedefi:** GitHub flag çözüldüğü gün + 3 iş günü.
