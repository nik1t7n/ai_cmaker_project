from contextlib import asynccontextmanager
import os
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.core.config import database_url 

load_dotenv()

DATABASE_URL = database_url 


engine = create_async_engine(DATABASE_URL, echo=True)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_manager() -> AsyncGenerator[AsyncSession, Any]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
