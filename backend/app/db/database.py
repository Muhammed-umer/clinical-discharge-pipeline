import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import ssl

load_dotenv(override=True)

# Production-grade asynchronous engine setup using asyncpg
DATABASE_URL = os.getenv("DATABASE_URL")


ssl_context = ssl.create_default_context()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True only for active query debugging
    pool_pre_ping=True,  # Automatically checks and revives dead connections
    pool_size=20,
    max_overflow=10,
    connect_args={
        "ssl": ssl_context
    }
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