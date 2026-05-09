from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# DBA-004 (FAZ H): Default 5+10 pool yetersiz. asyncio.gather snapshot job'da
# 10+ paralel sorgu, FastAPI dependency_overrides her istekte yeni session.
# pool_pre_ping=True stale connection kontrolu (TCP timeout sonrasi reuse hatasi).
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
