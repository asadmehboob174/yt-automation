"""
FFmpeg Video Editor - High-Speed Rendering.

Provides fast video stitching, Ken Burns effect,
and subtitle burning using FFmpeg filter graphs.
"""
import ffmpeg
import logging
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FFmpegVideoEditor:
    """High-speed video editing using FFmpeg filter graphs."""
    
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(tempfile.mkdtemp())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Support custom FFmpeg paths from .env
        import os
        self.ffmpeg_cmd = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.ffprobe_cmd = os.getenv("FFPROBE_PATH", "ffprobe")
    
    def stitch_clips(
        self,
        clip_paths: list[Path],
        output_path: Optional[Path] = None
    ) -> Path:
        """Concatenate multiple clips into a single video."""
        if not clip_paths:
            raise ValueError("No clips provided")
        
        output_path = output_path or self.output_dir / "stitched.mp4"
        
        # Create concat file
        concat_file = self.output_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for clip in clip_paths:
                f.write(f"file '{clip.absolute()}'\n")
        
        # Run FFmpeg concat
        (
            ffmpeg
            .input(str(concat_file), format="concat", safe=0)
            .output(str(output_path), c="copy")
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )
        
        logger.info(f"✅ Stitched {len(clip_paths)} clips -> {output_path.name}")
        return output_path
    
    def stitch_clips_with_fade(
        self,
        clip_paths: list[Path],
        output_path: Optional[Path] = None,
        fade_duration: float = 0.4,
        target_resolution: tuple[int, int] = (1920, 1080)
    ) -> Path:
        """
        Stitch clips with smooth cross-dissolve (Mix) transitions and optional SFX.
        Uses FFmpeg 'xfade' filter for true blending overlap.
        """
        import subprocess
        
        if not clip_paths:
            raise ValueError("No clips provided")
        
        target_w, target_h = target_resolution
        output_path = output_path or self.output_dir / "stitched_mix.mp4"
        
        # Check for SFX
        sfx_path = Path(__file__).parent / "assets" / "sfx" / "whoosh.mp3"
        has_sfx = sfx_path.exists()
        
        # If single clip, just scale
        if len(clip_paths) == 1:
            self._scale_single(clip_paths[0], output_path, target_w, target_h)
            return output_path
        
        # 1. Validate inputs and get durations
        valid_clips = []
        durations = []
        for clip in clip_paths:
            try:
                probe = ffmpeg.probe(str(clip), cmd=self.ffprobe_cmd)
                dur = float(probe['format']['duration'])
                valid_clips.append(clip)
                durations.append(dur)
            except Exception as e:
                logger.warning(f"⚠️ Skipping invalid clip {clip.name}: {e}")
        
        if not valid_clips:
            raise ValueError("No valid clips found")
            
        count = len(valid_clips)
        
        # 2. Build Inputs & Scale Each Clip First
        # Xfade requires consistent timebases/resos, so we scale inputs in the chain before xfading.
        inputs = []
        filter_parts = []
        
        # Map SFX input if exists
        sfx_input_idx = count
        if has_sfx:
             # We add SFX as the last input
             pass 

        for i, clip in enumerate(valid_clips):
            inputs.extend(['-i', str(clip)])
            # Scale each input [i:v] -> [v{i}]
            filter_parts.append(
                f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},setsar=1[v{i}]"
            )
            # Audio: assume exists, map [i:a] -> [a{i}]
            # We must handle missing audio or mixed formats? 
            # For simplicity, we assume inputs have audio. If not, 'anullsrc' is needed.
            inputs_probe = ffmpeg.probe(str(clip), cmd=self.ffprobe_cmd)
            has_audio = any(s['codec_type'] == 'audio' for s in inputs_probe['streams'])
            if has_audio:
                filter_parts.append(f"[{i}:a]aresample=44100[a{i}]")
            else:
                filter_parts.append(f"anullsrc=r=44100:cl=stereo[a{i}]")

        # 3. Chain XFades
        # Loop: [v0][v1]xfade=...[v01]; [v01][v2]xfade...
        # We need to track the cumulative offset.
        # Offset for transition i (between clip i and i+1) = Sum(durations 0..i) - (i * overlap)
        
        current_v_label = "[v0]"
        current_a_label = "[a0]"
        
        current_offset = 0.0
        
        # Transition Timestamps (for SFX)
        transition_times = []
        
        for i in range(count - 1):
            # Duration of the 'current' clip (which might be a result of previous xfades)
            # But simpler logic: Xfade offset is relative to the START of the VIDEO.
            # Offset = (Duration(0) + Duration(1) + ... + Duration(i)) - (i+1)*Overlap ?
            # Wait.
            # Clip 0 starts at 0. Ends at D0.
            # Clip 1 starts at D0 - Overlap.
            # Clip 2 starts at (D0 + D1 - Overlap) - Overlap = D0 + D1 - 2*Overlap.
            
            # So, transition starts at:
            # T_offset = CurrentCumulativeDuration - Overlap?
            # No.
            # Let's track precise end time.
            
            clip_dur = durations[i]
            
            # The offset for xfade is relative to the first input of the pair? No, global timeline?
            # FFmpeg xfade `offset` is "timestamp of the start of transition".
            # For the first transition (v0 -> v1), offset = D0 - Fade.
            # For the second (v01 -> v2), offset = (D0 + D1 - Fade) - Fade?
            
            # Math:
            # Start time of Clip i in timeline = Sum(D_k for k<i) - i * Fade
            # Transition i (joining i and i+1) happens at: StartTime(i+1)
            # StartTime(i+1) = StartTime(i) + D_i - Fade
            
            if i == 0:
                current_offset = durations[0] - fade_duration
            else:
                current_offset += durations[i] - fade_duration
            
            transition_times.append(current_offset)
            
            next_v_label = f"[v{i+1}]"
            next_a_label = f"[a{i+1}]"
            
            out_v = f"[vm{i+1}]"
            out_a = f"[am{i+1}]"
            
            # Video XFade (Method: fade -> simple cross dissolve)
            filter_parts.append(
                f"{current_v_label}{next_v_label}xfade=transition=fade:duration={fade_duration}:offset={current_offset}{out_v}"
            )
            
            # Audio Crossfade (acrossfade)
            # doesn't use offset, it just overlaps end of A and start of B.
            # "c0 c1 acrossfade=d=0.5:c1=tri:c2=tri"
            filter_parts.append(
                f"{current_a_label}{next_a_label}acrossfade=d={fade_duration}:c1=tri:c2=tri{out_a}"
            )
            
            current_v_label = out_v
            current_a_label = out_a
        
        # 4. Inject SFX (Mix Effect)
        final_v_label = current_v_label
        final_a_label = current_a_label
        
        if has_sfx and transition_times:
            # Add SFX input
            inputs.extend(['-i', str(sfx_path)])
            sfx_idx = count # After all clip inputs
            
            # Split SFX
             # Reduce volume of WHOOSH sound to 8%
            sfx_copies = "".join([f"[sfx{k}]" for k in range(len(transition_times))])
            filter_parts.append(f"[{sfx_idx}:a]volume=0.08,asplit={len(transition_times)}{sfx_copies}")
            
            delayed_sfx = []
            for k, time in enumerate(transition_times):
                # Start SFX slightly before transition center?
                # Transition starts at 'time', lasts 'fade_duration'.
                # Center = time + fade/2.
                # SFX usually peak at center. 
                # Let's start it at time.
                delay_ms = int(time * 1000)
                filter_parts.append(f"[sfx{k}]adelay={delay_ms}|{delay_ms}[dsfx{k}]")
                delayed_sfx.append(f"[dsfx{k}]")
            
            # Mix
            all_audios = final_a_label + "".join(delayed_sfx)
            # Inputs = 1 (main) + N (sfx). normalize=0.
            filter_parts.append(f"{all_audios}amix=inputs={1 + len(delayed_sfx)}:duration=first:normalize=0[final_a_out]")
            final_a_label = "[final_a_out]"
            
        
        # COMMAND
        cmd = [self.ffmpeg_cmd, '-y'] + inputs + [
            '-filter_complex', ";".join(filter_parts),
            '-map', final_v_label,
            '-map', final_a_label,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-pix_fmt', 'yuv420p', # Ensure WMP/QuickTime compatibility
            '-c:a', 'aac', '-b:a', '192k',
            str(output_path)
        ]
        
        logger.info(f"🎬 Stitching {count} clips with XFADE (Mix) transition (d={fade_duration}s)...")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ Stitched (Mix) -> {output_path.name}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg Error: {e.stderr.decode('utf-8')}")
            # Fallback to simple stitch if xfade fails
            return self.stitch_clips(valid_clips, output_path)
    
    def apply_ken_burns(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        zoom_start: float = 1.0,
        zoom_end: float = 1.1,
        duration: float = 10.0
    ) -> Path:
        """Apply Ken Burns effect (slow zoom) to video."""
        output_path = output_path or self.output_dir / "ken_burns.mp4"
        
        # Calculate zoom per frame (assuming 30fps)
        fps = 30
        total_frames = int(duration * fps)
        zoom_step = (zoom_end - zoom_start) / total_frames
        
        # FFmpeg zoompan filter
        zoompan_filter = (
            f"zoompan=z='min({zoom_start}+{zoom_step}*on,{zoom_end})':"
            f"d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=1920x1080:fps={fps}"
        )
        
        (
            ffmpeg
            .input(str(input_path))
            .filter_complex(zoompan_filter)
            .output(str(output_path), pix_fmt="yuv420p", c_a="copy")
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )
        
        logger.info(f"✅ Applied Ken Burns effect -> {output_path.name}")
        return output_path
    
    def _scale_single(self, input_path: Path, output_path: Path, width: int, height: int):
        """Helper to scale a single video to target resolution."""
        (
            ffmpeg
            .input(str(input_path))
            .filter('scale', width, height, force_original_aspect_ratio='increase')
            .filter('crop', width, height)
            .filter('setsar', 1)
            .output(str(output_path), c='libx264', preset='fast', crf=23, pix_fmt='yuv420p', ac='aac', audio_bitrate='192k')
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )

    def burn_subtitles(
        self,
        input_path: Path,
        srt_path: Path,
        output_path: Optional[Path] = None,
        style: str = "pop"
    ) -> Path:
        """Burn SRT subtitles into video."""
        output_path = output_path or self.output_dir / "subtitled.mp4"
        
        # Subtitle styles - optimized for retention (Poppins)
        # Fontname=Poppins implies it must be installed or mapped. 
        # Fallback to Arial if Poppins isn't available, but standardizing on a clean font.
        styles = {
            "yellow": "FontSize=24,Fontname=Arial,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=2",
            "white": "FontSize=24,Fontname=Arial,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=1,Shadow=1",
            # Fallback to Verdana (clean Sans Serif) if Poppins is missing, to ensure visibility
            "pop": "FontSize=28,Fontname=Verdana,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BackColour=&H80000000,Outline=3,Shadow=2,Bold=1,Alignment=2,MarginV=50",
        }
        
        force_style = styles.get(style, styles["pop"])
        
        # Windows path escaping for filter_complex
        # https://ffmpeg.org/ffmpeg-filters.html#subtitles
        # On Windows, we need to escape backslashes and colon in drive letter
        # e.g C:\foo\bar.srt -> C\:/foo/bar.srt
        # However, filter complex string quoting is tricky. Best approach is forward slashes and escaped colon.
        srt_path_str = str(srt_path.absolute()).replace("\\", "/")
        srt_path_str = srt_path_str.replace(":", "\\:")
        
        (
            ffmpeg
            .input(str(input_path))
            .filter("subtitles", srt_path_str, force_style=force_style)
            .output(str(output_path))
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )
        
        logger.info(f"✅ Burned subtitles (Style: {style}) -> {output_path.name}")
        return output_path
    
    def add_transition(
        self,
        clip_a: Path,
        clip_b: Path,
        output_path: Optional[Path] = None,
        transition_duration: float = 0.5
    ) -> Path:
        """Add crossfade transition between two clips."""
        output_path = output_path or self.output_dir / "transition.mp4"
        
        # Get duration of first clip
        probe = ffmpeg.probe(str(clip_a), cmd=self.ffprobe_cmd)
        duration_a = float(probe['streams'][0]['duration'])
        offset = duration_a - transition_duration
        
        (
            ffmpeg
            .filter(
                [ffmpeg.input(str(clip_a)), ffmpeg.input(str(clip_b))],
                "xfade",
                transition="fade",
                duration=transition_duration,
                offset=offset
            )
            .output(str(output_path))
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )
        
        logger.info(f"✅ Added transition -> {output_path.name}")
        return output_path
    
    def add_background_music(
        self,
        video_path: Path,
        music_path: Path,
        output_path: Optional[Path] = None,
        music_volume: float = 0.15
    ) -> Path:
        """
        Add background music to video, keeping original audio if present.
        
        Args:
            video_path: Input video
            music_path: Background music file
            output_path: Output video path
            music_volume: Volume level for music (0.0 to 1.0)
        """
        import subprocess
        output_path = output_path or self.output_dir / "with_music.mp4"
        
        # Check if video has audio stream
        probe = ffmpeg.probe(str(video_path), cmd=self.ffprobe_cmd)
        has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
        
        # Build command using subprocess for maximum control
        cmd = [self.ffmpeg_cmd, '-y', '-i', str(video_path), '-i', str(music_path)]
        
        if has_audio:
            # Normalize both inputs to 44.1kHz Stereo to prevent mixing errors
            filter_complex = (
                f"[1:a]aresample=44100,aformat=channel_layouts=stereo,volume={music_volume}[music];"
                f"[0:a]aresample=44100,aformat=channel_layouts=stereo[vid_a];"
                # CRITICAL: normalize=0 prevents main audio from being dropped to 50%
                f"[vid_a][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
            )
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '0:v',
                '-map', '[aout]'
            ])
        else:
            # Video is silent, use music as audio track
            filter_complex = (
                f"[1:a]aresample=44100,aformat=channel_layouts=stereo,volume={music_volume}[aout]"
            )
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '0:v',
                '-map', '[aout]',
                '-shortest'  # Cut music to video length
            ])
            
        cmd.extend([
            '-c:v', 'copy',  # Copy video stream without re-encoding
            '-c:a', 'aac',   # Encode audio to AAC
            '-b:a', '192k',
            '-ac', '2',
            '-ar', '44100',
            str(output_path)
        ])
        
        logger.info(f"🔊 Adding background music (vol={music_volume})...")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ Added background music -> {output_path.name}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg error: {e.stderr.decode('utf-8')}")
            raise e
    
    def stitch_clips_with_transitions(
        self,
        clip_paths: list[Path],
        output_path: Optional[Path] = None,
        transition_duration: float = 0.5,
        target_resolution: tuple[int, int] = (1920, 1080)
    ) -> Path:
        """Stitch clips with crossfade transitions (alias for workflow)."""
        # Call the sophisticated stitcher with fades and resolution forcing
        return self.stitch_clips_with_fade(
            clip_paths, 
            output_path, 
            fade_duration=transition_duration,
            target_resolution=target_resolution
        )
    
    def mix_audio(
        self,
        audio_paths: list[Path],
        bg_music_path: Optional[Path],
        output_path: Path
    ) -> Path:
        """Mix multiple audio files with optional background music."""
        if not audio_paths:
            raise ValueError("No audio files provided")
        
        # Concatenate all audio files
        concat_file = self.output_dir / "audio_concat.txt"
        with open(concat_file, "w") as f:
            for audio in audio_paths:
                f.write(f"file '{Path(audio).absolute()}'\\n")
        
        concat_output = self.output_dir / "concat_audio.mp3"
        
        (
            ffmpeg
            .input(str(concat_file), format="concat", safe=0)
            .output(str(concat_output), c="copy")
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )
        
        # Mix with background music if provided
        if bg_music_path:
            input_narration = ffmpeg.input(str(concat_output))
            input_music = ffmpeg.input(str(bg_music_path))
            
            (
                ffmpeg
                .output(
                    input_narration,
                    input_music,
                    str(output_path),
                    filter_complex="[1:a]volume=0.2[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                    map=['[aout]']
                )
                .overwrite_output()
                .run(quiet=True, cmd=self.ffmpeg_cmd)
            )
        else:
            # Just copy the concatenated audio
            import shutil
            shutil.copy(concat_output, output_path)
        
        logger.info(f"✅ Mixed audio -> {output_path}")
        return Path(output_path)
    
    def finalize(
        self,
        video_path: Path,
        audio_path: Path,
        subtitle_path: Optional[Path],
        output_path: Path
    ) -> Path:
        """Combine video, audio, and subtitles into final output."""
        if subtitle_path:
            # First combine video + audio, then burn subtitles
            temp_output = self.output_dir / "temp_combined.mp4"
            
            (
                ffmpeg
                .output(
                    ffmpeg.input(str(video_path)),
                    ffmpeg.input(str(audio_path)),
                    str(temp_output),
                    c_v="copy",
                    map=['0:v', '1:a'],
                    shortest=None
                )
                .overwrite_output()
                .run(quiet=True, cmd=self.ffmpeg_cmd)
            )
            
            return self.burn_subtitles(temp_output, subtitle_path, output_path)
        else:
            # Just combine video + audio
            (
                ffmpeg
                .output(
                    ffmpeg.input(str(video_path)),
                    ffmpeg.input(str(audio_path)),
                    str(output_path),
                    c_v="copy",
                    map=['0:v', '1:a'],
                    shortest=None
                )
                .overwrite_output()
                .run(quiet=True, cmd=self.ffmpeg_cmd)
            )
            
            logger.info(f"✅ Finalized video -> {output_path}")
            return Path(output_path)
    
    def stitch_clips_with_transitions(
        self,
        clip_paths: list[Path],
        output_path: Optional[Path] = None,
        transition_duration: float = 0.5,
        target_resolution: tuple[int, int] = (1920, 1080)
    ) -> Path:
        """Stitch clips with crossfade transitions (alias for workflow)."""
        return self.stitch_clips_with_fade(
            clip_paths, 
            output_path, 
            fade_duration=transition_duration, 
            target_resolution=target_resolution
        )

    def apply_color_grading(
        self,
        video_path: Path,
        grading_config: dict,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Apply color grading using FFmpeg filters.
        config example: {"overall_look": "desaturated", "consistency": "dark_stormy"}
        """
        output_path = output_path or self.output_dir / "graded.mp4"
        
        # Determine filters based on config
    def apply_color_grading(
        self,
        video_path: Path,
        grading_config: dict,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Apply color grading using FFmpeg filters.
        config example: {"overall_look": "desaturated", "consistency": "dark_stormy"}
        """
        import subprocess
        output_path = output_path or self.output_dir / "graded.mp4"
        
        # Determine filters based on config
        look = grading_config.get("overall_look", "").lower()
        filters = []
        
        if "desaturated" in look or "horror" in look:
            # Desaturate and increase contrast (eq) + slight blue tint (colorbalance)
            filters.append("eq=saturation=0.6:contrast=1.2:brightness=-0.05")
            filters.append("colorbalance=bs=0.1") # Blue shadows
        elif "vibrant" in look:
            filters.append("eq=saturation=1.3:contrast=1.1")
        elif "vintage" in look:
            filters.append("curves=vintage")
        else:
            # Default mild enhancement
            filters.append("eq=saturation=1.1:contrast=1.05")
            
        filter_str = ",".join(filters)
        
        cmd = [
            self.ffmpeg_cmd, "-y",
            "-i", str(video_path),
            "-vf", filter_str,
            "-c:a", "copy",
            str(output_path)
        ]
        
        logger.info(f"🎨 Applying color grading ({look})...")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ Applied color grading -> {output_path.name}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Grading failed: {e.stderr.decode('utf-8')}")
            raise e

    def render_title_card(
        self,
        text: str,
        style: str = "horror",
        duration: float = 3.0,
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate a title card video clip."""
        output_path = output_path or self.output_dir / "title_card.mp4"
        
        # Styles
        # Horror: Red text on black
        # Standard: White on black
        font_color = "red" if "horror" in style.lower() else "white"
        font_size = 96
        
        # Use simple color source + drawtext
        # Escape text for drawtext
        text_escaped = text.replace(":", "\\:").replace("'", "")
        
        (
            ffmpeg
            .input(f"color=c=black:s=1920x1080:d={duration}", f="lavfi")
            .filter("drawtext", text=text_escaped, fontsize=font_size, fontcolor=font_color, x="(w-text_w)/2", y="(h-text_h)/2")
            .output(str(output_path))
            .overwrite_output()
            .run(quiet=True, cmd=self.ffmpeg_cmd)
        )
        
        logger.info(f"🪧 Generated title card: '{text}'")
        return output_path
