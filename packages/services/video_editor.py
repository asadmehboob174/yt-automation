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
        target_resolution: tuple[int, int] = (1920, 1080),
        mute_audio: bool = False,
        target_durations: Optional[list[float]] = None
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
        has_sfx = sfx_path.exists() and not mute_audio
        
        # If single clip, just scale
        if len(clip_paths) == 1:
            self._scale_single(clip_paths[0], output_path, target_w, target_h, mute_audio=mute_audio)
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
        
        # 2. Build Inputs & Filter Parts
        inputs = []
        filter_parts = []
        
        v_labels = []
        a_labels = []
        
        cumulative_offset = 0.0
        
        for i, clip in enumerate(valid_clips):
            target_dur = target_durations[i] if target_durations and i < len(target_durations) else durations[i]
            durations[i] = target_dur # Actual duration we use
            
            # Input: Loop infinitely
            inputs.extend(['-stream_loop', '-1', '-i', str(clip)])
            
            # Video Graph: Scale -> Crop -> Trim
            v_label = f"vraw{i}"
            filter_parts.append(
                f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},setsar=1,trim=duration={target_dur},setpts=PTS-STARTPTS[{v_label}]"
            )
            v_labels.append(f"[{v_label}]")
            
            # Audio Graph: Resample -> Fade -> Delay
            # We delay each clip by its start time in the master timeline
            # StartTime(i) = Sum(D_k for k<i) - i * Fade
            delay_ms = int(cumulative_offset * 1000)
            
            # Check if audio stream exists for the current clip
            try:
                inputs_probe = ffmpeg.probe(str(clip), cmd=self.ffprobe_cmd)
                has_audio_stream = any(s['codec_type'] == 'audio' for s in inputs_probe['streams'])
            except Exception:
                has_audio_stream = False

            if has_audio_stream:
                f_in = f"afade=t=in:st=0:d={fade_duration}," if i > 0 else ""
                f_out = f"afade=t=out:st={target_dur - fade_duration}:d={fade_duration}," if i < (count - 1) else ""
                
                a_label = f"async{i}"
                filter_parts.append(
                    f"[{i}:a]aresample=44100,{f_in}{f_out}volume={0.10 if mute_audio else 1.0},"
                    f"adelay={delay_ms}|{delay_ms},atrim=duration={cumulative_offset + target_dur},asetpts=PTS-STARTPTS[{a_label}]"
                )
                a_labels.append(f"[{a_label}]")
            else:
                # If no audio stream, create a silent audio source for the duration
                a_label = f"async{i}"
                filter_parts.append(
                    f"anullsrc=r=44100:cl=stereo:d={target_dur}[a_null{i}];"
                    f"[a_null{i}]adelay={delay_ms}|{delay_ms},atrim=duration={cumulative_offset + target_dur},asetpts=PTS-STARTPTS[{a_label}]"
                )
                a_labels.append(f"[{a_label}]")
            
            # Update offset for NEXT clip
            cumulative_offset += target_dur - fade_duration

        # 3. Join Video via XFade (Still sequential, but cleaner)
        current_v = v_labels[0]
        v_offset = 0.0
        for i in range(count - 1):
            v_offset += durations[i] - fade_duration
            out_v = f"v_xfade{i}"
            filter_parts.append(
                f"{current_v}{v_labels[i+1]}xfade=transition=fade:duration={fade_duration}:offset={v_offset}[{out_v}]"
            )
            current_v = f"[{out_v}]"
        
        final_v_label = current_v

        # 4. Join Audio via AMix (Linear Parallel Mix)
        amix_inputs = "".join(a_labels)
        filter_parts.append(f"{amix_inputs}amix=inputs={count}:duration=longest:dropout_transition=0:normalize=0[a_mixed]")
        final_a_label = "[a_mixed]"
        
        # Transition Timestamps (for SFX WHOOSH)
        # Transition i happens at Offset i
        transition_times = []
        v_offset_check = 0.0
        for i in range(count - 1):
            v_offset_check += durations[i] - fade_duration
            transition_times.append(v_offset_check)
        
        # 5. Inject SFX (Mix Effect)
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
    
        return output_path
    
    def replace_audio_track(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Optional[Path] = None
    ) -> Path:
        """Replace the audio track of a video file with a new audio file."""
        import subprocess
        
        output_path = output_path or self.output_dir / f"{video_path.stem}_new_audio.mp4"
        
        # ffmpeg -i video -i audio -c:v copy -c:a aac -map 0:v -map 1:a output
        cmd = [
            self.ffmpeg_cmd, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "libx264",       # FORCE RE-ENCODE for web compatibility
            "-pix_fmt", "yuv420p",   # FORCE standard pixel format
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", # Ensure even dimensions for yuv420p
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0", # Explicitly map ONLY the first video stream (ignore cover art/mjpeg)
            "-map", "1:a",
            # "-shortest", # Removed: We want video length to dictate duration, looping audio or silence if needed? 
            # Actually, standard behavior: Audio should match video. 
            # If audio is shorter, video continues silent? Or loop audio?
            # Default map 1:a checks. If we want exact video length, we can use -fflags +shortest with input mapping or standard behavior.
            # Safest: Let ffmpeg handle it. If audio is short, it stops? No, usually video dictates.
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ Replaced audio track -> {output_path.name}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to replace audio in {video_path}: {e}")
            if e.stderr:
                logger.error(f"FFmpeg Error Details: {e.stderr.decode('utf-8', errors='replace')}")
            raise

    def swap_audio_streams(
        self,
        video1_path: Path,
        video2_path: Path,
        output_dir: Optional[Path] = None
    ) -> tuple[Path, Path]:
        """
        Swaps audio streams between two videos.
        Returns paths to (video1_visual_audio2, video2_visual_audio1).
        ALWAYS re-encodes video to ensure valid timestamps and compatibility.
        explicitly selects v:0 and a:0 to avoid issues with cover art/thumbnails.
        """
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        out1 = output_dir / f"swap_v1_{video1_path.stem}_a2_{video2_path.stem}.mp4"
        out2 = output_dir / f"swap_v2_{video2_path.stem}_a1_{video1_path.stem}.mp4"

        # Swap 1: Video 1 + Audio 2
        print(f"DEBUG: Swapping 1 (Re-encode): {video1_path} + {video2_path} -> {out1}")
        try:
            # Explicitly select first index streams to avoid cover art processing
            v1_stream = ffmpeg.input(str(video1_path))['v:0']
            a2_stream = ffmpeg.input(str(video2_path))['a:0']
            
            out, err = (
                ffmpeg
                .output(
                    v1_stream, 
                    a2_stream, 
                    str(out1), 
                    vcodec='libx264',
                    acodec='aac',
                    preset='ultrafast',
                    pix_fmt='yuv420p', # Ensure compatibility
                    shortest=None # Use None for boolean flags in ffmpeg-python
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, cmd=self.ffmpeg_cmd)
            )
            print(f"DEBUG: Swap 1 success. Stderr: {err.decode()[-300:] if err else 'None'}")
        except ffmpeg.Error as e:
             # Just print error and re-raise or let it be empty (failed)
             print(f"DEBUG: Swap 1 FAILED. Error: {e.stderr.decode() if e.stderr else str(e)}")
             raise e

        # Swap 2: Video 2 + Audio 1
        print(f"DEBUG: Swapping 2 (Re-encode): {video2_path} + {video1_path} -> {out2}")
        try:
            v2_stream = ffmpeg.input(str(video2_path))['v:0']
            a1_stream = ffmpeg.input(str(video1_path))['a:0']
            
            out, err = (
                ffmpeg
                .output(
                    v2_stream, 
                    a1_stream, 
                    str(out2), 
                    vcodec='libx264',
                    acodec='aac',
                    preset='ultrafast',
                    pix_fmt='yuv420p',
                    shortest=None
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, cmd=self.ffmpeg_cmd)
            )
            print(f"DEBUG: Swap 2 success. Stderr: {err.decode()[-300:] if err else 'None'}")
        except ffmpeg.Error as e:
             print(f"DEBUG: Swap 2 FAILED. Error: {e.stderr.decode() if e.stderr else str(e)}")
             raise e

        return out1, out2

    def _scale_single(self, input_path: Path, output_path: Path, width: int, height: int, mute_audio: bool = False):
        """Helper to scale a single video to target resolution."""
        stream = (
            ffmpeg
            .input(str(input_path))
            .filter('scale', width, height, force_original_aspect_ratio='increase')
            .filter('crop', width, height)
            .filter('setsar', 1)
        )
        
        if mute_audio:
            # Generate silence and map it
            audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi')
            stream = ffmpeg.output(stream, audio, str(output_path), c='libx264', preset='fast', crf=23, pix_fmt='yuv420p', acodec='aac', audio_bitrate='192k', shortest=None)
        else:
             stream = ffmpeg.output(stream, str(output_path), c='libx264', preset='fast', crf=23, pix_fmt='yuv420p', acodec='aac', audio_bitrate='192k')
             
        (
            stream
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
        
        # To completely avoid Windows drive letter colon (C:) parsing bugs in FFmpeg's filtergraph,
        # we run FFmpeg inside the directory where the .srt file lives, and just use its filename.
        srt_filename = srt_path.name
        
        import subprocess
        cmd = [
            self.ffmpeg_cmd, '-y',
            '-i', str(input_path.absolute()),
            '-vf', f"subtitles='{srt_filename}':force_style='{force_style}'",
            '-c:a', 'copy',
            str(output_path.absolute())
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, cwd=str(srt_path.parent))
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg burn_subtitles failed: {e.stderr.decode('utf-8')}")
            raise e
        
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
        output_path: Path,
        scene_interval: float = 9.7
    ) -> Path:
        """Mix multiple audio files sequentially (no overlap) and optional background music."""
        if not audio_paths:
            raise ValueError("No audio files provided")

        import subprocess
        import ffmpeg
        
        # 1. Pad audio sequentially without overlaps
        padded_paths = []
        for i, audio in enumerate(audio_paths):
            padded_out = self.output_dir / f"padded_narration_{i:03d}.mp3"
            
            # Check duration
            try:
                probe = ffmpeg.probe(str(audio), cmd=self.ffprobe_cmd)
                duration = float(probe['streams'][0]['duration'])
            except Exception as e:
                logger.warning(f"⚠️ Could not probe audio {audio}, assuming 0s: {e}")
                duration = 0.0
            
            if duration < scene_interval:
                # Pad with exact silence amount needed
                pad_amount = scene_interval - duration
                cmd = [
                    self.ffmpeg_cmd, '-y',
                    '-i', str(audio),
                    '-f', 'lavfi', '-i', f'anullsrc=r=44100:cl=stereo:d={pad_amount}',
                    '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[aout]',
                    '-map', '[aout]',
                    '-c:a', 'libmp3lame', '-q:a', '2',
                    str(padded_out)
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    padded_paths.append(padded_out)
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Padding failed for {audio}: {e.stderr.decode('utf-8')}")
                    padded_paths.append(audio) # Fallback to original
            else:
                # Keep as-is if it's longer to avoid words being cut off
                padded_paths.append(audio)
        
        # 2. Sequential Concatenation
        concat_file = self.output_dir / "audio_concat.txt"
        with open(concat_file, "w") as f:
            for audio in padded_paths:
                f.write(f"file '{Path(audio).absolute().as_posix()}'\n")
        
        concat_output = self.output_dir / "concat_audio.mp3"
        
        cmd = [
            self.ffmpeg_cmd, '-y',
            '-f', 'concat', '-safe', '0',
            '-i', str(concat_file),
            '-c:a', 'libmp3lame', '-q:a', '2',
            str(concat_output)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("✅ Concatenated audio sequentially.")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Concat failed: {e.stderr.decode('utf-8')}")
            raise e

        # 3. Add background music over the master concatenation track
        if bg_music_path:
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-i', str(concat_output),
                '-i', str(bg_music_path),
                '-filter_complex', '[1:a]volume=0.15[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]',
                '-map', '[aout]',
                '-c:a', 'libmp3lame', '-q:a', '2',
                str(output_path)
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"✅ Mixed BGM + sequential voice -> {output_path.name}")
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ BGM mixing failed: {e.stderr.decode('utf-8')}")
                raise e
        else:
            import shutil
            shutil.copy(concat_output, output_path)

        return output_path
        
    def mix_multiple_tracks(
        self,
        tracks: list[dict],
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Mix multiple audio tracks with specific volumes.
        tracks = [{"path": Path, "volume": 1.0, "loop": False}]
        """
        import subprocess
        output_path = output_path or self.output_dir / "multitrack_mix.mp3"
        
        if not tracks:
            raise ValueError("No tracks provided")
            
        cmd = [self.ffmpeg_cmd, '-y']
        
        filter_complex = []
        inputs_map = []
        
        # Add inputs
        for i, track in enumerate(tracks):
            cmd.extend(['-i', str(track['path'])])
            
            # Volume filter
            vol = track.get('volume', 1.0)
            filter_complex.append(f"[{i}:a]volume={vol}[a{i}]")
            inputs_map.append(f"[a{i}]")
            
        # Mix
        # amix=inputs=N:duration=first:dropout_transition=2
        # duration=longest insures we don't cut off if one track is shorter? 
        # Usually valid video duration determines final cut. Here we probably want 'longest' to be safe, or 'first' if track 0 is master.
        # Let's use duration=longest and let finalize() cut to video length.
        all_inputs = "".join(inputs_map)
        filter_complex.append(f"{all_inputs}amix=inputs={len(tracks)}:duration=longest:dropout_transition=2:normalize=0[aout]")
        
        cmd.extend([
            '-filter_complex', ";".join(filter_complex),
            '-map', '[aout]',
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            str(output_path)
        ])
        
        logger.info(f"🎛️ Mixing {len(tracks)} tracks -> {output_path.name}")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Mix failed: {e.stderr.decode('utf-8')}")
            raise e
    
    def finalize(
        self,
        video_path: Path,
        audio_path: Path,
        subtitle_path: Optional[Path],
        output_path: Path
    ) -> Path:
        """Combine video, audio, and subtitles into final output."""
        import subprocess
        
        if subtitle_path:
            # First combine video + audio, then burn subtitles
            temp_output = self.output_dir / "temp_combined.mp4"
            
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-c:v', 'copy',
                '-map', '0:v',
                '-map', '1:a',
                '-shortest',
                str(temp_output)
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ FFmpeg finalize (video+audio) failed: {e.stderr.decode('utf-8')}")
                raise e
            
            return self.burn_subtitles(temp_output, subtitle_path, output_path)
        else:
            # Just combine video + audio
            cmd = [
                self.ffmpeg_cmd, '-y',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-c:v', 'copy',
                '-map', '0:v',
                '-map', '1:a',
                '-shortest',
                str(output_path)
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ FFmpeg finalize failed: {e.stderr.decode('utf-8')}")
                raise e
            
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

    async def upscale_video(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        target_resolution: tuple[int, int] = (3840, 2160)
    ) -> Path:
        """Upscale video to 4K resolution using Hugging Face Space AI_Video_Enhancer_4K."""
        output_path = output_path or self.output_dir / f"upscaled_{input_path.name}"
        
        import os
        import shutil
        from gradio_client import Client
        import asyncio
        
        hf_token = os.getenv("HF_TOKEN")
        
        if not hf_token:
            logger.error("❌ HF_TOKEN not found. Skipping 4K upscale.")
            shutil.copy(input_path, output_path)
            return output_path
            
        logger.info(f"🚀 Sending {input_path.name} to Hugging Face Space (tggtg/AI_Video_Enhancer_4K)...")
        
        try:
            # We must run gradio client synchronously in an executor because it blocks
            def run_gradio():
                from gradio_client import Client, handle_file
                client = Client("tggtg/AI_Video_Enhancer_4K", token=hf_token)
                result = client.predict(
                    file_obj=handle_file(str(input_path)),
                    api_name="/on_click_process"
                )
                return result
                
            # result is a tuple: (status_text, dict_with_video_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_gradio)
            
            # Extract video path from result
            if isinstance(result, tuple) and len(result) == 2:
                status, video_info = result
                
                remote_path = None
                if isinstance(video_info, dict):
                    remote_path = video_info.get("video")
                elif isinstance(video_info, str):
                    remote_path = video_info

                if remote_path and os.path.exists(remote_path):
                    shutil.copy(remote_path, output_path)
                    logger.info(f"✅ Upscaled to 4K via HF Space -> {output_path.name}")
                    return output_path
            
            logger.warning(f"⚠️ Unexpected response from HF Space: {result}")
            raise ValueError("Invalid response format from space")
            
        except Exception as e:
            logger.error(f"❌ HF Space Upscale failed: {e}")
            logger.warning("⚠️ Falling back to returning original resolution video.")
            # If upscale fails, fallback to original. We avoid heavy local FFmpeg upscale by design.
            shutil.copy(input_path, output_path)
            return output_path
