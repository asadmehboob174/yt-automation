import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from playwright.async_api import async_playwright

PROFILE_PATH = Path(os.path.expanduser("~/.grok-profile"))

async def main():
    async with async_playwright() as p:
        print("🚀 Launching browser for Text-Only Test...")
        # Use exact same launch args as grok_agent
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_PATH),
            channel="chrome",
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await context.new_page()
        print("🔗 Navigating to Grok...")
        await page.goto("https://grok.com/imagine")
        await asyncio.sleep(5)
        
        # Test 1: Find Prompt Input
        print("📝 Looking for prompt input...")
        prompt_input = page.locator("textarea, [placeholder*='imagine'], [contenteditable='true']").first
        if await prompt_input.count() > 0:
            print("✅ Found prompt input! Typing...")
            await prompt_input.fill("A futuristic city at sunset, cyberpunk style")
        else:
            print("❌ Could not find prompt input!")
            return

        await asyncio.sleep(2)

        # Test 2: Find Submit Button
        print("🖱️ Looking for Send button...")
        submit_btn = page.locator("button[aria-label='Send message'], button[aria-label='Send'], button[aria-label='Submit'], button[type='submit']")
        
        if await submit_btn.count() > 0:
            print(f"✅ Found submit button: {await submit_btn.first.get_attribute('aria-label')}")
            print("🚀 Clicking submit...")
            await submit_btn.first.click()
        else:
            print("❌ Could not find submit button!")
            
        print("⏳ Waiting 10 seconds to see if generation starts...")
        await asyncio.sleep(10)
        
        print("✅ Test Complete. If you see an image generating, the bot controls work!")
        # await context.close() # Keep open for user to see

if __name__ == "__main__":
    asyncio.run(main())
