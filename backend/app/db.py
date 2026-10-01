from collections.abc import AsyncIterator
from typing import Annotated
import os

import boto3
from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def _iam_token() -> str:
    host = os.environ["DB_HOST"]
    port = int(os.environ.get("DB_PORT", "5432"))
    user = os.environ.get("DB_USER", "postgres")
    region = os.environ.get("DB_REGION", "us-east-1")

    return boto3.client("rds", region_name=region).generate_db_auth_token(
        DBHostname=host,
        Port=port,
        DBUsername=user,
        Region=region,
    )


def create_engine() -> AsyncEngine:
    settings = get_settings()

    if os.environ.get("DB_IAM_AUTH", "").lower() == "true":
        host = os.environ["DB_HOST"]
        port = os.environ.get("DB_PORT", "5432")
        user = os.environ.get("DB_USER", "postgres")
        database = os.environ.get("DB_NAME", "postgres")

        url = f"postgresql+asyncpg://{user}@{host}:{port}/{database}"

        return create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
            connect_args={
                "password": _iam_token(),
                "ssl": "require",
            },
        )

    if not settings.db_pooling:
        return create_async_engine(
            settings.database_url,
            echo=False,
            poolclass=NullPool,
        )

    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )


engine: AsyncEngine = create_engine()

SessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
