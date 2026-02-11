
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    print("Testing Playwright Browser Launch...")
    profile_path = r"C:\Users\asad.mehboob\.grok-profile"
    
    async with async_playwright() as p:
        print(f"Launching persistent context from: {profile_path}")
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-dev-shm-usage',
            '--js-flags="--max-old-space-size=2048"',
            '--process-per-site'
        ]
        
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=False,
                args=args,
                viewport={'width': 1920, 'height': 1080},
                # user_agent matches agent
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            )
            print("✅ Browser launched successfully!")
            page = browser.pages[0]
            await page.goto("https://google.com")
            print("✅ Navigation successful!")
            await asyncio.sleep(2)
            await browser.close()
            print("✅ Browser closed.")
            
        except Exception as e:
            print(f"❌ Failed to launch: {e}")

if __name__ == "__main__":
    asyncio.run(main())
