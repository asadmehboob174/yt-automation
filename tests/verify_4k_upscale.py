import os
import sys
from pathlib import Path
import ffmpeg
import logging

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from packages.services.video_editor import FFmpegVideoEditor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_resolution(video_path: Path, expected_res: tuple[int, int]):
    """Probe video resolution using ffprobe."""
    probe = ffmpeg.probe(str(video_path))
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    
    if not video_stream:
        raise ValueError("No video stream found")
        
    width = int(video_stream['width'])
    height = int(video_stream['height'])
    
    logger.info(f"Video Resolution: {width}x{height}")
    
    if (width, height) == expected_res:
        logger.info(f"✅ Resolution matches expected {expected_res[0]}x{expected_res[1]}!")
        return True
    else:
        logger.error(f"❌ Resolution {width}x{height} does NOT match expected {expected_res[0]}x{expected_res[1]}!")
        return False

def test_upscale():
    editor = FFmpegVideoEditor()
    
    # Create a small dummy video for testing if none exists
    # Or use an existing video if available.
    # For CI and local tests, we'll try to find a small mp4 in the project
    test_video = Path("tests/test_assets/small.mp4")
    
    if not test_video.exists():
        logger.info("Generating dummy 480p video for testing...")
        test_video.parent.mkdir(parents=True, exist_ok=True)
        (
            ffmpeg
            .input('color=c=blue:s=640x480:d=1', f='lavfi')
            .output(str(test_video), vcodec='libx264', t=1)
            .overwrite_output()
            .run(quiet=True)
        )

    # Test Long Format (Landscape 4K)
    logger.info("Testing Landscape 4K Upscale...")
    landscape_4k = (3840, 2160)
    output_landscape = editor.upscale_video(test_video, target_resolution=landscape_4k)
    verify_resolution(output_landscape, landscape_4k)
    
    # Test Shorts Format (Portrait 4K)
    logger.info("Testing Portrait 4K Upscale...")
    portrait_4k = (2160, 3840)
    output_portrait = editor.upscale_video(test_video, target_resolution=portrait_4k)
    verify_resolution(output_portrait, portrait_4k)

if __name__ == "__main__":
    test_upscale()
