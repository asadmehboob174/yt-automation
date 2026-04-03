
import asyncio
from pathlib import Path
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath("d:/GitHub/yt-automation"))

from packages.services.grok_agent import generate_single_clip, get_browser_context

async def test_grok():
    print("🚀 Starting Grok Manual Test...")
    
    # Create a dummy image for testing if one doesn't exist
    test_img = Path("test_image.png")
    if not test_img.exists():
        # Create a simple colored square
        from PIL import Image
        img = Image.new('RGB', (1024, 1024), color = 'red')
        img.save(test_img)
    
    try:
        print("📸 Capturing Grok UI state for debugging...")
        
        print("📸 Generating video from test image...")
        video_path = await generate_single_clip(
            image_path=test_img.absolute(),
            character_pose="A red square",
            camera_angle="Static",
            style_suffix="Minimalist",
            motion_description="The red square pulses slowly",
            dialogue="This is a test.",
            duration="6s", # 6s or 10s depending on unit test request
            aspect="9:16",
            resolution="480p"
        )
        print(f"✅ Video generated successfully: {video_path}")
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_grok())
