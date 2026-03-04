import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(r'd:\GitHub\yt-automation')))

from packages.services.video_editor import FFmpegVideoEditor

async def test_stitch():
    editor = FFmpegVideoEditor(output_dir=Path('./tmp_test_stitch'))
    
    # create 10 dummy clips (5s each) using ffmpeg if they don't exist
    import subprocess
    clips = []
    for i in range(13):
        p = Path(f'./tmp_test_stitch/dummy_{i}.mp4')
        if not p.exists():
            # Create a 5s dummy video with sine wave audio
            subprocess.run([
                editor.ffmpeg_cmd, '-y',
                '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:d=5',
                '-f', 'lavfi', '-i', f'sine=frequency={440+i*10}:duration=5',
                '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
                str(p)
            ], check=True)
        clips.append(p)
        
    # simulate the target lengths from the user's log
    target_durs = [7.24, 8.72, 4.98, 9.73, 14.41, 9.04, 6.64, 4.28, 9.52, 4.98, 8.22, 9.40, 3.78]
    
    print("🎬 Running stitch_clips_with_fade...")
    try:
        stitched = editor.stitch_clips_with_fade(
            clips,
            output_path=Path('./tmp_test_stitch/stitched_out.mp4'),
            fade_duration=0.3,
            target_resolution=(1280, 720),
            mute_audio=False,
            target_durations=target_durs
        )
        print(f"✅ Success: {stitched}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_stitch())
