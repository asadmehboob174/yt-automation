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
        voice_id: str = "en-US-AriaNeural",
        provider: str = "edge-tts", # edge-tts, elevenlabs, xtts
        reference_audio: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate narration using specified provider."""
        output_path = output_path or self.output_dir / f"narration_{provider}.mp3"
        
        try:
            if provider == "elevenlabs":
                return await self._generate_elevenlabs(text, voice_id, output_path)
            elif provider == "xtts":
                return await self._generate_xtts(text, reference_audio, output_path)
            else:
                # Default to Edge TTS
                communicate = edge_tts.Communicate(text, voice_id)
                await communicate.save(str(output_path))
        except Exception as e:
            logger.error(f"TTS Provider {provider} failed: {e}. Fallback to EdgeTTS.")
            # Fallback
            communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
            await communicate.save(str(output_path))
            
        logger.info(f"✅ Generated narration ({provider}) -> {output_path.name}")
        return output_path

    async def _generate_elevenlabs(self, text: str, voice_id: str, output_path: Path) -> Path:
        """Generate using ElevenLabs API."""
        import os
        import httpx
        
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            logger.warning("ELEVENLABS_API_KEY missing, falling back...")
            raise ValueError("ELEVENLABS_API_KEY not found")
            
        # Using V1 endpoint for simplicity, V2 requires more payload structure
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=headers, timeout=60.0)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
                
        return output_path

    async def _generate_xtts(self, text: str, reference_audio: Optional[Path], output_path: Path) -> Path:
        """
        Generate using Coqui XTTS via HuggingFace Spaces (Free).
        Uses simple API call to a public space.
        """
        from gradio_client import Client
        import shutil
        
        if not reference_audio or not reference_audio.exists():
             raise ValueError("Reference audio required for XTTS cloning")
             
        logger.info(f"🧬 Cloning voice using XTTS (Cloud) with ref: {reference_audio.name}")
        
        # Connect to a stable XTTS space
        # 'coqui/xtts' is the official one, often busy. 
        # We try to use it with a timeout, or handle queue.
        client = Client("coqui/xtts") 
        
        # API parameters for coqui/xtts standard demo:
        # 1. Text (str)
        # 2. Language (str)
        # 3. Reference Audio (filepath)
        # 4. Mic Audio (filepath/null)
        # 5. Use Mic (bool)
        # 6. Cleanup (bool)
        # 7. No Auto-Detect (bool)
        # 8. Agree (bool)
        
        result = client.predict(
                text,	
                "en",	
                str(reference_audio),	
                None,	
                False,	
                False,	
                False,	
                True,	
                api_name="/predict" # Explicit API name is safer
        )
        
        # Result format for this space is typically (text_output, audio_filepath)
        # We need the second element
        generated_wav = result[1] 
        
        shutil.copy(generated_wav, output_path)
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
    def construct_dynamic_soundtrack(
        self,
        track_segments: list[dict],
        total_duration: float,
        output_path: Optional[Path] = None,
        crossfade_duration: float = 3.0
    ) -> Path:
        """
        Construct a continuous soundtrack from segments.
        track_segments: [{'path': Path, 'duration': float}] (ordered by time)
        """
        output_path = output_path or self.output_dir / "dynamic_soundtrack.mp3"
        
        if not track_segments:
             raise ValueError("No track segments provided")
        
        # 1. Prepare each segment (loop if needed, trim to duration)
        processed_segments = []
        for i, seg in enumerate(track_segments):
            seg_path = seg['path']
            target_dur = seg['duration']
            
            # Ensure file exists
            if not Path(seg_path).exists():
                logger.warning(f"⚠️ Music segment missing: {seg_path}")
                continue
                
            temp_seg = self.output_dir / f"seg_{i}.mp3"
            
            # Loop and Trim
            # -stream_loop -1 loops infinitely
            # -t trims to target duration
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", str(seg_path),
                "-t", str(target_dur),
                "-c:a", "libmp3lame",
                str(temp_seg)
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                processed_segments.append(temp_seg)
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to process segment {i}: {e}")
                
        if not processed_segments:
            raise ValueError("No valid music segments created")

        # 2. Stitch with crossfades
        # [0][1]acrossfade=d=3[a01];[a01][2]acrossfade=d=3[out]
        
        if len(processed_segments) == 1:
            import shutil
            shutil.copy(processed_segments[0], output_path)
            logger.info(f"✅ Created single-track soundtrack -> {output_path.name}")
            return output_path
            
        inputs = []
        filter_parts = []
        last_label = "[0]"
        
        for i in range(len(processed_segments)):
            inputs.extend(["-i", str(processed_segments[i])])
            
        for i in range(len(processed_segments) - 1):
            next_label = f"[{i+1}]"
            out_label = f"[af{i+1}]" if i < len(processed_segments) - 2 else "[out]"
            
            # Only crossfade if duration allows
            filter_parts.append(f"{last_label}{next_label}acrossfade=d={crossfade_duration}:c1=tri:c2=tri{out_label}")
            last_label = out_label
            
        filter_str = ";".join(filter_parts)
        
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-c:a", "libmp3lame",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"✅ Created dynamic soundtrack ({len(processed_segments)} segments) -> {output_path.name}")
        
        return output_path

    def remove_vocals(
        self,
        input_path: Path,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Use Demucs to separate audio and remove vocals.
        Keeps drums, bass, and other.
        """
        import shlex
        
        output_path = output_path or self.output_dir / f"{input_path.stem}_no_vocals.mp3"
        
        # Create a temp dir for demucs output
        demucs_out = self.output_dir / "demucs_out"
        demucs_out.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🧬 Separating audio (removing vocals) -> {input_path.name}")
        
        # Command: demucs --two-stems=vocals -n htdemucs -o {out_dir} {input_path}
        cmd = [
            "demucs",
            "--two-stems", "vocals",
            "-n", "htdemucs", 
            "-o", str(demucs_out),
            str(input_path)
        ]
        
        try:
            # Run Demucs
            subprocess.run(cmd, check=True, capture_output=False)
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Demucs failed: {e}")
            raise RuntimeError("Failed to separate audio")
        except FileNotFoundError:
             logger.error("❌ Demucs not found. Please pip install demucs")
             raise RuntimeError("Demucs not installed")
            
        # The output file should be at:
        # demucs_out/htdemucs/{input_filename_without_ext}/no_vocals.wav
        track_name = input_path.stem
        target_file = demucs_out / "htdemucs" / track_name / "no_vocals.wav"
        
        if not target_file.exists():
            # Fallback check
            found = list(demucs_out.rglob("no_vocals.wav"))
            if found:
                target_file = found[0]
            else:
                 raise FileNotFoundError(f"Demucs output not found at {target_file}")
        
        # Convert to mp3 and move to output_path
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(target_file),
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path)
        ], check=True, capture_output=True)
        
        logger.info(f"✅ Vocals removed -> {output_path.name}")
        return output_path
