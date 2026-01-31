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
        print("🚀 Launching browser for debugging...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_PATH),
            channel="chrome",
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await context.new_page()
        print("🔗 Navigating to Grok...")
        await page.goto("https://grok.com/imagine")
        await page.wait_for_timeout(5000)
        
        print("📸 Dumping page content...")
        content = await page.content()
        with open("grok_page_dump.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        print("✅ HTML saved to grok_page_dump.html")
        
        # Also print all input elements
        inputs = await page.locator("input").all()
        print(f"🔎 Found {len(inputs)} input elements:")
        for i, inp in enumerate(inputs):
            try:
                type_attr = await inp.get_attribute("type")
                id_attr = await inp.get_attribute("id")
                visible = await inp.is_visible()
                print(f"   [{i}] Type: {type_attr}, ID: {id_attr}, Visible: {visible}")
            except:
                pass
                
        # Print buttons
        btns = await page.locator("button").all()
        print(f"🔎 Found {len(btns)} buttons:")
        for i, btn in enumerate(btns):
            try:
                label = await btn.get_attribute("aria-label")
                text = await btn.inner_text()
                if "Attach" in (label or "") or "Attach" in (text or ""):
                    print(f"   🎯 MATCH: Label: {label}, Text: {text}")
            except:
                pass

        print("🛑 Closing...")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
