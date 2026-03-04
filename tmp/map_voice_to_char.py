
import asyncio
from prisma import Prisma
from pathlib import Path

async def main():
    db = Prisma()
    await db.connect()
    
    # Check for the pets channel (Wholesome Paws) or just use the first available channel
    channel = await db.channel.find_first()
    if not channel:
        print("❌ No channels found. Cannot map character.")
        return

    voice_path = r"D:\GitHub\yt-automation\packages\assets\voices\girl_clone_raw.mp3"
    
    # Create or update a character named 'Girl'
    char = await db.character.upsert(
        where={
            "id": "ck-girl-cloned-voice" # Deterministic ID for testing
        },
        data={
            "create": {
                "id": "ck-girl-cloned-voice",
                "channelId": channel.id,
                "name": "Girl",
                "imageUrl": "placeholder.png",
                "voiceUrl": voice_path,
                "voiceProvider": "xtts"
            },
            "update": {
                "voiceUrl": voice_path,
                "voiceProvider": "xtts"
            }
        }
    )
    
    print(f"✅ Character '{char.name}' (ID: {char.id}) updated with custom voice.")
    print(f"📍 Voice Path: {char.voiceUrl}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
