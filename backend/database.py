from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

try:
    from config import DATABASE_URL
except ModuleNotFoundError:
    from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
