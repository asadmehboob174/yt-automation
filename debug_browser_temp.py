
import asyncio
from playwright.async_api import async_playwright
import os
import tempfile
import shutil

async def main():
    print("Testing Playwright Browser Launch (TEMP PROFILE)...")
    # specific temp dir
    temp_dir = os.path.join(tempfile.gettempdir(), "grok_debug_profile")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    
    async with async_playwright() as p:
        print(f"Launching persistent context from: {temp_dir}")
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-dev-shm-usage',
            '--js-flags="--max-old-space-size=2048"',
            '--process-per-site'
        ]
        
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=temp_dir,
                headless=False,
                args=args,
                viewport={'width': 1920, 'height': 1080}
            )
            print("✅ TEMP PROFILE Browser launched successfully!")
            await asyncio.sleep(2)
            await browser.close()
            print("✅ Browser closed.")
            
        except Exception as e:
            print(f"❌ Failed to launch with split profile: {e}")

if __name__ == "__main__":
    asyncio.run(main())
