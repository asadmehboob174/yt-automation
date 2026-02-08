
import asyncio
from pathlib import Path
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath("C:/Users/Asad/Documents/GitHub/yt-automation"))

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
        
        # We need to access the page object. generate_single_clip manages its own page unless passed.
        # So we'll modify the test to get a browser/page first, then pass it.
        browser, pw = await get_browser_context()
        page = await browser.new_page()
        await page.goto("https://grok.com/imagine", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5) # Wait for full load
        
        # CAPTURE SCREENSHOT
        await page.screenshot(path="grok_ui_state.png", full_page=True)
        print("✅ Saved grok_ui_state.png")

        print("📸 Generating video from test image...")
        video_path = await generate_single_clip(
            image_path=test_img.absolute(),
            character_pose="A red square",
            camera_angle="Static",
            style_suffix="Minimalist",
            motion_description="The red square pulses slowly",
            dialogue="This is a test.",
            duration="5s", # Short duration for test
            aspect="9:16",
            external_page=page # PASS THE PAGE WE OPENED
        )
        print(f"✅ Video generated successfully: {video_path}")
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_grok())
