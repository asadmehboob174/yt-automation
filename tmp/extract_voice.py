
import asyncio
import os
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from services.voice_extractor import VoiceExtractor

async def main():
    video_path = Path(r"d:\GitHub\yt-automation\video-audio-voice-cloning.mp4")
    extractor = VoiceExtractor()
    
    print(f"🎬 Starting extraction from: {video_path}")
    vocal_path = extractor.extract_vocals(video_path, "Girl_Clone")
    
    if vocal_path and vocal_path.exists():
        print(f"✅ Extraction Successful!")
        print(f"📍 Vocals saved at: {vocal_path.absolute()}")
    else:
        print(f"❌ Extraction Failed.")

if __name__ == "__main__":
    asyncio.run(main())
