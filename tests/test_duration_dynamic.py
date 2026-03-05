import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent
sys.path.append(str(root))

from playwright.async_api import async_playwright
from packages.services.grok_agent import VideoSettings, get_browser_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_duration_selection():
    async with async_playwright() as p:
        logger.info("🎬 Launching Grok Browser Context...")
        browser = await get_browser_context(p)
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        logger.info("🌐 Navigating to Grok Imagine...")
        await page.goto("https://grok.com/imagine")
        
        # Wait for the prompt area to load
        await page.wait_for_selector(".ProseMirror, textarea", state="visible", timeout=15000)
        await asyncio.sleep(2)
        
        # Test 1: Set 6s
        logger.info("🧪 TEST 1: Setting Duration to 6s")
        await VideoSettings.configure(page, duration="6s", aspect="9:16", resolution="480p")
        await asyncio.sleep(3)
        
        # Test 2: Set 10s
        logger.info("🧪 TEST 2: Setting Duration to 10s")
        await VideoSettings.configure(page, duration="10s", aspect="9:16", resolution="480p")
        await asyncio.sleep(3)
        
        # Test 3: Set 6s again
        logger.info("🧪 TEST 3: Setting Duration to 6s again")
        await VideoSettings.configure(page, duration="6s", aspect="16:9", resolution="720p")
        await asyncio.sleep(5)
        
        logger.info("✅ All duration tests complete.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_duration_selection())


if __name__ == "__main__":
    asyncio.run(test_duration_selection())
