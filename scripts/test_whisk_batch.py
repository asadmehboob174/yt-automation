
"""
Test Script for Native Whisk Batch Generation.
Demonstrates "Run on this Project" behavior by reusing one tab.
"""
import asyncio
import sys
import os

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.services.whisk_agent import WhiskAgent

async def run_batch_test():
    print("🚀 Initializing Native Whisk Agent (Version 'Auto-Whisk-Killer')...")
    agent = WhiskAgent(headless=False)
    
    prompts = [
        "A red apple on a wooden table, cinematic lighting",
        "A futuristic blue car driving on a neon road, cyberpunk style"
    ]
    
    print(f"📋 Loaded {len(prompts)} prompts for Batch Test.")
    print("👉 Watch the browser! It will reuse the SAME tab (Run on this Project mode).")
    
    results = await agent.generate_batch(
        prompts=prompts,
        is_shorts=False, # 16:9
        style_suffix="high quality 3d render",
        delay_seconds=5
    )
    
    print(f"✅ Batch Complete. Generated {len(results)} images.")
    
if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_batch_test())
