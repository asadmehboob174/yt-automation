
import asyncio
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from services.audio_engine import AudioEngine

async def main():
    engine = AudioEngine()
    
    test_cases = [
        {
            "name": "English Cloned Default",
            "text": "This is a test of the English cloned voice.",
            "provider": "xtts"
        },
        {
            "name": "Urdu Script Fallback",
            "text": "رنگوں اور روشنیوں سے سجی ہوئی دنیا",
            "provider": "xtts"
        }
    ]
    
    girl_path = r"D:\GitHub\yt-automation\packages\assets\voices\girl_clone_raw.mp3"
    
    for case in test_cases:
        print(f"🎬 Testing: {case['name']}...")
        try:
            output_path = await engine.generate_narration(
                text=case['text'],
                provider=case['provider'],
                voice_id=girl_path, # Passed as path (the new default)
                reference_audio=girl_path,
                output_path=Path(f"d:/GitHub/yt-automation/tmp/test_{case['name'].replace(' ', '_').lower()}.mp3")
            )
            print(f"✅ Success! Generated at: {output_path}")
        except Exception as e:
            print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
