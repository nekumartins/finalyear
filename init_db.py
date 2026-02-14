import asyncio
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.app.db.session import engine
from backend.app.db.models import Base

async def init_db():
    print("Initializing database...")
    async with engine.begin() as conn:
        # Create all tables defined in models.py
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
