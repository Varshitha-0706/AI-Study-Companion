import asyncio
import sys
sys.path.insert(0, ".")

from app.db.session import engine, Base
import app.models.models  # Register all models with Base.metadata
from sqlalchemy import text


async def init():
    print("Connecting to database...")
    async with engine.begin() as conn:
        print("Enabling vector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully!")

        result = await conn.execute(text("""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'chunks' AND column_name = 'embedding'
        """))
        row = result.fetchone()
        print(f"Chunks embedding column: {row}")

        dim_res = await conn.execute(text("""
            SELECT atttypmod 
            FROM pg_attribute 
            WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'
        """))
        print(f"Vector dimensions in pgvector: {dim_res.scalar()}")

        # Check all tables created
        tables_res = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """))
        tables = [r[0] for r in tables_res.fetchall()]
        print(f"Created {len(tables)} tables: {tables}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init())
