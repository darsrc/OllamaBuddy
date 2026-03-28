from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import event
from config import settings


class Base(DeclarativeBase):
    pass


# Convert sqlite:/// -> sqlite+aiosqlite:/// (idempotent)
_raw = settings.db_path
if _raw.startswith("sqlite:///") and "aiosqlite" not in _raw:
    _db_url = _raw.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    _db_url = _raw

engine = create_async_engine(_db_url, connect_args={"check_same_thread": False})


@event.listens_for(engine.sync_engine, "connect")
def _set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")


AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
