import asyncio
import os
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from services.music_generator import generate_music_with_ai, generate_background_music

async def test_music_generation():
    print("🎵 Testing Music Generation Systems...")
    
    # 1. Test AI Music Generation
    prompt = "Lo-fi hip hop beat for studying, chill vibes"
    print(f"\n1. AI Music Gen (Prompt: '{prompt}')...")
    
    # Check API Key
    if not os.getenv("HUGGINGFACE_API_KEY"):
        print("⚠️ HUGGINGFACE_API_KEY not found. Skipping AI test.")
    else:
        try:
            path = await generate_music_with_ai(prompt, duration=5)
            if path and path.exists():
                print(f"✅ AI Music Generated: {path}")
            else:
                print("❌ AI Music Generation failed (no file returned)")
        except Exception as e:
            print(f"❌ AI Music Error: {e}")

    # 2. Test Stock Music Fallback
    mood = "horror"
    print(f"\n2. Stock Music (Mood: '{mood}')...")
    try:
        path = generate_background_music(duration=5, mood=mood)
        if path and path.exists():
            print(f"✅ Stock Music Retrieved: {path}")
        else:
            print("❌ Stock Music failed")
    except Exception as e:
        print(f"❌ Stock Music Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_music_generation())
