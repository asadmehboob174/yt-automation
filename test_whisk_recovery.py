
import asyncio
import os
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(os.getcwd()) / "packages"))

from services.whisk_agent import WhiskAgent

async def test_recovery():
    print("[TEST] Starting Whisk Session Recovery Test...")
    agent = WhiskAgent(headless=False)
    
    try:
        # 1. Generate first image
        print("\n[STEP 1] Generating first image (Scene 1)...")
        img1 = await agent.generate_image("A futuristic city", is_shorts=True)
        if img1:
            print("[SUCCESS] Scene 1 Success!")
        
        # 2. Simulate browser crash/close
        print("\n[STEP 2] Simulating browser closure...")
        if agent.browser:
            await agent.browser.close()
        print("Done. Browser Context is now closed.")
        
        # 3. Generate thumbnail (should recover)
        print("\n[STEP 3] Generating thumbnail (Recovery Test)...")
        # setup_done=True simulates that we think we are in a batch
        thumb = await agent.generate_image("Cinematic movie poster", is_shorts=False, skip_setup=True)
        
        if thumb:
            print("[SUCCESS] Thumbnail Success! Recovery worked.")
            with open("test_thumb.png", "wb") as f:
                f.write(thumb)
            print("Saved to test_thumb.png")
        else:
            print("[ERROR] Thumbnail generation failed.")
            
    except Exception as e:
        print(f"[ERROR] Test encountered an error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()
        print("\n[STOP] Test complete.")

if __name__ == "__main__":
    # Ensure Windows policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_recovery())
