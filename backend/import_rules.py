from app.database import get_db
from app.services.init_rules import init_patent_rules
import asyncio

async def main():
    async for db in get_db():
        await init_patent_rules(db)
        break

if __name__ == "__main__":
    asyncio.run(main())
