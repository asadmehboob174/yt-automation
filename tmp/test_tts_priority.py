import asyncio
import os
import logging
from pathlib import Path
from packages.services.audio_engine import AudioEngine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_priority_chain():
    engine = AudioEngine()
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    
    # Test 1: ElevenLabs Priority (Expect failure if key missing, then fallback)
    print("\n💎 Testing: ElevenLabs Priority (Will fallback if key/ID fails)...")
    try:
        # Use the ID provided by the user
        voice_id = "Sm1seazb4gs7RSlUVw7c" 
        path = await engine.generate_narration(
            text="This is a priority test. ElevenLabs should be first.",
            voice_id=voice_id,
            output_path=tmp_dir / "test_elevenlabs_priority.mp3"
        )
        print(f"✅ Success! Generated at: {path}")
    except Exception as e:
        print(f"❌ ElevenLabs priority test failed: {e}")

    # Test 2: XTTS Fallback (Provide reference but invalid ElevenLabs ID)
    print("\n🎭 Testing: XTTS Fallback (By forcing ElevenLabs failure)...")
    try:
        # Provide a local path for voice_id to skip ElevenLabs priority
        ref_audio = Path(r"D:\GitHub\yt-automation\packages\assets\voices\girl_clone_raw.mp3")
        path = await engine.generate_narration(
            text="This should bypass ElevenLabs and use XTTS.",
            voice_id=str(ref_audio), # Path forces skip of ElevenLabs
            reference_audio=ref_audio,
            output_path=tmp_dir / "test_xtts_fallback.mp3"
        )
        print(f"✅ Success! Generated at: {path}")
    except Exception as e:
        print(f"❌ XTTS fallback test failed: {e}")

    # Test 3: Edge-TTS Ultimate Fallback (No key, no reference)
    print("\n🛡️ Testing: Edge-TTS Ultimate Fallback...")
    try:
        path = await engine.generate_narration(
            text="This is the final safety net.",
            voice_id="en-US-AriaNeural",
            output_path=tmp_dir / "test_edge_fallback.mp3"
        )
        print(f"✅ Success! Generated at: {path}")
    except Exception as e:
        print(f"❌ Edge-TTS fallback test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_priority_chain())
