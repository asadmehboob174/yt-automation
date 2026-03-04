import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "packages"))

load_dotenv()

async def test_sara():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = "hqFZL8ZnNxQK2qFcuxRL"
    
    from services.audio_engine import AudioEngine
    engine = AudioEngine()
    
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    out_path = tmp_dir / "test_sara.mp3"
    
    test_text = "یہ ایک ٹیسٹ ہے۔"
    print(f"Testing Sara Voice ID: {voice_id}")
    
    try:
        result_path = await engine.generate_narration(
            text=test_text,
            voice_id=voice_id,
            provider="elevenlabs",
            output_path=out_path
        )
        if result_path and result_path.exists():
            print(f"SUCCESS! Sara voice generated at {result_path}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_sara())
