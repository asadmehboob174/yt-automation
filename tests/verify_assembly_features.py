import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from packages.services.video_editor import FFmpegVideoEditor
from packages.services.audio_engine import AudioEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_assembly():
    editor = FFmpegVideoEditor()
    audio = AudioEngine()
    
    output_dir = Path("tests/output/assembly_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    editor.output_dir = output_dir
    audio.output_dir = output_dir

    print("🎥 1. Creating Dummy Content...")
    # Create dummy video clips
    clip1 = output_dir / "clip1.mp4"
    clip2 = output_dir / "clip2.mp4"
    
    os.system(f"ffmpeg -y -f lavfi -i testsrc=duration=5:size=1920x1080:rate=30 -c:v libx264 {clip1} > NUL 2>&1")
    os.system(f"ffmpeg -y -f lavfi -i testsrc=duration=5:size=1920x1080:rate=30 -vf hue=s=0 {clip2} > NUL 2>&1")
    
    # Create dummy audio
    audio1 = output_dir / "music1.mp3"
    audio2 = output_dir / "music2.mp3"
    os.system(f"ffmpeg -y -f lavfi -i sine=f=440:d=10 -c:a libmp3lame {audio1} > NUL 2>&1")
    os.system(f"ffmpeg -y -f lavfi -i sine=f=880:d=10 -c:a libmp3lame {audio2} > NUL 2>&1")

    print("\n🪧 2. Testing Title Cards...")
    try:
        opener = editor.render_title_card("THE HORROR BEGINS", style="horror", output_path=output_dir / "opener.mp4")
        print(f"✅ Opener generated: {opener}")
    except Exception as e:
        print(f"❌ Title card failed: {e}")

    print("\n🎨 3. Testing Color Grading...")
    try:
        graded = editor.apply_color_grading(clip1, {"overall_look": "desaturated horror"}, output_path=output_dir / "graded.mp4")
        print(f"✅ Grading applied: {graded}")
    except Exception as e:
        print(f"❌ Grading failed: {e}")

    print("\n🎵 4. Testing Dynamic Soundtrack...")
    try:
        segments = [
            {"path": audio1, "duration": 5.0},
            {"path": audio2, "duration": 5.0}
        ]
        soundtrack = audio.construct_dynamic_soundtrack(segments, total_duration=10.0, output_path=output_dir / "dyn_soundtrack.mp3")
        print(f"✅ Soundtrack constructed: {soundtrack}")
    except Exception as e:
        print(f"❌ Soundtrack failed: {e}")

    print("\n✂️ 5. Testing Stitching with Transitions...")
    try:
        clips = [opener, clip1, clip2]
        stitched = editor.stitch_clips_with_transitions(clips, output_dir / "final_stitch.mp4", transition_duration=0.5)
        print(f"✅ Stitched video: {stitched}")
    except Exception as e:
        print(f"❌ Stitching failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_assembly())
