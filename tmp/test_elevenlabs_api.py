import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root and packages to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "packages"))

# Load .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_elevenlabs_credentials():
    print("\n🔍 Testing ElevenLabs API Credentials and Voice ID...")
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ Error: ELEVENLABS_API_KEY not found in .env")
        return
    else:
        print(f"✅ Found API Key in .env (ends with ...{api_key[-4:]})")

    # The Voice ID the client provided
    voice_id = "Sm1seazb4gs7RSlUVw7c"
    print(f"🎙️ Testing Voice ID: {voice_id}")

    try:
        from services.audio_engine import AudioEngine
        engine = AudioEngine()
        
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)
        out_path = tmp_dir / "test_elevenlabs_urdu.mp3"
        
        # Test with Urdu text
        test_text = "یہ ایک ٹیسٹ ہے۔" # "This is a test."
        print(f"📝 Generating Urdu audio: '{test_text}'")
        
        result_path = await engine.generate_narration(
            text=test_text,
            voice_id=voice_id,
            provider="elevenlabs",
            output_path=out_path
        )
        
        if result_path and result_path.exists():
            size = result_path.stat().st_size
            print(f"✅ SUCCESS! ElevenLabs API is working perfectly.")
            print(f"✅ Voice '{voice_id}' works.")
            print(f"✅ Generated Audio: {result_path} ({size} bytes)")
        else:
            print("❌ FAILED: Generation completed but file not found.")
            
    except Exception as e:
        print(f"\n❌ FAILED: ElevenLabs API test threw an error:")
        print(f"Error Details: {e}")

if __name__ == "__main__":
    asyncio.run(test_elevenlabs_credentials())
