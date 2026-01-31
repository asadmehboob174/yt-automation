import asyncio
import os
import sys
from pathlib import Path

# Add project root to path to import packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from playwright.async_api import async_playwright

# Must match grok_agent.py
PROFILE_PATH = Path.home() / ".grok-profile"

async def main():
    print(f"📂 Loading profile from: {PROFILE_PATH}")
    
    # Force Proactor loop on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async with async_playwright() as p:
        print("🚀 Launching browser...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_PATH),
            channel="chrome",  # Connect to installed Chrome
            headless=False,
            # CRITICAL: Remove "Chrome is being controlled" banner and flags
            ignore_default_args=["--enable-automation"],
            args=[
                '--disable-blink-features=AutomationControlled', 
                '--no-sandbox',
                '--disable-infobars',
            ],
            # viewport={"width": 1280, "height": 720}
        )
        
        page = await context.new_page()
        # NOTE: We DO NOT use Stealth() here intentionally. 
        # For manual login, "less is more". Stealth JS sometimes triggers Cloudflare.
        
        print("🌐 Navigating to Grok...")
        await page.goto("https://grok.com/imagine")
        
        print("\n" + "="*50)
        print("✅ BROWSER OPENED!")
        print("👉 Please LOG IN manually in this window.")
        print("👉 When you are done, press CTRL+C in this terminal to save and exit.")
        print("="*50 + "\n")
        
        # input() blocks the async loop! Use a keep-alive loop instead.
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n💾 Saving session...")
            await context.close()
            print("✅ Session saved. You can now run the server.")

if __name__ == "__main__":
    asyncio.run(main())
