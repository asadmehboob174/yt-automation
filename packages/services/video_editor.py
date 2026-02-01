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
            .run(quiet=True)
        )
        
        logger.info(f"✅ Stitched {len(clip_paths)} clips -> {output_path.name}")
        return output_path
    
    def stitch_clips_with_fade(
        self,
        clip_paths: list[Path],
        output_path: Optional[Path] = None,
        fade_duration: float = 0.4,
        target_resolution: tuple[int, int] = (1080, 1920)
    ) -> Path:
        """
        Stitch clips with black fade transitions between each clip.
        Forces all clips to target_resolution to prevent concat errors.
        """
        import subprocess
        
        if not clip_paths:
            raise ValueError("No clips provided")
        
        target_w, target_h = target_resolution
        output_path = output_path or self.output_dir / "stitched_fade.mp4"
        
        if len(clip_paths) == 1:
            # Single clip, just copy it (or scale it?)
            # Let's scale it to be safe
            self._scale_single(clip_paths[0], output_path, target_w, target_h)
            return output_path
        
        # Get durations for each clip
        durations = []
        for clip in clip_paths:
            probe = ffmpeg.probe(str(clip))
            duration = float(probe['streams'][0]['duration'])
            durations.append(duration)
        
        # Build inputs
        inputs = []
        for clip in clip_paths:
            inputs.extend(['-i', str(clip)])
        
        # Build filter complex
        filter_parts = []
        
        # 1. Scale all inputs to target resolution first
        # Format: [0:v]scale=w:h:force_original_aspect_ratio=decrease,pad=w:h:(ow-iw)/2:(oh-ih)/2,setsar=1[s0]
        for i in range(len(clip_paths)):
            scale_filter = (
                f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},"
                f"setsar=1[s{i}]"
            )
            filter_parts.append(scale_filter)

        # 2. Apply fades to scaled streams [s0], [s1]...
        for i in range(len(clip_paths)):
            fade_in = f"fade=t=in:st=0:d={fade_duration}" if i > 0 else ""
            fade_out = f"fade=t=out:st={durations[i] - fade_duration}:d={fade_duration}" if i < len(clip_paths) - 1 else ""
            
            # Chain fade filters
            filters = []
            if fade_in: filters.append(fade_in)
            if fade_out: filters.append(fade_out)
            
            fade_chain = ",".join(filters) if filters else "copy"
            filter_parts.append(f"[s{i}]{fade_chain}[v{i}]")
            
            # Also handle audio fades
            afade_in = f"afade=t=in:st=0:d={fade_duration}" if i > 0 else ""
            afade_out = f"afade=t=out:st={durations[i] - fade_duration}:d={fade_duration}" if i < len(clip_paths) - 1 else ""
            
            if afade_in and afade_out:
                filter_parts.append(f"[{i}:a]{afade_in},{afade_out}[a{i}]")
            elif afade_in:
                filter_parts.append(f"[{i}:a]{afade_in}[a{i}]")
            elif afade_out:
                filter_parts.append(f"[{i}:a]{afade_out}[a{i}]")
            else:
                filter_parts.append(f"[{i}:a]acopy[a{i}]")
        
        # Concat all faded clips
        video_concat = "".join([f"[v{i}]" for i in range(len(clip_paths))])
        audio_concat = "".join([f"[a{i}]" for i in range(len(clip_paths))])
        filter_parts.append(f"{video_concat}concat=n={len(clip_paths)}:v=1:a=0[outv]")
        filter_parts.append(f"{audio_concat}concat=n={len(clip_paths)}:v=0:a=1[outa]")
        
        filter_complex = ";".join(filter_parts)
        
        # Build and run FFmpeg command
        cmd = ['ffmpeg', '-y'] + inputs + [
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            str(output_path)
        ]
        
        logger.info(f"🎬 Stitching {len(clip_paths)} clips with {fade_duration}s black fade...")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ Stitched with fades -> {output_path.name}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            # Fallback to simple concat if complex filter fails
            logger.warning("⚠️ Falling back to simple concat without fades")
            return self.stitch_clips(clip_paths, output_path)
    
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
            .run(quiet=True)
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
            .output(str(output_path), c='libx264', preset='fast', crf=23, ac='aac', audio_bitrate='192k')
            .overwrite_output()
            .run(quiet=True)
        )

    def burn_subtitles(
        self,
        input_path: Path,
        srt_path: Path,
        output_path: Optional[Path] = None,
        style: str = "yellow"
    ) -> Path:
        """Burn SRT subtitles into video."""
        output_path = output_path or self.output_dir / "subtitled.mp4"
        
        # Subtitle styles
        styles = {
            "yellow": "FontSize=24,Fontname=Arial,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=2",
            "white": "FontSize=24,Fontname=Arial,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=1,Shadow=1",
        }
        
        force_style = styles.get(style, styles["yellow"])
        
        (
            ffmpeg
            .input(str(input_path))
            .filter("subtitles", str(srt_path), force_style=force_style)
            .output(str(output_path))
            .overwrite_output()
            .run(quiet=True)
        )
        
        logger.info(f"✅ Burned subtitles -> {output_path.name}")
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
        probe = ffmpeg.probe(str(clip_a))
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
            .run(quiet=True)
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
        probe = ffmpeg.probe(str(video_path))
        has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
        
        # Build command using subprocess for maximum control
        cmd = ['ffmpeg', '-y', '-i', str(video_path), '-i', str(music_path)]
        
        if has_audio:
            # Normalize both inputs to 44.1kHz Stereo to prevent mixing errors
            filter_complex = (
                f"[1:a]aresample=44100,aformat=channel_layouts=stereo,volume={music_volume}[music];"
                f"[0:a]aresample=44100,aformat=channel_layouts=stereo[vid_a];"
                f"[vid_a][music]amix=inputs=2:duration=first[aout]"
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
        transition_duration: float = 0.5
    ) -> Path:
        """Stitch clips with crossfade transitions (alias for workflow)."""
        # For simplicity, just use basic concat
        # A full implementation would add transitions between each pair
        return self.stitch_clips(clip_paths, output_path)
    
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
            .run(quiet=True)
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
                .run(quiet=True)
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
                .run(quiet=True)
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
                .run(quiet=True)
            )
            
            logger.info(f"✅ Finalized video -> {output_path}")
            return Path(output_path)
