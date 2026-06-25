import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT id, stay_id, author_role, recorded_at, content FROM raw_document_nodes;"))
        rows = result.fetchall()
        print(f"Total raw document nodes: {len(rows)}")
        for r in rows:
            print(f"ID: {r[0]} | Stay: {r[1]} | Role: {r[2]} | Time: {r[3]}")
            print(f"  Content: {r[4][:100]}...")

if __name__ == "__main__":
    asyncio.run(check())
