
import subprocess
import logging
import shutil
import os
from pathlib import Path
from typing import Optional, Tuple
from .audio_separator import AudioSeparator

logger = logging.getLogger(__name__)

class VoiceExtractor:
    """
    Extracts high-quality vocals from video files for AI voice cloning.
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("packages/assets/voices")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.separator = AudioSeparator()
        
        # FFmpeg configuration
        import os
        self.ffmpeg_cmd = os.getenv("FFMPEG_PATH", "ffmpeg")

    def extract_vocals(self, video_path: Path, character_name: str) -> Optional[Path]:
        """
        1. Extract audio from video.
        2. Separate vocals from background.
        3. Save clean vocals mp3.
        """
        if not video_path.exists():
            logger.error(f"❌ Video file not found: {video_path}")
            return None
            
        safe_name = character_name.lower().replace(" ", "_")
        raw_audio = self.output_dir / f"{safe_name}_raw.mp3"
        final_vocals = self.output_dir / f"{safe_name}_vocals.mp3"
        
        # 1. Extract Raw Audio
        logger.info(f"🎙️ Extracting raw audio from: {video_path.name}")
        try:
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-i', str(video_path),
                '-vn', # No video
                '-acodec', 'libmp3lame',
                '-q:a', '2',
                str(raw_audio)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as e:
            logger.error(f"❌ FFmpeg extraction failed: {e}")
            return None

        # 2. Separate Vocals (Demucs)
        if self.separator.client:
            logger.info("✂️ Running Demucs vocal separation...")
            _, vocals_path = self.separator.separate_audio(raw_audio)
            if vocals_path and vocals_path.exists():
                # Convert Demucs output to final MP3 location
                shutil_copy = True
                try:
                    import shutil
                    shutil.move(str(vocals_path), str(final_vocals))
                    logger.info(f"✅ Clean vocals saved: {final_vocals}")
                    # Cleanup raw
                    if raw_audio.exists(): raw_audio.unlink()
                    return final_vocals
                except Exception as e:
                    logger.error(f"❌ Failed to move vocal file: {e}")
        
        logger.warning("⚠️ Vocal separation skipped or failed. Using raw extraction.")
        return raw_audio
