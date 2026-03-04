import asyncio
import os
import sys
import logging
from pathlib import Path

# Configure logging to see grok_agent output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from packages.services.grok_agent import GrokAnimator

async def test_dual_pass():
    print("Starting Grok Dual-Pass Unit Test...")
    
    # Check for test image
    image_path = Path("test_image.png").absolute()
    if not image_path.exists():
        print(f"Error: Test image not found at {image_path}")
        return

    animator = GrokAnimator()
    
    # Test Parameters
    motion_prompt = "Slow lateral tracking shot across the plaza from left to right. Young fairies stand tall and proud, wings fanning slightly."
    style_suffix = "Pixar 3D style, soft lighting, cute aesthetic"
    
    try:
        print(f"Animating image: {image_path.name}")
        print(f"Prompt: {motion_prompt}")
        
        # Trigger the animation
        # This should now follow the Seed -> Extend -> Refine flow automatically
        video_path = await animator.animate(
            image_path=image_path,
            motion_prompt=motion_prompt,
            style_suffix=style_suffix,
            duration=6,
            aspect_ratio="16:9", # Landscape for wide shot
            resolution="480p",   # NEW: Verification at 480p
            needs_extend=True,
            extend_duration="6s"
        )
        
        if video_path and video_path.exists():
            print(f"SUCCESS! Generated video: {video_path}")
            print(f"Size: {video_path.stat().st_size} bytes")
        else:
            print("FAILED: No video path returned or file missing.")
            
    except Exception as e:
        print(f"CRASHED during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dual_pass())
