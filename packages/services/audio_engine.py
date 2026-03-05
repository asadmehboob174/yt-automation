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
from typing import Optional, Union

import edge_tts
import shutil
import os
from dotenv import load_dotenv
from .cloud_storage import R2Storage

load_dotenv()

logger = logging.getLogger(__name__)


class AudioEngine:
    """Generate narration and mix audio with sidechain compression."""
    
    def __init__(self, voice_id: str = "en-US-AriaNeural"):
        self.voice_id = voice_id
        self.output_dir = Path(tempfile.mkdtemp())
        self.ffmpeg_cmd = os.getenv("FFMPEG_PATH", "ffmpeg")
    
    async def generate_narration(
        self,
        text: str,
        voice_id: str = "en-US-AriaNeural",
        provider: str = "edge-tts", # edge-tts, elevenlabs, xtts
        reference_audio: Optional[Union[Path, str]] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Generate narration with cascading priority:
        1. ElevenLabs (If API Key + Voice ID provided)
        2. XTTS (If Reference Audio provided)
        3. Edge-TTS (Reliable Fallback)
        """
        output_path = output_path or self.output_dir / f"narration_final.mp3"
        if isinstance(output_path, str): output_path = Path(output_path)
        
        # If reference_audio is a string (from DB), convert to Path
        if reference_audio and isinstance(reference_audio, str):
            reference_audio = Path(reference_audio)

        # 1. Pre-process text
        text = self._preprocess_prompt(text)
        is_arabic_script = any('\u0600' <= c <= '\u06FF' for c in text)
        is_path_voice = (":" in voice_id or "/" in voice_id or "\\" in voice_id)
        
        # 2. Try ElevenLabs Priority
        eleven_api_key = os.getenv("ELEVENLABS_API_KEY")
        # Removed the 'not is_arabic_script' block so ElevenLabs can process Urdu
        if eleven_api_key and not is_path_voice:
            try:
                logger.info(f"💎 Attempting ElevenLabs (Priority) for voice: {voice_id}")
                return await self._generate_elevenlabs(text, voice_id, output_path)
            except Exception as e:
                logger.warning(f"⚠️ ElevenLabs failed: {e}. Moving to XTTS/Edge fallback.")

        # 3. Try XTTS Priority
        if reference_audio:
            if isinstance(reference_audio, str): reference_audio = Path(reference_audio)
            try:
                logger.info(f"🎭 Attempting XTTS Cloning for reference: {reference_audio.name}")
                return await self._generate_xtts(text, reference_audio, output_path)
            except Exception as e:
                logger.warning(f"🧬 XTTS Cloning failed: {e}. Moving to Edge-TTS fallback.")

        # 4. Final Edge-TTS Fallback
        active_voice = voice_id
        
        # Detect if the voice_id is likely an ElevenLabs/XTTS ID (no dashes, or too long)
        # Edge-TTS voices always have the format 'lang-country-NameNeural'
        is_standard_edge = "-" in active_voice and "Neural" in active_voice
        
        if is_arabic_script:
             logger.info(f"🌐 Urdu script detected. Using Edge-TTS (ur-PK-UzmaNeural).")
             active_voice = "ur-PK-UzmaNeural"
        elif is_path_voice or not is_standard_edge:
             default_fallback = "en-GB-RyanNeural"
             logger.info(f"🔄 Voice ID '{active_voice}' incompatible with Edge-TTS. Defaulting to '{default_fallback}'.")
             active_voice = default_fallback
        
        try:
            logger.info(f"🛡️ Using Edge-TTS fallback: {active_voice}")
            communicate = edge_tts.Communicate(text, active_voice)
            await communicate.save(str(output_path))
            return output_path
        except Exception as e:
             logger.error(f"❌ Ultimate fallback failed: {e}")
             # Last ditch effort
             communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
             await communicate.save(str(output_path))
             return output_path

    def _preprocess_prompt(self, text: str) -> str:
        """
        Clean up emotional tags and sound effect markers for better TTS pacing.
        Example: "[breathing] Stop!" -> "... Stop!"
        """
        import re
        
        # 1. Convert tags in brackets to pauses (ellipses)
        # [gasp], [breathing], [laugh] -> ...
        text = re.sub(r'\[.*?\]', '...', text)
        
        # 2. Cleanup multiple ellipses (avoid too many dots)
        text = re.sub(r'\.{4,}', '...', text)
        
        # 3. Add a leading pause if it starts with ellipses
        if text.startswith('...'):
            text = "... " + text.lstrip('.')
            
        return text.strip()

    async def _generate_elevenlabs(self, text: str, voice_id: str, output_path: Path) -> Path:
        """Generate using ElevenLabs API."""
        import httpx
        
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY missing")
            
        # Using V1 endpoint for simplicity, but using V2 model for MUCH better quality
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2", # Upgraded to Multilingual V2 (Much better quality)
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
        
        # 1. Prepare & Upload to R2 so Gradio Space can download it (local paths won't work)
        try:
            # Convert to WAV for better compatibility with remote spaces (some require WAV explicitly)
            wav_ref = reference_audio.with_suffix(".wav")
            if not wav_ref.exists():
                logger.info(f"🔄 Converting {reference_audio.name} to WAV for compatibility...")
                conversion_cmd = [
                    self.ffmpeg_cmd, "-y",
                    "-i", str(reference_audio),
                    "-acodec", "pcm_s16le",
                    "-ar", "22050", # Common XTTS sample rate
                    "-ac", "1",
                    str(wav_ref)
                ]
                subprocess.run(conversion_cmd, check=True, capture_output=True)
            
            r2 = R2Storage()
            # Unique key for this voice reference
            remote_key = f"voices/refs/{wav_ref.name}"
            r2.upload(wav_ref, remote_key, content_type="audio/wav")
            reference_url = r2.get_url(remote_key)
            logger.info(f"📤 Uploaded WAV reference to R2. URL: {reference_url[:60]}...")
        except Exception as e:
            logger.warning(f"⚠️ R2 upload/conversion failed, falling back to local path: {e}")
            reference_url = str(reference_audio)

        # 2. Connect to a stable XTTS space
        # Trying a few known good ones for resilience
        spaces = [
            "hasanbasbunar/Voice-Cloning-XTTS-v2",
            "JymNils/Voice-Cloning-XTTS-v2",
            "ohmykush/coqui-XTTS-v2",
            "KaidenKama/coqui-XTTS-v2",
            "coqui/xtts" # Official but often down
        ]
        client = None
        hf_token = os.getenv("HF_TOKEN")
        
        for space_name in spaces:
            try:
                logger.info(f"🔄 Connecting to XTTS Space: {space_name}...")
                client = Client(space_name, token=hf_token)
                # Test connectivity with a tiny check if possible, or just assume ok if Client() works
                break
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect to {space_name}: {e}")
        
        if not client:
             raise RuntimeError("Could not connect to any XTTS provider Space")        
        
        # Map languages to the Literal strings expected by the Space
        lang_map = {
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "pl": "Polish",
            "tr": "Turkish",
            "ru": "Russian",
            "nl": "Dutch",
            "cs": "Czech",
            "ar": "Arabic",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "hu": "Hungarian",
            "hi": "Hindi"
        }
        
        # Detect language or use script detection
        is_arabic_script = any('\u0600' <= c <= '\u06FF' for c in text)
        if is_arabic_script:
            lang_name = "Arabic" # Arabic is supported by XTTS-v2 and shares script with Urdu
        else:
            try:
                from langdetect import detect
                lang_code = detect(text)
                lang_name = lang_map.get(lang_code, "English")
            except:
                lang_name = "English"

        # Try calling the synthesis endpoint
        try:
            result = client.predict(
                text,                       # text
                str(reference_url),         # reference_audio_url (Using R2 URL)
                None,                       # example_audio_name (Mutual exclusive with URL)
                lang_name,                  # language
                0.75,                       # temperature
                1.0,                        # speed
                True,                       # do_sample
                5.0,                        # repetition_penalty
                1.0,                        # length_penalty
                30,                         # gpt_cond_len
                50,                         # top_k
                0.85,                       # top_p
                True,                       # remove_silence_enabled
                -45,                        # silence_threshold
                300,                        # min_silence_len
                100,                        # keep_silence
                "Native XTTS splitting",     # text_splitting_method
                250,                        # max_chars_per_segment
                False,                      # enable_preprocessing
                api_name="/voice_clone_synthesis"
            )
        except Exception as e:
            logger.warning(f"XTTS /voice_clone_synthesis failed: {e}. Trying generic predict.")
            # Fallback to a simpler call if the space is different
            # Most spaces expect [text, language, ref_audio]
            result = client.predict(
                text,
                lang_name,
                str(reference_url),
                api_name="/predict"
            )

        # Result format for this space is typically just the audio filepath string
        # But some might return a tuple or a dict.
        if isinstance(result, str):
            audio_path = result
        elif isinstance(result, (list, tuple)) and len(result) > 0:
            # Check if it's (text, file) or just (file,)
            audio_path = result[1] if len(result) > 1 else result[0]
        elif isinstance(result, dict) and 'data' in result:
             audio_path = result['data'][0]
        else:
             audio_path = str(result)
             
        shutil.copy(audio_path, output_path)
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
