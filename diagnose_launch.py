import asyncio
import os
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

async def run_test(profile_path=None, use_temp=False):
    print(f"\n🧪 TEST: Launching with [{'TEMP' if use_temp else 'EXISTING'}] profile...")
    if profile_path:
        print(f"   Path: {profile_path}")

    async with async_playwright() as p:
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-infobars',
            '--disable-session-crashed-bubble',
            '--disable-extensions',
            '--no-default-browser-check',
            '--no-first-run',
            '--disable-gpu',
            '--ignore-certificate-errors',
            '--start-maximized'
        ]
        
        user_data_dir = profile_path if profile_path else (os.getcwd() + "\\temp_profile")
        
        try:
            print("   🚀 Launching...")
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                channel="chrome",
                headless=False,
                args=args,
                timeout=10000
            )
            print("   ✅ SUCCESS: Browser launched!")
            await asyncio.sleep(2)
            await browser.close()
            print("   🔻 Closed successfully.")
            return True
        except Exception as e:
            print(f"   ❌ FAILURE: {e}")
            return False

async def main():
    # 1. Test with the actual profile that is failing
    real_profile = Path.home() / ".whisk-profile"
    print(f"🔍 Diagnosing Launch Issues for: {real_profile}")
    
    # Clean locks first just in case
    locks = [
        real_profile / "SingletonLock",
        real_profile / "SingletonCookie",
        real_profile / "SingletonSocket",
        real_profile / "lock"
    ]
    for lock in locks:
        if lock.exists():
            try:
                lock.unlink()
                print(f"   🧹 Removed lock: {lock.name}")
            except: pass

    success_real = await run_test(profile_path=real_profile, use_temp=False)
    
    # 2. Test with a completely fresh temporary profile
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        success_temp = await run_test(profile_path=Path(tmp_dir), use_temp=True)

    print("\n📊 DIAGNOSTIC RESULTS:")
    print(f"   Existing Profile: {'✅ OK' if success_real else '❌ BROKEN'}")
    print(f"   Fresh Profile:    {'✅ OK' if success_temp else '❌ BROKEN'}")

    if not success_real and success_temp:
        print("\n💡 CONCLUSION: Your profile data is corrupted. We should backup and reset '.whisk-profile'.")
    elif not success_temp:
        print("\n💡 CONCLUSION: Chrome or Playwright environment is broken. Reinstall Chrome or check flags.")

if __name__ == "__main__":
    asyncio.run(main())
