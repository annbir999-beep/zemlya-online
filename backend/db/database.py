import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from core.config import settings

# В Celery каждая задача крутит СВОЙ event loop (см. tasks/*._run), а engine
# здесь модульный — один на форк воркера. Пул соединений при этом переживает
# луп: asyncpg-соединение, открытое в лупе N, всплывает в лупе N+1 и падает с
# «got Future attached to a different loop». Ставка на engine.dispose() в конце
# задачи не сработала: сам dispose бьётся об уже закрытый луп («Event loop is
# closed» — 100 таких warning'ов за сутки), соединения остаются в пуле, и
# следующий прогон берёт мёртвое (17.08.2026: 14 падений process_inbox и
# check_and_notify). NullPool убирает причину — соединение живёт ровно столько
# же, сколько сессия, и между лупами не переходит. API (uvicorn, один общий
# луп на весь процесс) остаётся на обычном пуле, там он по делу.
_NULLPOOL = os.getenv("SOTKA_DB_NULLPOOL") == "1"

if _NULLPOOL:
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
