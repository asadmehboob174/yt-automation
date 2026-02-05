
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    profile_dir = r"C:\Users\pc\.whisk-profile"
    print(f"🚀 Launching browser for manual login...")
    print(f"📁 Profile: {profile_dir}")
    
    async with async_playwright() as p:
        # Launching with a persistent context so the user's login is saved.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        page = await context.new_page()
        await page.goto("https://labs.google/whisk")
        
        print("\n" + "="*50)
        print("🔓 ACTION REQUIRED: Please log in to Whisk in the Chrome window.")
        print("✅ Once you are logged in and can see the generation dashboard,")
        print("   CLOSE THE BROWSER WINDOW to finish this script.")
        print("="*50 + "\n")
        
        # Wait until the browser is closed by the user.
        while True:
            if context.pages == []:
                break
            await asyncio.sleep(1)
            
        await context.close()
        print("✨ Login state saved! You can now run the automation.")

if __name__ == "__main__":
    asyncio.run(main())
