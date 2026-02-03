
"""
Authentication Helper for Google Whisk.
Run this script to open a browser and log in to your Google Account.
"""
import asyncio
import sys
import os

# Add root directory to path so we can import packages
sys.path.append(os.getcwd())

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
        # Wait until browser is closed by user (checking pages count)
        while len(browser.pages) > 0:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Loop exited: {e}")
        pass
        
    await pw.stop()
    print("✅ Session saved!")

if __name__ == "__main__":
    asyncio.run(login())
    input("\n👌 Press Enter to exit this script...")
