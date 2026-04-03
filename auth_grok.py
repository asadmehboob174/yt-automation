import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path
import sys
import argparse
import subprocess
import shutil

def kill_chrome():
    """Kill any hanging chrome processes that might lock the profile."""
    print("🔪 Killing any existing Chrome/Chromium processes...")
    try:
        # /F = Force, /T = Task Tree (kills children), /IM = Image Name
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["taskkill", "/F", "/IM", "chromium.exe", "/T"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

async def main():
    parser = argparse.ArgumentParser(description="Grok Authentication Script")
    parser.add_argument("--no-ext", action="store_true", help="Skip extension loading and prompts")
    parser.add_argument("--ext-paths", type=str, help="Comma-separated paths to unpacked extensions")
    parser.add_argument("--reset", action="store_true", help="Wipe the existing profile and start fresh")
    args_cli = parser.parse_args()

    profile_dir = Path.home() / ".grok-profile"
    
    # 1. Kill any zombie processes first
    kill_chrome()

    # 2. Handle Reset
    if args_cli.reset and profile_dir.exists():
        print(f"🧹 Resetting profile: {profile_dir}")
        try:
            shutil.rmtree(profile_dir)
            print("✅ Profile wiped successfully.")
        except Exception as e:
            print(f"❌ Could not wipe profile: {e}. It might still be in use.")

    extension_paths = []

    if args_cli.no_ext:
        print("\n🚀 Skipping extensions as requested by --no-ext")
    else:
        print("\n🧩 Grok Extension & Developer Mode")
        print("---------------------------------------")
        
        paths_input = ""
        if args_cli.ext_paths:
            paths_input = args_cli.ext_paths
            print(f"Using extensions from CLI: {paths_input}")
        else:
            print("Please provide the paths to your unpacked extensions (folders).")
            print("Example: C:\\Users\\pc\\Downloads\\Ex 01, C:\\Users\\pc\\Downloads\\Ex 02")
            print("💡 TIP: Press Enter to skip and login WITHOUT extensions.")
            
            paths_input = input("\nExtension Path(s): ").strip()
        
        if paths_input:
            raw_paths = [p.strip().replace('"', '') for p in paths_input.split(',')]
            for p in raw_paths:
                full_path = os.path.abspath(p)
                if os.path.isdir(full_path):
                    extension_paths.append(full_path)
                else:
                    print(f"⚠️ Warning: Path not found: {full_path}")

    print(f"\n🚀 Launching browser with DEVELOPER MODE active...")
    print(f"📁 Profile: {profile_dir}")
    
    # Advanced flags for stability
    browser_args = [
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
        "--no-first-run",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--remote-debugging-port=9222"
    ]
    
    if extension_paths:
        load_arg = ",".join(extension_paths)
        browser_args.append(f"--disable-extensions-except={load_arg}")
        browser_args.append(f"--load-extension={load_arg}")

    async with async_playwright() as p:
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=browser_args,
                ignore_default_args=["--enable-automation"]
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Additional tab for extensions if needed
            ext_page = await context.new_page()
            await ext_page.goto("chrome://extensions/")
            
            await page.bring_to_front()
            await page.goto("https://grok.com/imagine")
            
            print("\n" + "="*65)
            print("🔓 BROWSER OPEN: Please log in to Grok manually.")
            print("✅ Once ready, CLOSE THE WINDOW to save the session.")
            print("="*65 + "\n")
            
            while True:
                try:
                    if not context.pages:
                        break
                except: 
                    break
                await asyncio.sleep(1)
                
            await context.close()
            print("✨ Session saved!")
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {e}")
            print("💡 TIP: Try running with 'python auth_grok.py --reset --no-ext'")

if __name__ == "__main__":
    asyncio.run(main())
