
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from packages.services.whisk_agent import WhiskAgent

async def capture_whisk():
    agent = WhiskAgent(headless=False)
    browser = None
    try:
        browser, pw = await agent.get_context()
        page = await browser.new_page()
        print("Navigating to Whisk Project...")
        await page.goto("https://labs.google/fx/tools/whisk/project", timeout=60000)
        await asyncio.sleep(8)
        
        # Click ENTER TOOL if present
        enter_tool_btn = page.locator("text='ENTER TOOL'")
        if await enter_tool_btn.count() > 0:
            print("Clicking ENTER TOOL landing button...")
            await enter_tool_btn.first.click()
            await asyncio.sleep(5)
        
        # Open Sidebar
        print("Searching for 'ADD IMAGES' button...")
        add_images_btn = page.locator("button:has-text('ADD IMAGES')")
        if await add_images_btn.count() > 0:
            print("Found 'ADD IMAGES'. Clicking...")
            await add_images_btn.click()
            await asyncio.sleep(3)
        
        # Take full page screenshot
        screenshot_path = "whisk_full_page.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to {screenshot_path}")
        
        # Also print some debug info about slots
        slots = page.locator("div[style*='dashed'], div[class*='dashed'], div:has(i:text('person'))").filter(has_not=page.locator("h1, h2, h3, h4"))
        count = await slots.count()
        print(f"Detected {count} potential slots.")
        for i in range(min(count, 5)):
            text = await slots.nth(i).inner_text()
            print(f"Slot {i} text: {text}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if browser:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_whisk())
