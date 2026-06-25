import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Production-grade asynchronous engine setup using asyncpg
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_pipeline")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True only for active query debugging
    pool_pre_ping=True,  # Automatically checks and revives dead connections
    pool_size=20,
    max_overflow=10
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """Dependency injection wrapper providing safe transaction boundaries for FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise