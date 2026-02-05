import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def test_launch():
    profile_path = Path.home() / ".whisk-profile"
    print(f"Testing launch with profile: {profile_path}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=False,
            )
            print("Successfully launched!")
            await browser.close()
    except Exception as e:
        print(f"Launch failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_launch())
