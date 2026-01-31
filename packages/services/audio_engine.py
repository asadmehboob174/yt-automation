"""
Audio Engine - TTS and Sidechain Compression.

Generates narration using Edge-TTS and mixes audio
with sidechain compression to duck background music.
"""
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import edge_tts

logger = logging.getLogger(__name__)


class AudioEngine:
    """Generate narration and mix audio with sidechain compression."""
    
    def __init__(self, voice_id: str = "en-US-AriaNeural"):
        self.voice_id = voice_id
        self.output_dir = Path(tempfile.mkdtemp())
    
    async def generate_narration(
        self,
        text: str,
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate TTS narration using Edge-TTS."""
        output_path = output_path or self.output_dir / "narration.mp3"
        
        communicate = edge_tts.Communicate(text, self.voice_id)
        await communicate.save(str(output_path))
        
        logger.info(f"✅ Generated narration -> {output_path.name}")
        return output_path
    
    def mix_with_sidechain_compression(
        self,
        narration_path: Path,
        music_path: Path,
        output_path: Optional[Path] = None,
        music_volume: float = 0.3,
        duck_amount: float = 0.7
    ) -> Path:
        """
        Mix narration with background music using sidechain compression.
        This automatically ducks the music when narration is playing.
        """
        output_path = output_path or self.output_dir / "mixed_audio.mp3"
        
        # FFmpeg sidechain compression filter
        # threshold: when to start ducking
        # ratio: how much to duck
        # attack/release: how fast to duck/recover
        sidechain_filter = (
            f"[1:a]volume={music_volume}[music];"
            f"[music][0:a]sidechaincompress="
            f"threshold=0.02:ratio=8:attack=50:release=500:level_sc=1"
            f"[ducked];"
            f"[0:a][ducked]amix=inputs=2:duration=longest"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(narration_path),
            "-i", str(music_path),
            "-filter_complex", sidechain_filter,
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        logger.info(f"✅ Mixed audio with sidechain compression -> {output_path.name}")
        return output_path
    
    def extract_audio_from_clip(
        self,
        video_path: Path,
        output_path: Optional[Path] = None
    ) -> Path:
        """Extract audio stream from a Grok-generated clip."""
        output_path = output_path or self.output_dir / f"{video_path.stem}_audio.mp3"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",  # No video
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        logger.info(f"✅ Extracted audio -> {output_path.name}")
        return output_path
    
    def mix_all_tracks(
        self,
        narration_path: Path,
        clip_audio_paths: list[Path],
        music_path: Path,
        output_path: Optional[Path] = None,
        music_volume: float = 0.2
    ) -> Path:
        """
        Mix narration, Grok clip audio, and background music.
        Preserves dialogue from Grok clips while ducking music.
        """
        output_path = output_path or self.output_dir / "final_audio.mp3"
        
        # First merge all clip audio
        if clip_audio_paths:
            concat_file = self.output_dir / "audio_concat.txt"
            with open(concat_file, "w") as f:
                for audio in clip_audio_paths:
                    f.write(f"file '{audio.absolute()}'\n")
            
            merged_clips = self.output_dir / "merged_clips.mp3"
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c:a", "libmp3lame",
                str(merged_clips)
            ], check=True, capture_output=True)
        else:
            merged_clips = None
        
        # Now mix with sidechain
        if merged_clips:
            # Mix narration + clips first, then duck music
            temp_mix = self.output_dir / "temp_mix.mp3"
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(narration_path),
                "-i", str(merged_clips),
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest",
                "-c:a", "libmp3lame",
                str(temp_mix)
            ], check=True, capture_output=True)
            
            return self.mix_with_sidechain_compression(
                temp_mix, music_path, output_path, music_volume
            )
        else:
            return self.mix_with_sidechain_compression(
                narration_path, music_path, output_path, music_volume
            )
