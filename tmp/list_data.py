
import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
    
    channels = await db.channel.find_many()
    print(f"Found {len(channels)} channels:")
    for ch in channels:
        print(f"ID: {ch.id}, NicheId: {ch.nicheId}, Name: {ch.name}")
        # Find characters for this channel
        chars = await db.character.find_many(where={"channelId": ch.id})
        for c in chars:
            print(f"  - Char: {c.name}, ID: {c.id}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
