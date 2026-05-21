# FAZ G — Sistem Audit Bulgu Özeti (2026-05-08)

> 11 uzman ajan paralel sistem analizi — 240 bulgu
>
> **Kritik+High** GitHub Issue olarak açıldı (#3-#65). Bu doküman **medium+low** bulguların kompakt özetini içerir.
>
> İlgili: [`sprint-plan.md`](./sprint-plan.md)

---

## G1 — Mimari (architect, 11 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| ARC-001 | high | [#20](https://github.com/celikada/KFinans/issues/20) | services/snapshot.py:304 API katmanını import ediyor |
| ARC-003 | high | [#21](https://github.com/celikada/KFinans/issues/21) | Snapshot job sıralı for loop |
| ARC-006 | high | [#22](https://github.com/celikada/KFinans/issues/22) | Genel exception handler eksik |
| ARC-011 | high | [#23](https://github.com/celikada/KFinans/issues/23) | Scheduler global instance — multi-replica güvensiz |

### Backlog (medium/low — issue açılmadı)
- **ARC-002 (medium):** services/snapshot.py 624 satır god module → Collector pattern, app/services/snapshot/ klasörü
- **ARC-004 (medium):** In-memory cache'ler horizontal scaling'de tutarsız → Redis
- **ARC-005 (medium):** aggregator.py 4 sorumluluk yüklü → fx.py, pricing.py, portfolio_analytics.py'ya böl
- **ARC-007 (medium):** Audit log + snapshot tetikleme + AI tavsiye event-driven olmalı (BackgroundTasks → Celery)
- **ARC-008 (low):** Polkadot to_thread thread pool sınırı → httpx async direkt
- **ARC-009 (low):** DI tutarsızlığı — service'ler global instance + dataclass karışımı
- **ARC-010 (low):** snapshot.py'de fonksiyon-içi lazy import (gereksiz)

---

## G2 — Backend (backend-expert, 18 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| BACK-007 | critical | [#3](https://github.com/celikada/KFinans/issues/3) | manual_crypto.py logger NameError |
| BACK-001 | high | [#24](https://github.com/celikada/KFinans/issues/24) | snapshot endpoint response_model eksik |
| BACK-008 | high | [#25](https://github.com/celikada/KFinans/issues/25) | Generic exception handler |
| BACK-013 | high | [#26](https://github.com/celikada/KFinans/issues/26) | Wallet xpub plaintext response |

### Backlog
- **BACK-002 (medium):** /audit-logs router'da inline Pydantic model — schemas/'a taşı
- **BACK-003 (low):** class Config Pydantic v1 stili 4 schema'da — model_config = ConfigDict
- **BACK-004 (medium):** model_post_init validation → field_validator/Literal kullan
- **BACK-005 (medium):** Global cache'ler async-lock yok → single-flight pattern
- **BACK-006 (medium):** auth.logout `except Exception:` çıplak yakalama → IntegrityError
- **BACK-009 (low):** MKK Excel import log seviyesi tutarsız
- **BACK-010 (medium):** wallets.py is_active filtre tutarsız — soft-delete vs hard-delete kararı
- **BACK-012 (low):** asset_catalog handler dispatcher awaitable test brittle
- **BACK-014 (low):** sessiz `except Exception: return 0, 0` blokları — log warning ekle
- **BACK-015 (low):** delete endpoint audit log + commit sırası riski (best-effort tradeoff)
- **BACK-016 (medium):** wallets/sync + integrations/sync placeholder 202 — kaldır veya BackgroundTask
- **BACK-017 (low):** decode_token KeyError defensive check eksik
- **BACK-018 (low):** _oauth2 duplicate (auth.py + deps.py) — tek instance

---

## G3 — Güvenlik (security-expert, 24 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| SEC-001 | high | [#27](https://github.com/celikada/KFinans/issues/27) | Password reset endpoint yok |
| SEC-002 | high | [#28](https://github.com/celikada/KFinans/issues/28) | Brute-force koruması zayıf |
| SEC-003 | high | [#29](https://github.com/celikada/KFinans/issues/29) | Multi-replica rate limit baypası |
| SEC-004 | high | [#30](https://github.com/celikada/KFinans/issues/30) | X-Forwarded-For spoofing |

### Backlog (medium ağırlıklı)
- **SEC-005 (medium):** JWT secret rotation prosedürü dokümante değil
- **SEC-006 (medium):** Settings boş string default'ları — prod'da fail-closed olmalı
- **SEC-007 (medium):** Stack trace/DB hata mesajı client'a leak (7 yerde `detail=str(e)`)
- **SEC-008 (medium):** CSRF koruması yok — cookie + localStorage dual storage
- **SEC-009 (medium):** File upload — magic-byte/MIME doğrulaması yok, boyut limiti yok (8 endpoint)
- **SEC-010 (low):** SSRF zayıflığı yok ama RPC URL whitelist eksik (Faz 4)
- **SEC-011 (medium):** Backend Dockerfile root user (DEVOPS-002 ile birleşik)
- **SEC-012 (medium):** Dependency pinning yok — pyproject.toml `>=` aralıkları, lock file yok
- **SEC-013 (low):** Audit log immutability garantisi yok — DELETE permission DB'de
- **SEC-014 (low):** Audit log retention policy yok — sonsuz büyür
- **SEC-015 (medium):** Audit `extra` JSONB PII over-logging (auth.login_failed email)
- **SEC-016 (medium):** Cookie HttpOnly + Secure flag yok
- **SEC-017 (low):** Refresh token rotation race window — RFC 6819 reuse detection eksik
- **SEC-018 (low):** Pydantic model_post_init ValueError 500 dönüyor (BACK-004 ile)
- **SEC-019 (low):** verify-email timing-safe değil — secrets.compare_digest
- **SEC-020 (medium):** /portfolio/snapshot POST flood koruması yok — 8 import endpoint için rate limit
- **SEC-021 (medium):** DB connection SSL/TLS yok (asyncpg sslmode=prefer)
- **SEC-022 (low):** cors_origins dev default localhost — prod'da fail-closed olmalı
- **SEC-023 (low):** verify_token üzerinde index yok
- **SEC-024 (low):** Frontend CSP unsafe-inline — nonce stratejisi yok

---

## G4 — Database (dba, 24 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| DBA-020 | critical | [#6](https://github.com/celikada/KFinans/issues/6) | Postgres backup yok (= DEVOPS-009) |
| DBA-001 | high | [#31](https://github.com/celikada/KFinans/issues/31) | 5 FK ondelete CASCADE eksik |
| DBA-003 | high | [#32](https://github.com/celikada/KFinans/issues/32) | Faz C migration downgrade test'siz |
| DBA-004 | high | [#33](https://github.com/celikada/KFinans/issues/33) | Connection pool default — bottleneck |

### Backlog
- **DBA-002 (medium):** snapshot_date DESC index sırası optimal değil — re-create with DESC
- **DBA-005 (low):** audit_logs.extra GIN index yok (Faz 3'te gerekirse)
- **DBA-006 (low):** PK Integer vs UUID tutarsızlık — SaaS için UUID standart
- **DBA-007 (low):** Expense/Income partial index yok (date + is_paid)
- **DBA-008 (low):** Numeric(28,12) vs (28,8) tutarsız — manual_crypto hizala
- **DBA-009 (low):** Pricing precision tutarsız — Numeric(20,10) hizala
- **DBA-010 (medium):** users.email unique soft-delete'li — partial unique index gerekli
- **DBA-011 (low):** revoked_tokens.expires_at BRIN index (Faz 3 büyük volume)
- **DBA-012 (low):** is_active partial index yok (Faz 3)
- **DBA-013 (medium):** incomes.recurring_income_id unique date-bazlı, ay bazlı olmalı
- **DBA-014 (low):** address_fingerprint duplicate index (uq + ix) — birini düşür
- **DBA-015 (low):** audit_logs.user_agent VARCHAR(512) truncation server-side yok
- **DBA-016 (medium):** Snapshot UPSERT — ON CONFLICT DO UPDATE race condition
- **DBA-017 (low):** Decimal ↔ asyncpg ↔ JSON serialization v2 davranışı kontrol
- **DBA-018 (medium):** CONCURRENTLY index oluşturma kullanılmıyor
- **DBA-019 (low):** commodity_holdings vs Expense/Income vs Wallet — CHECK constraint'leri yok
- **DBA-021 (medium):** Single-instance Postgres SPOF — read replica yok (Faz 3 SaaS)
- **DBA-022 (low):** address_encrypted normalize edilmiyor (encrypt öncesi lower())
- **DBA-023 (low):** updated_at onupdate eksik (CreditCard, CashHolding, ManualCrypto)
- **DBA-024 (low):** Date kolonları timezone-aware değil — sözleşme dokümante edilsin

---

## G5 — Frontend (frontend-expert, 23 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| FE-001 | critical | [#4](https://github.com/celikada/KFinans/issues/4) | getToken() 19 yerde undefined |
| FE-002 | high | [#34](https://github.com/celikada/KFinans/issues/34) | recharts type tanımı eksik |
| FE-003 | high | [#35](https://github.com/celikada/KFinans/issues/35) | dashboard/page.tsx 913 satır |
| FE-004 | high | [#36](https://github.com/celikada/KFinans/issues/36) | 14 paralel fetch orchestration yok |
| FE-005 | high | [#37](https://github.com/celikada/KFinans/issues/37) | 16 sayfada auth check boilerplate |

### Backlog (medium ağırlıklı)
- **FE-006 (medium):** Auth state localStorage + cookie + state — sync edilmiyor (storage event listener yok)
- **FE-007 (medium):** CSP connect-src localhost dev URL'i içermiyor — dev mod fetch broken
- **FE-008 (medium):** recharts dynamic import yok — chart sayfalarında bundle ağır
- **FE-009 (low):** next/image kullanılmıyor (public PNG'ler dead asset)
- **FE-010 (medium):** useEffect exhaustive-deps eslint disable 5 sayfada (stale closure riski)
- **FE-011 (low):** INPUT_CLS / TOOLBAR_BTN_CLS / CARD_CLS 3 dosyada duplicate (BES yeşil farklı)
- **FE-012 (medium):** A11y — placeholder label değil, aria-label eksik, htmlFor association eksik
- **FE-013 (medium):** confirm() native — bloke edici, A11y zayıf, i18n yok
- **FE-014 (medium):** Vitest coverage threshold %30 — component testleri yetersiz
- **FE-015 (medium):** parseFloat() NaN guard yok — backend null/empty dönerse "NaN ₺"
- **FE-016 (low):** Excel/PDF download fonksiyonları 7 kez kopyalanmış (DRY ihlali)
- **FE-017 (medium):** proxy.ts redirect loop riski — cookie kabul edilmezse infinite loop
- **FE-018 (low):** Dashboard ana header custom, alt sayfalar PageHeader — tutarsız
- **FE-019 (low):** Server Actions kullanılmadı — form submit'lerde useFormStatus
- **FE-020 (low):** Dark mode hazırlığı yok
- **FE-021 (low):** asset_type union narrowing yok — DTO Literal type
- **FE-022 (low):** Logos.tsx xl size text-4xl orantısız (görsel kontrol)
- **FE-023 (low):** useUsdRate Context yerine her TLValue'da hook → 20 paralel fetch riski

---

## G6 — AI/Claude (ai-expert, 14 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| AI-003 | critical | [#7](https://github.com/celikada/KFinans/issues/7) | System prompt < 1024 token cache yok |
| AI-005 | critical | [#9](https://github.com/celikada/KFinans/issues/9) | KVKK açık rıza akışı yok |
| AI-008 | critical | [#10](https://github.com/celikada/KFinans/issues/10) | SPK disclaimer eksik |
| AI-001 | high | [#38](https://github.com/celikada/KFinans/issues/38) | Anthropic exception handler |
| AI-002 | high | [#39](https://github.com/celikada/KFinans/issues/39) | Cache hit oranı izlenmiyor |
| AI-004 | high | [#40](https://github.com/celikada/KFinans/issues/40) | Audit log entegrasyonu eksik |
| AI-007 | high | [#41](https://github.com/celikada/KFinans/issues/41) | Kredi tüketim mantığı yok |

### Backlog
- **AI-006 (medium):** Prompt versiyonlama yok — investment_advice.prompt_version migration
- **AI-009 (high — issue açılmadı):** LLM hesap yapıyor — rakam halüsinasyon (yüzde aralığı kullan, spesifik TL üretme)
- **AI-010 (medium):** Streaming yanıt yok — Faz 4 SSE
- **AI-011 (low):** Model snapshot ID değil alias — prod reproducibility
- **AI-012 (low):** User prompt cache breakpoint kullanılmamış (düşük ROI)
- **AI-013 (medium):** Hata yolu testi yok (timeout/rate_limit/overloaded)
- **AI-014 (low):** AsyncAnthropic her çağrıda yeni instance — singleton

---

## G7 — Compliance (compliance-expert, 30 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| COMP-001 | critical | [#11](https://github.com/celikada/KFinans/issues/11) | KVKK Aydınlatma placeholder |
| COMP-002 | critical | [#12](https://github.com/celikada/KFinans/issues/12) | kvkk@ + privacy@ mailbox yok |
| COMP-005 | critical | [#13](https://github.com/celikada/KFinans/issues/13) | DPA imzaları yok |
| COMP-009 | critical | [#10](https://github.com/celikada/KFinans/issues/10) | SPK disclaimer (= AI-008) |
| COMP-003 | high | [#43](https://github.com/celikada/KFinans/issues/43) | Veri taşınabilirliği endpoint |
| COMP-004 | high | [#44](https://github.com/celikada/KFinans/issues/44) | 30g hard-delete cron |
| COMP-006 | high | [#45](https://github.com/celikada/KFinans/issues/45) | Açık rıza geri çekme akışı |
| COMP-010 | high | [#47](https://github.com/celikada/KFinans/issues/47) | 18+ yaş doğrulama |
| COMP-021 | high | [#49](https://github.com/celikada/KFinans/issues/49) | İhlal müdahale planı operasyonel değil |
| COMP-024 | high | [#48](https://github.com/celikada/KFinans/issues/48) | Wallet xpub Excel export plaintext |
| COMP-029 | high | [#46](https://github.com/celikada/KFinans/issues/46) | Email değiştirme endpoint |

### Backlog
- **COMP-007 (medium):** Audit log retention süresi tanımsız — 24 ay TTL cron
- **COMP-008 (medium):** Audit extra PII over-logging — email mask helper
- **COMP-011 (medium):** Cookie consent banner yok (analytics eklenirse)
- **COMP-012 (medium):** Frontend CSP unsafe-inline — nonce middleware
- **COMP-013 (medium):** Wallet adresleri dış servis log'larında plaintext
- **COMP-014 (low):** Audit log immutability — REVOKE DELETE permission
- **COMP-015 (medium):** Brute force per-email rate limit + captcha
- **COMP-016 (low):** Email enumeration login farklı mesaj
- **COMP-017 (low):** PCI-DSS scope DIŞI ✅ — last_4 saklamada uyumlu
- **COMP-018 (info):** MASAK kapsam DIŞI ✅ — sadece bakiye okuma
- **COMP-019 (medium):** Mesafeli Sözleşme Faz 3 öncesi şart — TKHK m.48 14g cayma
- **COMP-020 (low):** VERBİS yıllık eşik kontrolü süreci
- **COMP-022 (low):** AI itiraz hakkı (KVKK m.11/g) endpoint
- **COMP-023 (low):** Şifre politikası asgari — HIBP top-1000 + zxcvbn
- **COMP-025 (medium):** wallet/import audit log eksik
- **COMP-026 (low):** Anthropic anonim portföy özet — top_assets symbol kuasi-identifier
- **COMP-027 (info):** GDPR DPO Faz 4 öncesi bütçe
- **COMP-028 (low):** Resend SPF/DKIM/DMARC kayıtları
- **COMP-030 (low):** Hesap silme uyarı modal — şeffaflık

---

## G8 — DevOps (devops, 30 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| DEVOPS-009 | critical | [#6](https://github.com/celikada/KFinans/issues/6) | Postgres backup yok |
| DEVOPS-001 | critical | [#14](https://github.com/celikada/KFinans/issues/14) | K8s :latest tag |
| DEVOPS-002 | critical | [#15](https://github.com/celikada/KFinans/issues/15) | Backend root user |
| DEVOPS-003 | high | [#51](https://github.com/celikada/KFinans/issues/51) | Pod Security Standards |
| DEVOPS-004 | high | [#52](https://github.com/celikada/KFinans/issues/52) | apply + set image race |
| DEVOPS-005 | high | [#53](https://github.com/celikada/KFinans/issues/53) | Otomatik rollback yok |
| DEVOPS-008 | high | [#54](https://github.com/celikada/KFinans/issues/54) | NetworkPolicy yok |
| DEVOPS-017 | high | [#55](https://github.com/celikada/KFinans/issues/55) | etcd encryption-at-rest yok |
| DEVOPS-018 | high | [#50](https://github.com/celikada/KFinans/issues/50) | ConfigMap CORS misconfig |
| DEVOPS-027 | high | [#56](https://github.com/celikada/KFinans/issues/56) | Postgres StorageClass |

### Backlog
- **DEVOPS-006 (medium):** HPA yok — backend min=2 max=4
- **DEVOPS-007 (medium):** PodDisruptionBudget yok — minAvailable: 1
- **DEVOPS-010 (low):** Frontend Dockerfile dev-deps stage karışık
- **DEVOPS-011 (medium):** pip cache key pyproject.toml — lock file yok (uv lock)
- **DEVOPS-012 (low):** Path filter 6 workflow'da tutarsız (e2e, sonar, security)
- **DEVOPS-013 (medium):** Sonar quality gate skipped warning yok — production unutulur
- **DEVOPS-014 (info):** Secret with vs env mix — best practice doğru
- **DEVOPS-015 (info):** Concurrency cancel-in-progress: false ✓
- **DEVOPS-016 (info):** packages: write scope ✓
- **DEVOPS-019 (medium):** ACCESS_TOKEN_EXPIRE_MINUTES=480 prod'da; CLAUDE.md 30 dk diyor
- **DEVOPS-020 (medium):** Postgres memory 1Gi düşük — 2Gi
- **DEVOPS-021 (low):** Frontend liveness probe / — /api/health endpoint
- **DEVOPS-022 (low):** Failed release image GHCR retention policy
- **DEVOPS-023 (medium):** Logs centralization yok — Loki + Promtail
- **DEVOPS-024 (medium):** Prometheus metrics endpoint yok
- **DEVOPS-025 (medium):** Sentry/error tracking yok
- **DEVOPS-026 (info):** Dev parity Tilt/Skaffold (memory tech debt)
- **DEVOPS-028 (low):** CodeQL JS autobuild Next.js 16 — build-mode: none
- **DEVOPS-029 (info):** Multi-arch image (linux/amd64,linux/arm64) — Faz 4
- **DEVOPS-030 (low):** Test secret üretimi DRY — composite action

---

## G9 — Testing (test-expert, 17 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| TEST-001 | critical | [#7](https://github.com/celikada/KFinans/issues/7) | 18 servis modülü unit test'siz |
| TEST-009 | critical | [#5](https://github.com/celikada/KFinans/issues/5) | release.yml @smoke 0 senaryo |
| TEST-011 | critical | [#19](https://github.com/celikada/KFinans/issues/19) | stocks/tefas/credit_cards test yok |
| TEST-002 | high | [#52](https://github.com/celikada/KFinans/issues/52) | _make_user 18 yerde copy-paste |
| TEST-004 | high | [#53](https://github.com/celikada/KFinans/issues/53) | DB izolasyon yok |
| TEST-005 | high | [#54](https://github.com/celikada/KFinans/issues/54) | Negative path testleri |
| TEST-007 | high | [#55](https://github.com/celikada/KFinans/issues/55) | Coverage gate %50 düşük |
| TEST-008 | high | [#56](https://github.com/celikada/KFinans/issues/56) | E2E coverage dar |
| TEST-016 | high | [#57](https://github.com/celikada/KFinans/issues/57) | services/email.py test'siz |

### Backlog
- **TEST-003 (medium):** Test e-postaları hardcoded — faker/uuid
- **TEST-006 (medium):** Mock fabrikaları yok — factory_boy/Pydantic
- **TEST-010 (medium):** services/audit.py log_audit unit test
- **TEST-012 (low):** respx context vs decorator mix — tek pattern
- **TEST-013 (medium):** Performance/load testing yok — Locust/k6
- **TEST-014 (low):** Mutation testing — mutmut/cosmic-ray
- **TEST-015 (medium):** pytest-xdist paralel — TEST-002/003/004 öncesi
- **TEST-017 (low):** Test sayısı / süre regression detection

---

## G10 — Finance (finance-expert, 25 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| FIN-005 | high | [#58](https://github.com/celikada/KFinans/issues/58) | Pricing fail → 0 TL silent loss |
| FIN-007 | high | [#59](https://github.com/celikada/KFinans/issues/59) | EUR/GBP cash → TRY tek USD/TRY |
| FIN-018 | high | [#60](https://github.com/celikada/KFinans/issues/60) | Numeric(18,4) mikro fiyatlar 0 |
| FIN-004 | high | [#61](https://github.com/celikada/KFinans/issues/61) | Yahoo stale price kontrolü yok |

### Backlog (medium ağırlıklı)
- **FIN-001 (medium):** Snapshot total vs pozisyon toplam yuvarlama farkı
- **FIN-002 (low):** weight_pct Numeric(5,2) overflow + sıfır portföy 0%
- **FIN-003 (medium):** TEFAS hafta sonu fiyat — tarih bazlı `max(date)` seç
- **FIN-006 (medium):** CoinGecko ilk eşleşme — market_cap_rank kullan
- **FIN-008 (low):** Stock GBp dönüşüm currency whitelist
- **FIN-009 (low):** BES 4 metric tek unit_price_tl'de eziyor — JSONB extra
- **FIN-010 (medium):** calculate_changes index varsayımı — tarih bazlı seç
- **FIN-011 (medium):** Sıfır portföyde divide-by-zero yanlış sonuç
- **FIN-012 (medium):** Snapshot atomicity — kritik kaynak fail → is_partial flag
- **FIN-013 (low):** Manuel kripto sanity check (linked'tan %50+ sapma uyarı)
- **FIN-014 (medium):** Cash flow installment + statement çift sayım riski
- **FIN-015 (low):** recurring_income hard-delete yerine archive
- **FIN-016 (medium):** wallets endpoint sembol whitelist sabit (snapshot dinamik)
- **FIN-017 (low):** TCMB cache 2 modülde ayrı — RateContext atomicity
- **FIN-019 (medium):** Vergi hesaplama yok (stopaj, GVK) — Faz 4
- **FIN-020 (medium):** total_value_tl Numeric(20,2) future-proof
- **FIN-021 (low):** ROUND_HALF_EVEN vs ROUND_HALF_UP (TMS standart)
- **FIN-022 (medium):** Decimal → JSON float — frontend precision kaybı
- **FIN-023 (low):** RecurringIncome.passive_deletes=True
- **FIN-024 (medium):** CoinGecko fail health_issues sızdırılmıyor
- **FIN-025 (low):** AssetPosition.unit_price_usd opsiyonel kolon

---

## G11 — Docs (doc-expert, 24 bulgu)

### Açılan Issue'lar
| ID | Öncelik | Issue | Başlık |
|----|---------|-------|--------|
| DOC-001 | critical | [#16](https://github.com/celikada/KFinans/issues/16) | CLAUDE.md sayım drift |
| DOC-002 | critical | [#17](https://github.com/celikada/KFinans/issues/17) | Router listesi 5 router eksik |
| DOC-003 | critical | [#18](https://github.com/celikada/KFinans/issues/18) | API ref 7 endpoint grubu eksik |
| DOC-004 | high | [#62](https://github.com/celikada/KFinans/issues/62) | Frontend dashboard sayfa listesi |
| DOC-005 | high | [#63](https://github.com/celikada/KFinans/issues/63) | docs/01 tarih + Faz 3 modülleri |
| DOC-008 | high | [#64](https://github.com/celikada/KFinans/issues/64) | docs/01 test sayısı drift |
| DOC-009 | high | [#65](https://github.com/celikada/KFinans/issues/65) | docs/02 8 tablo eksik |

### Backlog
- **DOC-006 (medium):** Cross-link path numaralandırılmamış — markdown-link-check CI
- **DOC-007 (medium):** CLAUDE.md "5 workflow" — 6 olmalı
- **DOC-010 (medium):** docs/05 model adı claude-sonnet-4-6 güncel mi?
- **DOC-011 (low):** docs/06 Faz 3 status header "Last updated"
- **DOC-012 (medium):** docs/04 §10 teknik borç — gerçek satır sayımı
- **DOC-013 (medium):** CLAUDE.md "Geliştirme Kuralları" 4 madde dar — 8-12 madde
- **DOC-014 (medium):** Memory tech_debt_cost_basis ✅ işaretli mi?
- **DOC-015 (low):** Memory settings_useeffect tech debt → docs/04 §10
- **DOC-016 (medium):** docs/01 sonraki sprint snapshot health/usd_try_rate ✓ yap
- **DOC-017 (medium):** Glossary eksik (TEFAS, BES, MKK, BiGA, SFC vb.)
- **DOC-018 (medium):** CHANGELOG.md yok — Keep a Changelog formatı
- **DOC-019 (low):** Multilingual: README + CONTRIBUTING TR+EN (Faz 4)
- **DOC-020 (low):** Sequence diagram'lar (auth flow, snapshot flow) Mermaid
- **DOC-021 (medium):** "11 dashboard kartı" iddiası — DASHBOARD_CARDS array baz alınsın
- **DOC-022 (medium):** FastAPI /docs prod'da kapalı mı? (ENABLE_DOCS=false)
- **DOC-023 (low):** User guide eksik (FAZ E)
- **DOC-024 (medium):** PR template doc checklist'i

---

## Toplam İstatistik

| Ajan | Bulgu | Critical | High | Issue Açılan | Backlog (md) |
|------|-------|----------|------|--------------|--------------|
| G1 architect | 11 | 0 | 4 | 4 | 7 |
| G2 backend | 18 | 1 | 3 | 4 | 14 |
| G3 security | 24 | 0 | 4 | 4 | 20 |
| G4 dba | 24 | 1 | 3 | 4 | 20 |
| G5 frontend | 23 | 1 | 4 | 5 | 18 |
| G6 ai | 14 | 3 | 4 | 7 | 7 |
| G7 compliance | 30 | 4 | 7 | 11 | 19 |
| G8 devops | 30 | 3 | 7 | 10 | 20 |
| G9 testing | 17 | 3 | 6 | 9 | 8 |
| G10 finance | 25 | 0 | 4 | 4 | 21 |
| G11 docs | 24 | 2 | 4 | 7 | 17 |
| **Toplam** | **240** | **18** | **50** | **63** | **171** |

> Critical/High sayıları rapor özetlerinden hafif farklı çünkü bazı bulgular birden fazla ajan tarafından yakalandı (örn. xpub leak SEC + BACK, SPK disclaimer AI + COMP, Postgres backup DBA + DEVOPS). Birleştirildiklerinde tek issue olarak açıldı.

## Sıradaki Aksiyon

1. [`sprint-plan.md`](./sprint-plan.md) — P0/P1/P2 önceliklendirme + tarih hedefleri
2. GitHub flag (#4360519) çözüldüğünde issue'lar anonim ziyaretçiye görünür olur
3. Backlog'taki medium/low bulgulardan birini ele almak isterseniz: `gh issue create` ile bu doc'tan kopyala-yapıştır + label ekle.
