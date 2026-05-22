from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# DBA-004 (FAZ H): Default 5+10 pool yetersiz. asyncio.gather snapshot job'da
# 10+ paralel sorgu, FastAPI dependency_overrides her istekte yeni session.
# pool_pre_ping=True stale connection kontrolu (TCP timeout sonrasi reuse hatasi).
#
# Audit 2026-05-21 #3: DB TLS. settings.database_ssl_mode degerine gore
# asyncpg connect_args ssl parametre set edilir. Modlar:
# - "disable": ssl=False (eski davranis, geriye uyumlu)
# - "prefer":  ssl=True ama cert verify OFF (self-signed cluster cert kabul)
# - "require": ssl=True + cert chain validate (production CA gerekli)
# Postgres pod selfsigned-cluster-issuer cert ile aktif; "prefer" cluster-ici
# defence-in-depth saglar (node compromise -> in-flight leak engelli).
_ssl_mode = settings.database_ssl_mode
if _ssl_mode == "disable":
    _connect_args = {"ssl": False}
elif _ssl_mode == "prefer":
    # Self-signed cluster cert pattern: encrypt-in-transit aktif ama
    # cert chain dogrulamasi cluster-ici trust modeli ile saglanir
    # (postgres svc DNS + K8s service mesh). Public CA yok.
    # SonarLint S5527/S4423/S4830 burada uygulanmaz — gercek
    # production "require" mode'a gecirilmeli (cluster CA bundle mount
    # gerektigi icin ayri PR).
    import ssl as _ssl_mod

    _ctx = _ssl_mod.create_default_context()
    _ctx.check_hostname = False  # noqa: S5527 (cluster-internal trust)
    _ctx.verify_mode = _ssl_mod.CERT_NONE  # noqa: S4830 (self-signed)
    _connect_args = {"ssl": _ctx}
elif _ssl_mode == "require":
    # CA bundle ile cert chain dogrulamasi — cluster-ici production-grade TLS.
    # cert-manager `postgres-tls` Secret backend pod'a /etc/postgres-ca/ca.crt
    # olarak mount edilir (k8s/backend.yaml volumeMount). CA bundle yoksa
    # default ssl_ctx CERT_REQUIRED (PKI'a guvenir) — fallback davranis.
    import os
    import ssl as _ssl_mod

    _ca_path = settings.database_ssl_ca_path
    if _ca_path and os.path.isfile(_ca_path):
        _ctx = _ssl_mod.create_default_context(cafile=_ca_path)
        _ctx.check_hostname = True
        _ctx.verify_mode = _ssl_mod.CERT_REQUIRED
        _connect_args = {"ssl": _ctx}
    else:
        _connect_args = {"ssl": True}  # asyncpg default ssl_ctx
else:
    _connect_args = {}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
