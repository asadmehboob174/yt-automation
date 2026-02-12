import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from packages.services.grok_agent import GrokAnimator, logger
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_audio_generation():
    print("🚀 Starting Audio Reproduction Test...")
    
    # Use an existing image or create a dummy one
    image_path = Path("test_thumb.png")
    if not image_path.exists():
        print("⚠️ 'test_thumb.png' not found. Please provide an image path.")
        # Try to find any png/jpg in current dir
        images = list(Path(".").glob("*.png")) + list(Path(".").glob("*.jpg"))
        if images:
            image_path = images[0]
            print(f"✅ Found fallback image: {image_path}")
        else:
            print("❌ No images found for testing.")
            return

    animator = GrokAnimator()
    
    try:
        print(f"🎬 Generating video from {image_path}...")
        video_path = await animator.animate(
            image_path=image_path,
            motion_prompt="The character speaks clearly",
            dialogue="Hello, this is a test of the audio generation capabilities.",
            duration=10
        )
        
        print(f"✅ Video generated at: {video_path}")
        
        # Verify Audio Stream using ffprobe
        import ffmpeg
        try:
            probe = ffmpeg.probe(str(video_path))
            audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
            
            if audio_streams:
                print(f"🔊 SUCCESS: Audio stream detected! Codec: {audio_streams[0]['codec_name']}")
            else:
                print("🔇 FAILURE: No audio stream found in the video file.")
                
        except Exception as e:
            print(f"⚠️ Failed to probe video file: {e}")
            
    except Exception as e:
        print(f"❌ Generation failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_audio_generation())
