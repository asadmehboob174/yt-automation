
import asyncio
import os
import sys
import logging
from pathlib import Path

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from packages.services.whisk_agent import WhiskAgent

async def run_integration_test():
    test_img = Path("test_char.png")
    if not test_img.exists():
        print("X Test image not found!")
        return

    agent = WhiskAgent(headless=False)
    try:
        print("Starting WhiskAgent integration test...")
        # We use a dummy prompt
        img_bytes = await agent.generate_image(
            prompt="A blue square on a white background",
            character_paths=[test_img.absolute()]
        )
        
        if img_bytes:
            print(f"SUCCESS! Generated {len(img_bytes)} bytes.")
        else:
            print("FAILED: No image bytes returned.")
            
    except Exception as e:
        print(f"Integration Test Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(run_integration_test())
