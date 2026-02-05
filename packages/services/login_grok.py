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

    # CLEAN STALE LOCKS FIRST
    if os.name == 'nt':
        try:
            os.system('taskkill /F /IM chrome.exe /T 2>nul')
            os.system('taskkill /F /IM chromium.exe /T 2>nul')
            print("🔪 Force killed dangling browser processes.")
            await asyncio.sleep(1)
        except: pass

    async with async_playwright() as p:
        print("🚀 Launching browser...")
        try:
            # MATCHING GROK AGENT CONFIG EXACTLY
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_PATH),
                # channel="chrome" REMOVED to match grok_agent
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=[
                    '--disable-blink-features=AutomationControlled', 
                    '--no-sandbox',
                    '--disable-infobars',
                ],
            )
        except Exception as e:
            print(f"❌ Failed to launch browser: {e}")
            print("💡 Tip: Close ALL Chrome windows and run this again.")
            return
        
        page = await context.new_page()
        # NOTE: We DO NOT use Stealth() here intentionally. 
        # For manual login, "less is more". Stealth JS sometimes triggers Cloudflare.
        
        print("🌐 Navigating to Grok...")
        try:
            await page.goto("https://grok.com/imagine")
        except Exception as e:
            print(f"⚠️ Navigation warning (safe to ignore if page loads): {e}")
        
        print("\n" + "="*50)
        print("✅ BROWSER OPENED!")
        print("👉 Please LOG IN manually in this window.")
        print("👉 When you are done, press CTRL+C in this terminal to save and exit.")
        print("="*50 + "\n")
        
        # Keep alive
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n💾 Saving session...")
            await context.close()
            print("✅ Session saved. You can now run the server.")

if __name__ == "__main__":
    asyncio.run(main())
