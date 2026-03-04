
import asyncio
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from services.audio_engine import AudioEngine

async def main():
    engine = AudioEngine()
    text = "This is a test of the default system voice. It should sound like the extracted girl's voice."
    
    # Defaults set in main.py logic: provider="xtts", voice_id=girl_path
    girl_path = r"D:\GitHub\yt-automation\packages\assets\voices\girl_clone_raw.mp3"
    
    print(f"🎬 Testing default voice cloning...")
    try:
        output_path = await engine.generate_narration(
            text=text,
            provider="xtts",
            reference_audio=girl_path,
            output_path=Path("d:/GitHub/yt-automation/tmp/default_voice_test.mp3")
        )
        print(f"✅ Success! Generated at: {output_path}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
