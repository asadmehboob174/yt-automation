"""
Quick test: generate a 10s clip then extend it by 6s → total 16s.
Uses a real image from tmp/characters and calls generate_single_clip directly.
"""
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from packages.services.grok_agent import generate_single_clip

IMAGE_PATH = Path(__file__).parent / "tmp/characters/pets/blue_fairy_neeli.png"

async def main():
    print("\n" + "="*60)
    print("TEST: generate 10s clip + extend by 6s => 16s total")
    print("="*60 + "\n")

    if not IMAGE_PATH.exists():
        print(f"❌ Image not found: {IMAGE_PATH}")
        return

    output = await generate_single_clip(
        image_path=IMAGE_PATH,
        character_pose="standing, arms slightly open",
        camera_angle="medium shot",
        style_suffix="cinematic, soft glow, fairy tale",
        motion_description="gentle floating movement, wings fluttering, sparkles around her",
        character_name="Neeli",
        emotion="joyfully",
        duration="10s",
        aspect="9:16",
        resolution="480p",
        needs_extend=True,
        extend_duration="6s",
    )

    print(f"\n✅ Output file: {output}")
    print(f"   Size: {output.stat().st_size:,} bytes")

    # Check duration with ffprobe if available
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(output)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip())
        print(f"   Duration: {duration:.1f}s (expected ~16s)")
        if duration >= 14:
            print("✅ PASS: Video is extended!")
        else:
            print(f"⚠️  WARNING: Duration {duration:.1f}s is shorter than expected 16s")
    except Exception as e:
        print(f"   (ffprobe not available to verify duration: {e})")

if __name__ == "__main__":
    asyncio.run(main())
