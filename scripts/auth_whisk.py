
"""
Authentication Helper for Google Whisk.
Run this script to open a browser and log in to your Google Account.
"""
import asyncio
from packages.services.whisk_agent import WhiskAgent

async def login():
    print("🚀 Launching Browser for Login...")
    print("👉 Please log in to Google Whisk manually in the window.")
    print("❌ Close the browser window when you are done to save the session.")
    
    agent = WhiskAgent(headless=False)
    browser, pw = await agent.get_context()
    
    page = await browser.new_page()
    await page.goto("https://labs.google/fx/tools/whisk/project")
    
    # Keep script running while browser is open
    try:
        # Wait until browser is closed by user
        while browser.contexts:
            await asyncio.sleep(1)
    except Exception:
        pass
        
    await pw.stop()
    print("✅ Session saved!")

if __name__ == "__main__":
    asyncio.run(login())
