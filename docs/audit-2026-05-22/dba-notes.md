# DBA Audit Notları — 2026-05-22

> **⚠️ Güncelleme (2026-06-23):** Bu audit notu yazıldığında barındırma **Oracle Cloud Always Free VM** (`141.144.243.54`) idi. Proje **2026-06-23'te Hetzner Cloud'a taşındı** (CX23, 2 vCPU/4 GB, Falkenstein fsn1 DE, tek-node k3s v1.35, IP `91.99.123.163`). Aşağıdaki Oracle referansları **tarihsel** olarak korunmuştur; "multi-cloud taşınabilirlik / Hetzner'e migrate" önerileri kısmen gerçekleşmiştir. Güncel altyapı için CLAUDE.md + docs/operations/infrastructure-runbook.md'ye bakın.

Kapsam: PostgreSQL 16 (K3s StatefulSet, single-node Oracle Cloud), 40 Alembic migration (head `e2f3a4b5c6d7`), günlük age-encrypted logical backup (30 gün retention), DBA-004 connection pool (20+10), DBA-001 FK CASCADE/SET NULL, PERF-003 user_id index'leri, FAZ C1 wallet xpub Fernet.

## ✓ Mevcut Pozitif

- **TLS in-transit aktif**: cert-manager `selfsigned-cluster-issuer` + initContainer chmod 0600 (`postgres.yaml:35-67`). `ssl_min_protocol_version=TLSv1.2` (TLSv1.3 fiili).
- **Encryption-at-rest (backup)**: pg_dump → gzip → age asymmetric encryption; private key cluster DIŞINDA (Temp + Bitwarden). Cluster compromise → backup okunamaz.
- **FK bütünlüğü DB seviyesinde**: DBA-001 (`f7a8b9c0d1e2`) 7 FK'yı CASCADE/SET NULL'a çevirdi — ORM-only cascade'e bağımlılık kalktı, `pg_dump` restore'da FK violation yok.
- **Connection pool tunit**: 20+10 pool, `pool_pre_ping=True` (stale TCP detect), `pool_recycle=1800s` (PG idle timeout altında).
- **Index coverage**: PERF-003 + tablo-bazlı migration'lar; expenses/incomes/budgets user_id index'lendi, audit_logs composite (user_id, created_at) zaten yapılı.
- **CronJob hardening**: `readOnlyRootFilesystem=true`, `runAsNonRoot`, `seccompProfile=RuntimeDefault`, age binary `/tmp` emptyDir'a indiriliyor (PSS restricted).
- **Migration zinciri lineer**: 40 migration tek linked-list (initial `876bd62e282c` → head `e2f3a4b5c6d7`); branch label / merge yok. "multi-branch" şüphesi yanlış — `9a8b7c6d5e4f` (verify_token_expiry) zincir içinde normal node.

## ⚠ Çelişti / Düzeltme Notları (öncelik sırasıyla)

| # | Öncelik | Sorun | Etki | Öneri |
|---|---------|-------|------|-------|
| 1 | P0 | **Off-site backup YOK** — tüm yedekler aynı PVC'de (`local-path`, aynı Oracle VM disk). Node disk failure → DB + 30 gün backup birlikte kaybolur. | Tek-fail-point; KVKK m.12 "uygun güvenlik tedbirleri" risk altında | rclone CronJob → Oracle Object Storage (Always Free 20 GB) veya AWS S3 Glacier; günlük asenkron sync; encrypted age dump zaten transit-safe. 3-2-1 kuralı (3 kopya, 2 medya, 1 off-site) |
| 2 | P0 | **DR drill HİÇ YAPILMADI** — restore prosedürü dokümante (`backup-cronjob.yaml:13-17`) ama manuel test edilmemiş. "Backup exists ≠ restore works" | Felaket anında RTO bilinmiyor; private key path doğrulanmamış; age decrypt + psql restore zincirinde hidden bug olabilir | Quarterly drill protocol: (a) staging cluster'da random tarihli backup restore, (b) row count + checksum (`SELECT COUNT(*) per table`), (c) smoke test (login + dashboard), (d) RTO/RPO ölçümü, (e) runbook |
| 3 | P0 | **PITR yok** — sadece günlük logical dump. RPO = 24 saat (en kötü senaryoda 1 günlük veri kaybı; haftalık snapshot job tüm hafta verisini regenerate edemez) | Manual entry kayıpları (expense, income) restore edilemez; advice token billing log'u kaybolabilir | WAL-G veya pgBackRest → S3-compatible. PG `archive_mode=on` + `archive_command`. RPO 5 dk'ya düşer. Storage maliyeti minimal (WAL ~50 MB/gün) |
| 4 | P1 | **PVC `local-path` vendor lock-in (K3s)** — K3s `local-path-provisioner` node'a bind eder. Multi-node migration'da pod re-schedule edilirse stuck Pending. K8s portability sınırlı | Cloud taşıma (DigitalOcean / Hetzner / AWS EKS) durumunda PVC manuel mount; HA imkansız | Migration plan: Oracle Block Volume CSI (`oci-bv`) veya Longhorn (3-replica). Comment zaten `postgres.yaml:141-158`'de var; production-grade aşamasında uncomment |
| 5 | P1 | **Single replica StatefulSet** — `replicas: 1`. Postgres pod restart sırasında ~30 sn downtime (livenessProbe + startupProbe gerekli; şu an startupProbe YOK, initialDelaySeconds=30 yeterli değil) | Plan/unplan pod kill → uygulama 500 verir; `pool_pre_ping` reconnect yapsa da TCP backoff | Kısa vadeli: `startupProbe failureThreshold=30 periodSeconds=10`. Uzun vadeli: streaming replication + read replica (CloudNativePG operator önerilir) |
| 6 | P1 | **Migration zinciri 40 commit, baseline yok** — boş DB initial migration'dan head'e 40 step. Yeni dev/staging cluster setup'ı yavaş; rollback hata yüzeyi geniş | `alembic upgrade head` boş DB'de ~5-10 sn; production-grade ortamda DB schema kararlılığı belirsiz | Squash ETMEYIN (history kaybolur). Bunun yerine: post-1.0 release'de "consolidated baseline" migration üret + eski 40'ı archive (`alembic stamp` ile). Şimdilik dokümantasyon yeterli |
| 7 | P1 | **PostgreSQL-spesifik özellikler — DB portability düşük** | `pg_try_advisory_lock` (scheduler.py:48), JSONB (`audit_logs.extra`, kullanıcı consent), `gen_random_uuid()` muhtemel, `text[]` array. SQLite/MySQL'e portability ~%0 | Karar: vendor lock-in **kabul** (Postgres KFinans için core). Ancak `services/db_lock.py` abstraction'la advisory_lock'u soyutla (test'te in-memory mock) + JSONB için SQLAlchemy `JSON` type'ı kullan (driver-agnostic generic JSON) |
| 8 | P1 | **Pool `db_pool_size=20 + max_overflow=10` × multi-replica → patlamış limit riski** | Postgres `max_connections=100` default. 3 replica × 30 = 90 connection. K3s'de henüz tek pod ama scale-out durumunda Postgres overload | Pool per-pod env override: `DB_POOL_SIZE=10 DB_MAX_OVERFLOW=5` multi-replica config map; veya pgBouncer pooler (transaction mode, connection multiplexing) |
| 9 | P2 | **`pool_pre_ping=True` her query öncesi `SELECT 1` lateny** | ~0.5-1 ms latency per request (lokalde ihmal edilebilir, prod'da P99'a ekleniyor) | Trade-off kabul; `pool_recycle=1800` zaten stale azaltır. Alternatif: pre_ping kapat + connection_lost handler retry |
| 10 | P2 | **Backup CronJob success metric yok** — son backup zamanı + boyutu + decryption smoke test izlenmiyor | Sessizce fail eden backup (PVC dolu, age binary download fail) farkedilmeyebilir | Prometheus push-gateway veya Sentry breadcrumb; basit: Kubernetes Event + alert: `kubectl get cronjob postgres-backup -o jsonpath='{.status.lastSuccessfulTime}'` > 26 saat = alarm |
| 11 | P2 | **age binary GitHub'dan her run'da indiriliyor** (`backup-cronjob.yaml:125-129`) | GitHub rate limit + supply-chain risk (release artifact replace); ağ kesintisinde backup fail | Custom image: `postgres:16-alpine` + age binary pre-installed (multi-stage Dockerfile, GHCR'a push); CronJob `image: ghcr.io/celikada/postgres-backup:1.0` |
| 12 | P2 | **Backup retention 30 gün, KVKK retention politikası bağlamı yok** | audit_logs 365 gün (`COMP-022` doc'unda); ama backup'ta tutulan **kullanıcı** verisi 30 gün sonra silinemiyor (encrypted snapshot soft-delete'i geri çevirebilir) | Backup retention'ı KVKK m.7 ile uyumlula: ya backup'ta silinmiş kullanıcıların verisi backfill ile maskele, ya backup retention 30 → 90 gün (yasal saklama) + immutability politikası dokümante |
| 13 | P3 | **DB user `kfinans` superuser benzeri** — POSTGRES_USER = kfinans, ayrı `kfinans_app` (DML only) + `kfinans_admin` (DDL) ayrımı yok | Compromise edilen backend container DROP TABLE çağırabilir | İki user: app (CRUD), admin (migration). Alembic env.py'de `DATABASE_ADMIN_URL` ayrı |
| 14 | P3 | **`postgres-cert` Secret rotation manuel** — cert-manager renewal yapıyor olsa da Postgres pod cert reload için restart gerekir (TLS cert hot-reload yok) | 90 günde bir pod restart (downtime ~30 sn) | reloader operator (stakater/reloader): Secret değişti → StatefulSet rollout |

## Backup & DR Roadmap

**Sprint 1 (1 hafta) — RPO düşürme:**
- WAL archiving aktif: PG `archive_mode=on archive_command='wal-g wal-push %p'`
- WAL-G config: Oracle Object Storage bucket (Always Free 20 GB + free egress)
- RPO: 24 saat → 5-15 dk

**Sprint 2 (1 hafta) — Off-site:**
- rclone CronJob (her gün 03:00, daily backup'tan sonra) → Object Storage `kfinans-backups-offsite/`
- IAM policy: write-only (CronJob append-only token); read sadece manuel DR sırasında
- Retention: hot bucket 30 gün + cold tier 1 yıl (KVKK)

**Sprint 3 (2 hafta) — DR drill protokolü:**
- Staging cluster (`kfinans-staging` namespace) provision
- Quarterly drill checklist:
  1. Random backup tarihi seç (son 30 gün)
  2. Pull encrypted dump → local age decrypt → staging Postgres restore
  3. Migration head doğrula (`alembic current`)
  4. Row count regression check (script: top 10 tables row count delta)
  5. Smoke test: login + dashboard yüklenme + snapshot generate
  6. RTO/RPO ölç + runbook güncelle
- İlk drill ÖNCE production cutover'dan ÖNCE yapılmalı

**Sprint 4 (uzun vadeli) — HA + streaming replication:**
- CloudNativePG operator (cluster-native PG HA)
- Read replica → analytics workload (advisor.py portfolio analizi)
- Failover: <30 sn

## Reusability / Portability

**Migration zinciri:** 40 commit + lineer (multi-branch yanılgı; tek down_revision chain). **Squash gerekli DEĞIL** — Alembic history forensic value (her migration KFinans evolution story). Post-1.0 baseline consolidation (`alembic stamp` ile) opsiyonel. Risk düşük.

**PostgreSQL-spesifik feature audit:**
- `pg_try_advisory_lock` (scheduler leader election) → Tek bağımlılık noktası. `app/services/db_lock.py` abstraction önerilir: `async with distributed_lock("snapshot_job"): ...` (PG advisory_lock implementation; SQLite için no-op, MySQL için GET_LOCK).
- `JSONB` (audit_logs.extra, consent fields) → SQLAlchemy `sa.JSON` (generic) zaten Postgres'te otomatik JSONB. MySQL 8+ JSON, SQLite TEXT(JSON1) — driver layer transparent. OK.
- `gen_random_uuid()` / `uuid_generate_v4()` → Doğrulanmadı; Python `uuid.uuid4()` ile üretiliyorsa portable.
- `TIMESTAMP WITH TIME ZONE` → Standart SQL, portable.
- **Karar**: Postgres lock-in **kabul edilebilir** (Oracle K3s + 50 GB veri büyüklüğü için PG optimal). DB-agnostic abstraction sadece advisory_lock için (low effort, high portability gain).

**Connection pool tuning multi-instance ready mi?** Hayır. Şu an `db_pool_size=20` global config. Multi-replica deploy'da `replicas × (pool_size + max_overflow) <= PG max_connections` aritmetiği env-override gerektirir. Önerilen değerler `app/config.py:108` comment'inde dokümante (30 connection/replica). Production cutover'dan ÖNCE Helm chart `values.yaml` `db.poolSizePerReplica` parametresi eklenmeli.

---

## 300-500 Kelime Özet

KFinans PostgreSQL 16 setup'ı **gelişme yolunda ama production-grade DR için 3 P0 boşluk** taşıyor. Pozitif tarafta: TLS in-transit aktif (cert-manager + initContainer chmod 0600), age asymmetric encryption ile backup-at-rest (private key cluster dışında), DBA-001 FK CASCADE/SET NULL (pg_dump restore'da FK violation riski yok), connection pool 20+10 + `pool_pre_ping` + `pool_recycle=1800` (stale TCP koruma), CronJob PSS restricted (readOnlyRootFilesystem + non-root + seccomp). Migration zinciri 40 commit ve **lineer** (multi-branch endişesi yanlış — `9a8b7c6d5e4f` zincirin normal düğümü, branch_labels yok).

**3 kritik (P0) boşluk:**
1. **Off-site backup yok** — tüm 30 günlük yedek aynı PVC'de, aynı `local-path` storage class'ında, aynı Oracle VM disk'inde. Node disk failure → DB + tüm backup tek tarafta kaybolur. 3-2-1 backup kuralı ihlal. rclone → Oracle Object Storage (Always Free) CronJob 1 hafta.
2. **DR drill hiç yapılmamış** — restore prosedürü dokümante ama age decrypt + psql restore zinciri test edilmemiş. "Backup exists ≠ restore works". Quarterly drill protokolü + ilk drill production cutover'dan ÖNCE şart.
3. **PITR yok** — sadece günlük logical pg_dump. RPO 24 saat. Manual entry (expense, income) restore edilemez. WAL-G + Oracle Object Storage ile RPO 5-15 dk'ya iner; storage maliyeti minimal (~50 MB WAL/gün).

**Portability:** PVC `local-path` K3s built-in provisioner — node-bound, multi-node'a uygunsuz. Migration plan zaten comment'te (`oci-bv` veya Longhorn) — production ölçeklenmeden uncomment edilmeli. PostgreSQL-spesifik özellikler: `pg_try_advisory_lock` (scheduler leader election, **tek lock-in noktası** — `services/db_lock.py` abstraction önerilir), JSONB (SQLAlchemy generic `sa.JSON` ile zaten driver-agnostic transparent), `TIMESTAMP WITH TIME ZONE` standart. Karar: Postgres vendor lock-in kabul edilebilir; sadece advisory_lock'u abstract et.

**Connection pool multi-replica ready DEĞIL** — `db_pool_size=20` global; 3 replica × 30 = 90 connection PG `max_connections=100` default'a çok yaklaşır. Helm `db.poolSizePerReplica` env override + opsiyonel pgBouncer transaction pooler önerilir.

**Migration squash GEREKSIZ** — 40 commit lineer, history forensic değer taşır. Post-1.0 release'de "baseline consolidation" opsiyonel (alembic stamp ile). Şu an dokümantasyon yeterli.

**Aksiyon önceliği**: (a) off-site sync (P0, 1 hafta), (b) DR drill protokolü + ilk drill (P0, 2 hafta), (c) PITR/WAL-G (P0, 1 hafta), (d) PVC StorageClass migration plan (P1, multi-node geçiş öncesi), (e) advisory_lock abstraction (P1, low effort), (f) pool per-replica tuning (P1, scale-out öncesi).
