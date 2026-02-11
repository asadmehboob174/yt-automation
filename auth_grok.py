
import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path
import sys

async def main():
    profile_dir = Path.home() / ".grok-profile"
    
    print("\n🚀 Grok Authentication Setup")
    print("---------------------------------------")
    print("Select an option:")
    print("1. Direct Login (Quick - No Extensions)")
    print("2. Developer Mode (Load Custom Extensions)")
    
    try:
        choice = input("\nEnter choice [1 or 2, default 1]: ").strip() or "1"
    except EOFError:
        choice = "1"

    extension_paths = []
    args = [
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
    ]

    if choice == "2":
        print("\n🧩 Developer Mode - Extension Setup")
        print("Please provide paths to your unpacked extensions (folders), separated by commas.")
        try:
            paths_input = input("Extension Path(s) [Press Enter to skip]: ").strip()
        except EOFError:
            paths_input = ""
            
        if paths_input:
            raw_paths = [p.strip().replace('"', '') for p in paths_input.split(',')]
            for p in raw_paths:
                full_path = os.path.abspath(p)
                if os.path.isdir(full_path):
                    extension_paths.append(full_path)
                else:
                    print(f"⚠️ Warning: Path not found: {full_path}")

        # Extra flags for developer mode with extensions
        args.extend([
            "--no-sandbox",
            "--disable-infobars",
            "--no-first-run",
            "--enable-extension-apps",
            "--allow-legacy-extension-manifests",
        ])
        
        if extension_paths:
            print(f"✅ Auto-loading {len(extension_paths)} extension(s)...")
            load_arg = ",".join(extension_paths)
            args.append(f"--disable-extensions-except={load_arg}")
            args.append(f"--load-extension={load_arg}")
    else:
        print("\n⚡ Launching Direct Login mode...")

    print(f"📁 Profile: {profile_dir}")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            ignore_default_args=["--enable-automation"] if choice == "2" else None,
            args=args
        )
        
        # Reuse page or create new
        page = context.pages[0] if context.pages else await context.new_page()
            
        if choice == "2":
            # Open extension management in a background tab
            ext_page = await context.new_page()
            await ext_page.goto("chrome://extensions/")
            await page.bring_to_front()
        
        await page.goto("https://grok.com/imagine")
        
        print("\n" + "="*65)
        print("🔓 ACTION REQUIRED: Please log in to Grok in the browser window.")
        if choice == "2":
            print("🛠️  Check the 'Extensions' tab to ensure your tools are ON.")
        print("✅ Once logged in, CLOSE THE BROWSER WINDOW to save the session.")
        print("="*65 + "\n")
        
        while True:
            try:
                if context.pages == []:
                    break
            except: 
                break
            await asyncio.sleep(1)
            
        await context.close()
        print("✨ Session saved!")

if __name__ == "__main__":
    asyncio.run(main())
