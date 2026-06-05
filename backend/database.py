from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
# sqlite:/// → sqlite+aiosqlite:///
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
# postgresql:// → postgresql+asyncpg://
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
# postgres:// (Render/Heroku 互換) → postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def run_migrations() -> None:
    """SQLite ローカル開発用: 既存テーブルへの新カラム追加。カラムが既存の場合は無視する。"""
    if not _IS_SQLITE:
        return  # PostgreSQL では create_all() で全カラムが作成されるためスキップ
    migrations = [
        "ALTER TABLE sources ADD COLUMN dedup_enabled BOOLEAN NOT NULL DEFAULT 1",
        "ALTER TABLE sources ADD COLUMN citation_filter_enabled BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE sources ADD COLUMN citation_top_multiplier INTEGER NOT NULL DEFAULT 5",
        "ALTER TABLE sources ADD COLUMN llm_prompt TEXT",
    ]
    async with engine.begin() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # カラムが既に存在する場合は無視


async def init_db() -> None:
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_migrations()
