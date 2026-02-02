
"""
Test Script for Native Whisk Batch Generation.
Demonstrates "Run on this Project" behavior by reusing one tab.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.services.whisk_agent import WhiskAgent

async def run_batch_test():
    print("🚀 Initializing Native Whisk Agent (Version 'Stable Revert')...")
    agent = WhiskAgent(headless=False)
    
    # Create a dummy character file for testing sidebar verify
    dummy_char = Path("test_char.txt")
    with open(dummy_char, "w") as f:
        f.write("dummy image content")
    
    prompts = [
        "A red apple on a wooden table, cinematic lighting",
        "A futuristic blue car driving on a neon road, cyberpunk style"
    ]
    
    print(f"📋 Loaded {len(prompts)} prompts for Batch Test.")
    print("👉 Watch the browser! It SHOULD open the sidebar (Add Image) now.")
    
    try:
        results = await agent.generate_batch(
            prompts=prompts,
            is_shorts=False, # 16:9
            style_suffix="high quality 3d render",
            delay_seconds=10,
            character_paths=[dummy_char] # Passing a character triggers the logic
        )
        print(f"✅ Batch Complete. Generated {len(results)} images.")
    except Exception as e:
        print(f"❌ Batch Failed: {e}")
    finally:
        # cleanup
        if dummy_char.exists():
            dummy_char.unlink()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_batch_test())
