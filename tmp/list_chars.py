
import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
    
    characters = await db.character.find_many()
    print(f"Found {len(characters)} characters:")
    for char in characters:
        print(f"ID: {char.id}, Name: {char.name}, VoiceId: {char.voiceId}, VoiceUrl: {char.voiceUrl}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
