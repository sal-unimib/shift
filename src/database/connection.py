from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.utils.settings import settings

engine = create_async_engine(
    settings.db.sqlalchemy_url,
    echo=settings.db.echo,
    pool_pre_ping=True,
    pool_size=settings.db.pool_size,
    max_overflow=settings.db.max_overflow,
    pool_timeout=settings.db.pool_timeout,
)

SessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Provide an asynchronous database session for a FastAPI request.

    Closes the session when the request ends and attempts rollback before propagating an unhandled exception. Successful writes are committed explicitly by their callers.

    :return: Async iterator yielding the session for the request.
    :rtype: collections.abc.AsyncIterator[sqlalchemy.ext.asyncio.AsyncSession]
    """
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
