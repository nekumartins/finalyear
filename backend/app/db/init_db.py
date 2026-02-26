"""
Database bootstrap helper.

Creates any missing tables using SQLAlchemy metadata. This is idempotent and
safe to run at container startup for MVP deployments.
"""
import asyncio

from backend.app.db.models import Base
from backend.app.db.session import engine


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
