
import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path
import sys

async def main():
    profile_dir = Path.home() / ".grok-profile"
    
    print("\n🧩 Grok Extension & Developer Mode")
    print("---------------------------------------")
    print("Please provide the paths to your unpacked extensions (folders).")
    print("Example: C:\\Users\\pc\\Downloads\\Ex 01, C:\\Users\\pc\\Downloads\\Ex 02")
    
    paths_input = input("\nExtension Path(s): ").strip()
    
    extension_paths = []
    if paths_input:
        # Split by comma and clean up quotes/whitespace
        raw_paths = [p.strip().replace('"', '') for p in paths_input.split(',')]
        for p in raw_paths:
            full_path = os.path.abspath(p)
            if os.path.isdir(full_path):
                extension_paths.append(full_path)
            else:
                print(f"⚠️ Warning: Path not found: {full_path}")

    print(f"\n🚀 Launching browser with DEVELOPER MODE active...")
    print(f"📁 Profile: {profile_dir}")
    
    # Advanced flags to "un-crip" the browser for developers
    args = [
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
        "--no-first-run",
        "--enable-extension-apps",
        "--allow-legacy-extension-manifests",
    ]
    
    if extension_paths:
        print(f"✅ Auto-loading {len(extension_paths)} extension(s)...")
        load_arg = ",".join(extension_paths)
        args.append(f"--disable-extensions-except={load_arg}")
        args.append(f"--load-extension={load_arg}")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            ignore_default_args=["--enable-automation"], # This helps keep Dev Mode stable
            args=args
        )
        
        # Reuse the first page if it exists (persistent context often opens one)
        if len(context.pages) > 0:
            page = context.pages[0]
        else:
            page = await context.new_page()
            
        # Open extension management in a background tab just in case they need it
        ext_page = await context.new_page()
        await ext_page.goto("chrome://extensions/")
        
        # Go back to Grok
        await page.bring_to_front()
        await page.goto("https://grok.com/imagine")
        
        print("\n" + "="*65)
        print("🔓 DEVELOPER MODE: The browser is now open in developer-friendly mode.")
        print("🛠️  Check the 'Extensions' tab to ensure your tools are ON.")
        print("✅ Once ready, CLOSE THE BROWSER WINDOW to save the session.")
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
