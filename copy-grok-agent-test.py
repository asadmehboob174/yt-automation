
import asyncio
import logging
import sys
from pathlib import Path

# Add root to path
sys.path.append(str(Path.cwd()))

from packages.services.grok_agent import GrokAnimator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_locks():
    profile = Path.home() / ".grok-profile"
    locks = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock in locks:
        lock_path = profile / lock
        if lock_path.exists():
            try:
                lock_path.unlink()
                logger.info(f"🧹 Removed stale lock: {lock}")
            except Exception as e:
                logger.warning(f"Failed to remove lock {lock}: {e}")

async def test_generation(image_path_str):
    clean_locks()
    image_path = Path(image_path_str)
    if not image_path.exists():
        logger.error(f"Image not found: {image_path}")
        return

    logger.info(f"🚀 Starting Test Generation with: {image_path.name}")
    animator = GrokAnimator()
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        # We'll just run a single animation and see if it waits correctly
        # The GrokAnimator has internal logging that we should see in stdout
        # The user provided a specific complex prompt for LEO
        complex_prompt = (
            "Animate with building dread. [LEO] still running but head twisted looking backward over shoulder. "
            "Eyes dart, tracking movement in darkness. Expression transitions from fear to absolute terror. "
            "Mouth opens wider in horror. In background: the tall dark silhouette MOVES - shifts position between trees, "
            "gets slightly closer (advancing), moves with unnatural stuttering motion. Silhouette's eyes suddenly glow "
            "faint amber for 1 second. Leo's pupil dilates. Snowball trembles harder, ears flatten back. Fog swirls ominously. "
            "At 3-second mark: Leo's eyes go even wider - realization that it's RIGHT THERE."
        )
        
        result = await animator.animate(
            image_path=image_path,
            motion_prompt=complex_prompt,
            duration=10, # Longer duration for complex prompt
            style_suffix="Spooky 2D Cartoon"
        )
        
        end_time = asyncio.get_event_loop().time()
        duration_taken = end_time - start_time
        
        logger.info(f"✅ Test Complete! Result: {result}")
        logger.info(f"⏱️ Total Time Taken: {duration_taken:.2f} seconds")
        
        if result and result.exists():
            size = result.stat().st_size
            logger.info(f"📁 File Size: {size/1024:.2f} KB")
            
            # Validation using ffprobe if available
            try:
                import subprocess
                # Check for ffprobe
                subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                logger.info("🎬 Validating video file with ffprobe...")
                cmd = [
                    "ffprobe", 
                    "-v", "error", 
                    "-show_entries", "format=duration", 
                    "-of", "default=noprint_wrappers=1:nokey=1", 
                    str(result)
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                video_duration = float(proc.stdout.strip())
                logger.info(f"🎞️ Video Duration: {video_duration} seconds")
                
                if video_duration < 1:
                    logger.error("❌ Video is too short! Invalid file.")
                else:
                    logger.info("✅ Video content validity confirmed.")
                    
            except FileNotFoundError:
                logger.warning("⚠️ ffprobe not found in PATH, skipping deep validation.")
            except Exception as e:
                logger.error(f"❌ Video validation failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_grok_fix.py <image_path>")
    else:
        asyncio.run(test_generation(sys.argv[1]))