"""
Video Generation Workflow - Inngest Functions.

Durable workflow for generating AI videos with:
- Image generation (PuLID)
- Video animation (Grok)
- Audio generation (Edge-TTS)
- Final rendering (FFmpeg)
- YouTube upload
"""
import logging
import asyncio
from inngest import Inngest, Function, Context
from pathlib import Path
from typing import Any, Optional

from .inngest_client import inngest_client
from .cloud_storage import R2Storage
from .email_service import email_service

logger = logging.getLogger(__name__)


# ============================================
# VIDEO GENERATION WORKFLOW
# ============================================

@inngest_client.create_function(
    fn_id="video-generation",
    trigger={"event": "video/generation.started"},
    retries=3,
)
async def video_generation_workflow(ctx: Context) -> dict:
    """
    Main video generation workflow with full pipeline.
    
    Event data should contain:
    - video_id: Database ID of the video record
    - script: The VideoScript object
    - channel_config: Channel configuration
    - resume_from_checkpoint: Optional checkpoint to resume from
    """
    video_id = ctx.event.data.get("video_id")
    script = ctx.event.data.get("script")
    channel_config = ctx.event.data.get("channel_config")
    checkpoint = ctx.event.data.get("resume_from_checkpoint", {})
    
    logger.info(f"🎬 Starting video generation for {video_id}")
    
    # Track completed steps for checkpoint recovery
    completed_steps = checkpoint.get("completed_steps", [])
    partial_results = checkpoint.get("partial_results", {})
    
    try:
        # Step 1: Generate character images for each scene
        if "scene_images" not in completed_steps:
            scene_images = await ctx.step.run(
                "generate-scene-images",
                lambda: generate_scene_images(script, channel_config)
            )
            partial_results["scene_images"] = scene_images
            completed_steps.append("scene_images")
        else:
            scene_images = partial_results["scene_images"]
        
        # Step 2: Animate scenes with Grok (with rate limit handling)
        if "animated_clips" not in completed_steps:
            try:
                animated_clips = await ctx.step.run(
                    "animate-scenes",
                    lambda: animate_scenes_with_grok(scene_images, script)
                )
                partial_results["animated_clips"] = animated_clips
                completed_steps.append("animated_clips")
            except Exception as e:
                if "rate limit" in str(e).lower():
                    # Trigger rate limit recovery
                    await ctx.step.send_event(
                        "rate-limit-detected",
                        {
                            "name": "video/generation.rate_limited",
                            "data": {
                                "video_id": video_id,
                                "script": script,
                                "channel_config": channel_config,
                                "checkpoint": {
                                    "completed_steps": completed_steps,
                                    "partial_results": partial_results
                                },
                                "wait_seconds": 7200
                            }
                        }
                    )
                    return {"status": "rate_limited", "checkpoint": completed_steps}
                raise
        else:
            # INTEGRITY GUARD ON RESUME:
            # Even if 'animated_clips' is in completed_steps, we MUST verify them
            # because some might have been corrupt HTML in a previous attempt.
            logger.info(f"🔄 Resuming from checkpoint. Verifying integrity for {video_id}...")
            animated_clips = await ctx.step.run(
                "verify-clips-integrity",
                lambda: animate_scenes_with_grok(scene_images, script) # This function now handles selective repair!
            )
            partial_results["animated_clips"] = animated_clips
        
        # Step 3: Generate voiceover audio (ONLY for documentary videos)
        # Story videos use Grok's built-in dialogue audio
        video_type = script.get("video_type", "story")
        
        if video_type == "documentary":
            if "audio_files" not in completed_steps:
                audio_files = await ctx.step.run(
                    "generate-voiceover",
                    lambda: generate_voiceover(script, channel_config)
                )
                partial_results["audio_files"] = audio_files
                completed_steps.append("audio_files")
            else:
                audio_files = partial_results["audio_files"]
        else:
            # Story mode: no separate voiceover needed, Grok generates dialogue
            audio_files = []
            logger.info(f"📹 Story mode: Using Grok's built-in audio for {video_id}")
        
        # CHECKPOINT: All clips ready
        all_clips_ready = len(animated_clips) == len(script.get("scenes", []))
        
        # For documentary, also check audio files
        if video_type == "documentary":
            all_clips_ready = all_clips_ready and len(audio_files) == len(script.get("scenes", []))
        
        if not all_clips_ready:
            logger.error(f"❌ Not all clips ready: {len(animated_clips)} clips, {len(audio_files)} audio")
            raise ValueError("Incomplete clip generation")
        
        logger.info(f"✅ All clips ready checkpoint passed for {video_id}")
        
        # Step 4: Generate SEO content (Title, Description, Tags, Thumbnail)
        if "seo_result" not in completed_steps:
            seo_result = await ctx.step.run(
                "generate-seo-content",
                lambda: generate_seo_content(script, channel_config, scene_images[0] if scene_images else None)
            )
            partial_results["seo_result"] = seo_result
            completed_steps.append("seo_result")
        else:
            seo_result = partial_results["seo_result"]
        
        # Step 5: Render final video with FFmpeg
        if "final_video_key" not in completed_steps:
            final_video_key = await ctx.step.run(
                "render-final-video",
                lambda: render_final_video(
                    animated_clips, 
                    audio_files, 
                    script,
                    channel_config
                )
            )
            partial_results["final_video_key"] = final_video_key
            completed_steps.append("final_video_key")
        else:
            final_video_key = partial_results["final_video_key"]
        
        # Step 6: Upload thumbnail to R2
        if "thumbnail_key" not in completed_steps and seo_result.get("thumbnail_path"):
            thumbnail_key = await ctx.step.run(
                "upload-thumbnail",
                lambda: upload_thumbnail(seo_result["thumbnail_path"], script)
            )
            partial_results["thumbnail_key"] = thumbnail_key
            completed_steps.append("thumbnail_key")
        else:
            thumbnail_key = partial_results.get("thumbnail_key")
        
        # Step 7: SKIPPED (Manual Review Requested)
        # Original auto-upload removed. Now we wait for user approval.
        
        # Step 8: Update video status to REVIEW_PENDING
        await ctx.step.run(
            "update-status-review",
            lambda: update_video_status(video_id, "REVIEW_PENDING", {
                "seo": seo_result,
                "final_video_key": final_video_key,
                "thumbnail_key": thumbnail_key,
                "steps_completed": len(completed_steps)
            })
        )
        
        logger.info(f"✅ Video ready for review: {video_id}")
        
        # Step 9: Send email notification
        await ctx.step.run(
            "send-completion-email",
            lambda: email_service.send_video_complete(
                project_name=script.get("title", "New Video"),
                video_url=R2Storage().get_url(final_video_key),
                channel_name=channel_config.get("name")
            )
        )
        
        return {
            "video_id": video_id,
            "status": "review_pending",
            "final_video_key": final_video_key,
            "thumbnail_key": thumbnail_key,
            "title": seo_result.get("title"),
        }
        
    except Exception as e:
        logger.error(f"❌ Video generation failed for {video_id}: {e}")
        
        # Save checkpoint for partial failure recovery
        await update_video_status(video_id, "FAILED", {
            "error": str(e),
            "checkpoint": {
                "completed_steps": completed_steps,
                "partial_results": {k: v for k, v in partial_results.items() if isinstance(v, (str, list))}
            }
        })
        raise

@inngest_client.create_function(
    fn_id="video-upload",
    trigger={"event": "video/upload.requested"},
    retries=3,
)
async def video_upload_workflow(ctx: Context) -> dict:
    """
    Manual upload workflow triggered after user review.
    """
    video_id = ctx.event.data.get("video_id")
    final_video_key = ctx.event.data.get("final_video_key")
    thumbnail_key = ctx.event.data.get("thumbnail_key")
    script = ctx.event.data.get("script")
    channel_config = ctx.event.data.get("channel_config")
    seo_result = ctx.event.data.get("seo_result")
    
    logger.info(f"🚀 Starting manual upload for {video_id}")
    
    try:
        # Upload to YouTube
        youtube_result = await ctx.step.run(
            "upload-to-youtube",
            lambda: upload_to_youtube(
                final_video_key, 
                script, 
                channel_config,
                seo_result,
                thumbnail_key
            )
        )
        
        # Update status to COMPLETED
        await ctx.step.run(
            "update-status-completed",
            lambda: update_video_status(video_id, "COMPLETED", {
                **youtube_result,
                "final_video_key": final_video_key,
                "uploaded_at": youtube_result.get("published_at")
            })
        )
        
        return {"status": "uploaded", "youtube_id": youtube_result.get("video_id")}
        
    except Exception as e:
        logger.error(f"❌ Upload failed for {video_id}: {e}")
        await update_video_status(video_id, "UPLOAD_FAILED", {"error": str(e)})
        raise


# ============================================
# STEP FUNCTIONS
# ============================================

async def generate_scene_images(script: dict, channel_config: dict) -> list[str]:
    """Generate consistency character images for each scene using Google Whisk."""
    from .whisk_agent import WhiskAgent
    
    # Initialize Whisk Agent
    # Note: Requires 'python scripts/auth_whisk.py' to be run first for login
    agent = WhiskAgent(headless=False) # Headful for alpha stability
    storage = R2Storage()
    image_keys = []
    
    # Determine Aspect Ratio
    # If "shorts" is in the niche ID or style, use 9:16
    is_shorts = "shorts" in channel_config.get("nicheId", "").lower() or "shorts" in channel_config.get("styleSuffix", "").lower()
    logger.info(f"📐 Detected Mode: {'Shorts (9:16)' if is_shorts else 'Landscape (16:9)'}")

    # Generate anchor/consistent character if needed (Optional: Whisk is prompt-based mostly)
    # anchor_image_path = channel_config.get("anchorImage")
    
    # Prepare Batch
    prompts = [scene.get("character_pose_prompt", "") for scene in script.get("scenes", [])]
    style = channel_config.get("styleSuffix", "")
    
    logger.info(f"🚀 Starting Auto-Whisk Batch Generation for {len(prompts)} scenes...")
    
    # Run Batch (Mimics Auto Whisk Extension)
    # This keeps the browser open and loops through prompts efficiently
    batch_results = await agent.generate_batch(
        prompts=prompts,
        is_shorts=is_shorts,
        style_suffix=style,
        delay_seconds=5
    )
    
    # Process Results
    for i, (scene, image_bytes) in enumerate(zip(script.get("scenes", []), batch_results)):
        if not image_bytes:
            logger.error(f"❌ Skipped scene {i+1} due to generation failure")
            continue
            
        try:
            # Upload to R2
            key = f"clips/{script['niche_id']}/scene_{i:03d}_image.png"
            storage.upload_asset(image_bytes, key, "image/png")
            image_keys.append(key)
            logger.info(f"✅ Saved Scene {i+1}: {key}")
        except Exception as e:
             logger.error(f"❌ Failed to upload scene {i+1}: {e}")
    
    return image_keys

def is_valid_video_content(p: Path) -> bool:
    """Check if a file is a valid video (not HTML error page)."""
    try:
        if p.stat().st_size < 1000: return False
        with open(p, "rb") as f:
            head = f.read(200)
            if b"<!DOCTYPE html>" in head or b"<html" in head:
                return False
        # Optional: ffprobe check if too large
        if p.stat().st_size > 50000:
            import ffmpeg
            ffmpeg.probe(str(p))
        return True
    except:
        return False


async def animate_scenes_with_grok(image_keys: list[str], script: dict) -> list[str]:
    """
    Animate scene images using Grok Imagine with Deep Integrity Check.
    
    This function:
    1. Checks for existing clips in R2.
    2. Performs a "Deep Check" (downloading and verifying against HTML content).
    3. Retries only the missing or corrupt indices.
    """
    from .grok_agent import GrokAnimator
    from pathlib import Path
    import tempfile
    
    animator = GrokAnimator()
    storage = R2Storage()
    scenes = script.get("scenes", [])
    clip_keys = [None] * len(scenes)
    
    # 1. INITIAL SCAN: Check existing clips in R2 for corruption
    logger.info(f"🔍 Performing Deep Integrity Check on {len(scenes)} potential clips...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        for i in range(len(scenes)):
            expected_key = f"clips/{script['niche_id']}/scene_{i:03d}_animated.mp4"
            
            # Check if exists in R2 metadata
            if storage.exists(expected_key):
                # DEEP CHECK: Download and verify
                local_check_path = Path(tmp_dir) / f"check_{i}.mp4"
                try:
                    storage.download(expected_key, str(local_check_path))
                    if is_valid_video_content(local_check_path):
                        clip_keys[i] = expected_key
                        logger.info(f"   ✅ Scene {i+1} exists and is valid.")
                    else:
                        logger.warning(f"   ❌ Scene {i+1} is CORRUPT (HTML) despite being in R2. Marking for repair.")
                        storage.delete_file(expected_key) # Fixed method name: delete_file
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not verify existing scene {i+1}: {e}")

    # 2. GENERATION/REPAIR LOOP
    MAX_BATCH_ATTEMPTS = 3
    for batch_attempt in range(MAX_BATCH_ATTEMPTS):
        missing_indices = [i for i, key in enumerate(clip_keys) if key is None]
        if not missing_indices:
            break
            
        logger.info(f"🔄 Batch Repair Attempt {batch_attempt+1}/{MAX_BATCH_ATTEMPTS}: Retrying {len(missing_indices)} scenes...")
        
        for i in missing_indices:
            image_key = image_keys[i]
            scene = scenes[i]
            
            try:
                logger.info(f"🎥 Animating scene {i+1}/{len(scenes)}")
                
                # Download image from R2
                local_image = storage.download(image_key, f"/tmp/scene_{i}.png")
                
                motion_prompt = scene.get("motion_description", "")
                
                # Extract new structured fields
                grok_prompt = scene.get("grok_video_prompt")
                sfx_list = scene.get("sfx")
                music_notes = scene.get("music_notes")
                
                # Derive components for fallback/hybrid usage
                current_emotion = "neutrally"
                if grok_prompt and isinstance(grok_prompt, dict):
                    current_emotion = grok_prompt.get("emotion", "neutrally")
                
                # Format dialogue for Grok prompt
                dialogue_raw = scene.get("dialogue")
                dialogue_str = ""
                if isinstance(dialogue_raw, dict):
                    dialogue_str = " ".join([f'{k}: "{v}"' for k, v in dialogue_raw.items()])
                elif isinstance(dialogue_raw, str):
                    dialogue_str = dialogue_raw

                try:
                    # Animate with Grok
                    video_path = await animator.animate(
                        image_path=local_image,
                        motion_prompt=motion_prompt,
                        duration=scene.get("duration_in_seconds", 10),
                        grok_video_prompt=grok_prompt,
                        sfx=sfx_list,
                        music_notes=music_notes,
                        emotion=current_emotion,
                        dialogue=dialogue_str
                    )
                except Exception as e:
                    from .grok_agent import ModerationError
                    if isinstance(e, ModerationError):
                        logger.warning(f"🛑 Moderation detected for scene {i+1}. Attempting AI rewrite...")
                        from .script_generator import ScriptGenerator
                        gen = ScriptGenerator()
                        new_prompt = await gen.rewrite_moderated_prompt(motion_prompt)
                        
                        if new_prompt != motion_prompt:
                            logger.info(f"🔄 Retrying scene {i+1} with sanitized prompt: {new_prompt}")
                            # RETRY ONCE
                            # Pass grok_video_prompt=None to stick to the sanitized text prompt
                            video_path = await animator.animate(
                                image_path=local_image,
                                motion_prompt=new_prompt,
                                duration=scene.get("duration_in_seconds", 10),
                                grok_video_prompt=None, # Force use of new_prompt
                                sfx=sfx_list,
                                music_notes=music_notes,
                                emotion=current_emotion
                            )
                        else:
                            raise e # If rewrite failed or didn't change anything, give up
                    else:
                        raise e # Rethrow non-moderation errors
                
                # Verify locally before upload
                if video_path and video_path.exists() and is_valid_video_content(video_path):
                    # Upload animated clip to R2
                    clip_key = f"clips/{script['niche_id']}/scene_{i:03d}_animated.mp4"
                    storage.upload(video_path, clip_key)
                    clip_keys[i] = clip_key
                    logger.info(f"   ✅ Scene {i+1} generated and verified.")
                else:
                    logger.warning(f"   ⚠️ Scene {i+1} failed verification on generation.")
                    
            except Exception as e:
                logger.error(f"   ❌ Failed to animate scene {i+1}: {e}")
                if "rate limit" in str(e).lower():
                    raise # Re-raise rate limit to trigger Inngest recovery
        
        # Cooling period between batch retries
        if any(key is None for key in clip_keys) and batch_attempt < MAX_BATCH_ATTEMPTS - 1:
            wait_time = (batch_attempt + 1) * 30
            logger.info(f"⏱️ Waiting {wait_time}s before next repair attempt...")
            await asyncio.sleep(wait_time)

    # 3. FINAL INTEGRITY GUARD
    final_clips = [k for k in clip_keys if k is not None]
    if len(final_clips) < len(scenes):
        missing = [i+1 for i, k in enumerate(clip_keys) if k is None]
        error_msg = f"❌ Integrity Check Failed: Scenes {missing} are still missing or corrupt."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info(f"🏆 Batch generation complete with 100% integrity ({len(final_clips)} clips).")
    return final_clips


async def generate_voiceover(script: dict, channel_config: dict) -> list[str]:
    """Generate TTS voiceover for each scene."""
    from .audio_engine import AudioEngine
    
    engine = AudioEngine()
    storage = R2Storage()
    audio_keys = []
    
    voice_id = channel_config.get("voiceId", "en-US-AriaNeural")
    
    for i, scene in enumerate(script.get("scenes", [])):
        logger.info(f"🎙️ Generating voiceover for scene {i+1}")
        
        audio_path = await engine.generate_narration(
            text=scene.get("voiceover_text", ""),
            voice=voice_id,
            output_path=f"/tmp/scene_{i}_audio.mp3"
        )
        
        # Upload to R2
        audio_key = f"clips/{script['niche_id']}/scene_{i:03d}_audio.mp3"
        storage.upload(audio_path, audio_key)
        audio_keys.append(audio_key)
    
    return audio_keys


async def _generate_dynamic_soundtrack(soundtrack_config: dict, script: dict, total_duration: float) -> Any:
    """Generate dynamic soundtrack based on timing config."""
    from .music_generator import generate_music_with_ai
    from .audio_engine import AudioEngine
    import re
    import math
    
    timing_str = soundtrack_config.get("music_timing", "")
    # Example: "Adventure (scene 1-3) -> Horror (4-6)"
    
    engine = AudioEngine()
    segments = []
    scenes = script.get("scenes", [])
    
    # 1. Parse timing string
    # Regex to find "Description (Range)" patterns
    # Handles: "Desc (scene 1)", "Desc (1-3)", "Desc (scenes 1-3)"
    pattern = r"(.+?)\s*\((?:scene\w*\s*)?(\d+)(?:-(\d+))?\)"
    matches = re.findall(pattern, timing_str, re.IGNORECASE)
    
    if not matches:
        # Fallback: Generate one track for whole video based on background_music description
        desc = soundtrack_config.get("background_music", "Background music")
        logger.info(f"🎵 Dynamic Soundtrack: No timing found, generating single track for '{desc}'")
        path = await generate_music_with_ai(desc, duration=int(total_duration) + 5)
        return path

    logger.info(f"🎵 Constructing Dynamic Soundtrack with {len(matches)} segments...")
    
    current_time = 0.0
    
    for desc, start_idx, end_idx in matches:
        start_scene = int(start_idx) - 1
        end_scene = int(end_idx) - 1 if end_idx else start_scene
        
        # Calculate duration based on scenes
        # We need to know duration of these scenes.
        # Estimate from script or passed info? 
        # We don't have exact duration of *generated* clips here easily unless we probe them.
        # But render_final_video has local_clips... 
        # We'll rely on script['duration_in_seconds'] as estimate or just assume 5s?
        # Better: use script duration.
        
        segment_duration = 0.0
        for i in range(start_scene, min(end_scene + 1, len(scenes))):
             segment_duration += scenes[i].get("duration_in_seconds", 5)
             
        # Add buffer for crossfades
        gen_duration = int(segment_duration) + 10
        
        logger.info(f"   🎹 Segment: '{desc.strip()}' for scenes {start_scene+1}-{end_scene+1} ({segment_duration}s)")
        
        music_path = await generate_music_with_ai(desc.strip(), duration=gen_duration)
        if music_path:
            segments.append({
                "path": music_path,
                "duration": segment_duration
            })
            
    if segments:
        return engine.construct_dynamic_soundtrack(segments, total_duration)
    return None

async def render_final_video(
    clip_keys: list[str], 
    audio_keys: list[str], 
    script: dict,
    channel_config: dict
) -> str:
    """
    Render final video with transitions, audio, grading, and subtitles.
    Supports 'FinalAssembly' features.
    """
    from .video_editor import FFmpegVideoEditor
    from .subtitle_engine import SubtitleEngine
    import ffmpeg
    
    storage = R2Storage()
    editor = FFmpegVideoEditor()
    subtitle_engine = SubtitleEngine()
    
    assembly = script.get("final_assembly")
    video_type = script.get("video_type", "story")
    
    # Ensure storage space
    storage.ensure_storage_available(required_gb=1.0)
    
    # 1. Download Core Clips
    local_clips = []
    for i, clip_key in enumerate(clip_keys):
        local_path = storage.download(clip_key, Path(f"/tmp/clip_{i}.mp4"))
        if not is_valid_video_content(local_path):
             raise ValueError(f"Clip {clip_key} is corrupt.")
        local_clips.append(local_path)
    
    # 2. Title Cards (Opening/Closing)
    if assembly and assembly.get("title_cards"):
        tc = assembly["title_cards"]
        style = "horror" if "horror" in script.get("niche_id", "") else "standard"
        
        if tc.get("opening"):
            opener = editor.render_title_card(tc["opening"], style=style, output_path=Path("/tmp/title_opener.mp4"))
            local_clips.insert(0, opener)
            # Adjust audio keys index? Title cards have no audio usually.
            
        if tc.get("closing"):
            closer = editor.render_title_card(tc["closing"], style=style, output_path=Path("/tmp/title_closer.mp4"))
            local_clips.append(closer)

    # Determine Resolution
    is_shorts = "shorts" in channel_config.get("nicheId", "").lower() or "shorts" in channel_config.get("styleSuffix", "").lower()
    target_res = (1080, 1920) if is_shorts else (1920, 1080)
    
    # Extract Audio Config
    audio_cfg = channel_config.get("audio", {})
    mute_source = audio_cfg.get("mute_source_audio", False)
    audio_provider = audio_cfg.get("provider") # 'elevenlabs', 'xtts', 'edge-tts'
    voice_id = audio_cfg.get("voice_id")
    voice_sample_key = audio_cfg.get("voice_sample_key")
    
    # 3. Stitching
    logger.info(f"🧵 Stitching {len(local_clips)} clips (Mute Source: {mute_source})...")
    stitched_path = editor.stitch_clips_with_transitions(
        local_clips, 
        "/tmp/stitched.mp4",
        target_resolution=target_res,
        transition_duration=0.5,
        mute_audio=mute_source
    )
    
    # 3.5 Generate Custom TTS / Rescripting
    # Check if we should use 'Advanced Rescripting' (text_to_audio_prompt)
    is_rescripting = any(s.get("text_to_audio_prompt") for s in script.get("scenes", []))
    
    if is_rescripting:
        logger.info("🎤 Advanced Rescripting Detected: Using text_to_audio_prompt for audio generation.")
        audio_provider = "xtts" # Force XTTS for cloning
        has_fresh_audio = True
    elif audio_provider and (video_type == "story" or video_type == "documentary"):
        logger.info(f"🎙️ Generating fresh Voiceover using {audio_provider}...")
        has_fresh_audio = True
    else:
        has_fresh_audio = False
        
    # Track paths for cleanup
    extracted_vocals_path = None
    extracted_background_path = None

    if has_fresh_audio:
        from .audio_engine import AudioEngine
        from .audio_separator import AudioSeparator
        engine = AudioEngine()
        separator = AudioSeparator()
        
        # In Rescripting Mode, we need a voice sample from the original clips
        ref_audio_path = None
        
        # Download explicit sample if provided in config
        if voice_sample_key:
             ref_audio_path = Path("/tmp/ref_voice.wav")
             try:
                 storage.download(voice_sample_key, ref_audio_path)
             except Exception as e:
                 logger.warning(f"⚠️ Failed to download voice sample for XTTS: {e}")
                 ref_audio_path = None

        # FALLBACK: If no explicit sample, or we need background preservation, extract from clips
        if (is_rescripting or has_fresh_audio) and not ref_audio_path:
            logger.info("🎼 Extracting original audio for reference and background preservation...")
            temp_stitched_audio = Path("/tmp/stitched_source.mp3")
            (
                ffmpeg
                .input(str(stitched_path))
                .output(str(temp_stitched_audio), acodec='libmp3lame', q=2)
                .overwrite_output()
                .run(quiet=True, cmd=editor.ffmpeg_cmd)
            )
            
            # Separate to get vocals and background
            if separator.client:
                bg_sep, voc_sep = separator.separate_audio(temp_stitched_audio)
                if voc_sep and voc_sep.exists():
                    extracted_vocals_path = voc_sep
                    logger.info(f"✅ Found voice reference for cloning: {extracted_vocals_path}")
                if bg_sep and bg_sep.exists():
                    extracted_background_path = bg_sep
                    logger.info(f"✅ Extracted background audio (SFX/Music): {extracted_background_path}")
            else:
                logger.warning("⚠️ Audio Separator not available. Background preservation/cloning will be limited.")

        fresh_audio_paths = []
        current_ref = ref_audio_path or extracted_vocals_path
        
        for i, scene in enumerate(script.get("scenes", [])):
            # Prioritize text_to_audio_prompt for rescripting
            text = scene.get("text_to_audio_prompt") or scene.get("voiceover_text") or scene.get("dialogue")
            if isinstance(text, dict): text = " ".join(text.values())
            
            if text:
                try:
                    logger.info(f"🎙️ Generating audio for scene {i+1}...")
                    p = await engine.generate_narration(
                        text=text,
                        voice_id=voice_id or "en-US-AriaNeural",
                        provider=audio_provider,
                        reference_audio=current_ref,
                        output_path=Path(f"/tmp/gen_audio_{i}.mp3")
                    )
                    fresh_audio_paths.append(p)
                except Exception as e:
                    logger.error(f"❌ Failed to generate audio for scene {i}: {e}")
        
        local_audio = fresh_audio_paths
    else:
        local_audio = []
    
    # 4. Color Grading
    if assembly and assembly.get("color_grading"):
        logger.info("🎨 Applying Color Grading...")
        stitched_path = editor.apply_color_grading(
            stitched_path, 
            assembly["color_grading"],
            output_path=Path("/tmp/stitched_graded.mp4")
        )

    # Calculate Duration
    try:
        probe = ffmpeg.probe(str(stitched_path))
        total_duration = float(probe['format']['duration'])
    except:
        total_duration = len(local_clips) * 5.0

    # 5. Audio Construction
    bg_music_local = None
    
    # A. Dynamic Soundtrack (Priority)
    if assembly and assembly.get("soundtrack"):
        try:
            bg_music_local = await _generate_dynamic_soundtrack(assembly["soundtrack"], script, total_duration)
        except Exception as e:
            logger.error(f"❌ Dynamic soundtrack failed: {e}")
    
    # B. Fallback to existing logic if no dynamic track
    if not bg_music_local:
         # ... (existing selection logic) ...
         bg_music_cfg = channel_config.get("bgMusic")
         if bg_music_cfg:
             try:
                bg_music_local = storage.download(bg_music_cfg, "/tmp/bg_music_manual.mp3")
             except: pass
         else:
             from .music_generator import generate_background_music
             mood = script.get("music_mood") or "calm"
             try:
                 bg_music_local = generate_background_music(total_duration, mood)
             except: pass

    # 6. Final Mix
    final_audio_path = stitched_path # Default if no audio added
    
    # If we generated fresh audio, treat it like documentary mode (VO + BGM)
    if has_fresh_audio:
        logger.info("🎛️ Mixing Fresh TTS Audio with Background Music...")
        
        # Prepare Tracks for Mixing
        tracks_to_mix = []
        
        # 1. Voiceover (Main) - Concatenate first
        concat_vo_path = Path("/tmp/concat_vo_final.mp3")
        with open("/tmp/concat_vo_list.txt", "w") as f:
            for p in local_audio:
                f.write(f"file '{Path(p).absolute().as_posix()}'\n")
        (
            ffmpeg
            .input("/tmp/concat_vo_list.txt", format="concat", safe=0)
            .output(str(concat_vo_path), c="copy")
            .overwrite_output()
            .run(quiet=True, cmd=editor.ffmpeg_cmd)
        )
        tracks_to_mix.append({"path": concat_vo_path, "volume": 1.25}) # Boost VO slightly
        
        # 2. Original Background (Music/SFX preserved from clips)
        if extracted_background_path and extracted_background_path.exists():
             tracks_to_mix.append({"path": extracted_background_path, "volume": 0.4})
             
        # 3. Additional Dynamic Music (if any)
        if bg_music_local:
             tracks_to_mix.append({"path": bg_music_local, "volume": 0.15})
             
        # Mix multiple tracks
        try:
            final_audio_path = editor.mix_multiple_tracks(tracks_to_mix, "/tmp/final_audio_mix.mp3")
        except Exception as e:
            logger.error(f"❌ Mixing failed: {e}")
            final_audio_path = concat_vo_path # Fallback to just VO
            
        # Generate Subtitles
        subtitle_scenes = []
        for s in script.get("scenes", []):
             sc = s.copy()
             if not sc.get("voiceover_text") and sc.get("dialogue"):
                 sc["voiceover_text"] = sc["dialogue"]
             subtitle_scenes.append(sc)
        srt_path = subtitle_engine.generate_from_script(subtitle_scenes, "/tmp/subtitles.srt")
        
        # Finalize Video
        final_path = editor.finalize(stitched_path, final_audio_path, srt_path, "/tmp/final_video.mp4")
        
        # Cleanup
        for f in local_audio: Path(f).unlink(missing_ok=True)
        if extracted_background_path: extracted_background_path.unlink(missing_ok=True)
        if extracted_vocals_path: extracted_vocals_path.unlink(missing_ok=True)
        if concat_vo_path: concat_vo_path.unlink(missing_ok=True)
        Path("/tmp/stitched_source.mp3").unlink(missing_ok=True)
        Path("/tmp/concat_vo_list.txt").unlink(missing_ok=True)
        logger.info(f"✨ Advanced Audio Rescripting complete. Final video: {final_path}")
        
    elif video_type == "documentary" and audio_keys:
        # Documentary: Download VO and Mix
        local_audio = [storage.download(k, f"/tmp/audio_{i}.mp3") for i, k in enumerate(audio_keys)]
        
        # Generate Subtitles
        srt_path = subtitle_engine.generate_srt(script, "/tmp/subtitles.srt")
        
        # Mix VO + BGM
        # Use new mix logic for consistency?
        # For now keep old flow for 'standard' documentary unless we want to separate there too?
        # User request was specifically for "original grok video clip" which usually implies the 'Story' mode converted/overridden or hybrid.
        
        # Let's stick to old simple mix since we don't have "original grok audio" here usually? 
        # Actually documentary mode builds from clips too. 
        # If the clips have sound, we might want to keep it? 
        # BUT usually Grok clips are silent or generic in docu mode?
        # Let's leave docu mode as is for now to avoid regression, optimizing the 'fresh_audio' (Story->Docu conversion) path.
        final_audio_path = editor.mix_audio(local_audio, bg_music_local, "/tmp/final_audio_mix.mp3")
        
        # Finalize
        final_path = editor.finalize(stitched_path, final_audio_path, srt_path, "/tmp/final_video.mp4")
        
        # Cleanup VO
        for f in local_audio: Path(f).unlink(missing_ok=True)
            
    else:
        # Story Mode (Original Audio): Audio already in stitched clips
        # We need to mix BGM with the *video's existing audio*
        
        if bg_music_local:
            if mute_source:
                 # If source is muted and no fresh audio, it's just BGM
                 final_audio_path = bg_music_local
            else:
                final_audio_path = editor.add_background_music(
                    stitched_path,
                    bg_music_local,
                    "/tmp/final_video_w_music.mp4",
                    music_volume=0.15
                )
        else:
            if mute_source:
                # Silent video? create silent audio track
                # editor.finalize will handle it? No, finalize expects audio path.
                # If mute_source and no BGM, we effectively have no audio track.
                # Creates a valid path with silent audio
                import shutil
                shutil.copy(stitched_path, "/tmp/silent.mp4") # Placeholder?
                # Actually, finalize() uses map 1:a. If we pass stitched_path as audio_path, it uses its audio.
                # If we want silence, we need a silent audio file.
                # For now assume mute_source isn't primary use case here.
                pass# We can generate 1s of silence or just rely on stitched_path having silent track (from anullsrc)
                final_audio_path = stitched_path # It has anullsrc audio track now
            else:
                final_audio_path = stitched_path
            
        # Subtitles for Story
        subtitle_scenes = []
        for s in script.get("scenes", []):
            sc = s.copy()
            if not sc.get("voiceover_text") and sc.get("dialogue"):
                sc["voiceover_text"] = sc["dialogue"]
            subtitle_scenes.append(sc)
            
        srt_path = subtitle_engine.generate_from_script(subtitle_scenes, "/tmp/subtitles.srt")
        
        final_path = editor.finalize(
             video_path=final_audio_path,
             audio_path=final_audio_path, # Embedded
             subtitle_path=srt_path,
             output_path="/tmp/final_video.mp4"
        )

    # Upload
    final_key = f"videos/{script['niche_id']}/{script['title'].replace(' ', '_')}.mp4"
    storage.upload(final_path, final_key)
    
    # Cleanup
    for c in local_clips: Path(c).unlink(missing_ok=True)
    if bg_music_local: Path(bg_music_local).unlink(missing_ok=True)
    
    return final_key



async def generate_seo_content(script: dict, channel_config: dict, background_image_key: str = None) -> dict:
    """Generate SEO-optimized content using LLM."""
    from .youtube_seo import YouTubeSEO
    from pathlib import Path
    
    storage = R2Storage()
    seo = YouTubeSEO()
    
    # Download background image if available
    background_image = None
    if background_image_key:
        background_image = Path(f"/tmp/bg_for_thumbnail.png")
        storage.download(background_image_key, background_image)
    
    # Get niche from script
    niche = script.get("niche_id", "default").split("_")[0] if "_" in script.get("niche_id", "") else script.get("niche_id", "default")
    
    # Get full script text for LLM analysis
    script_text = script.get("full_text") or "\n".join([s.get("voiceover_text", "") for s in script.get("scenes", [])])
    
    # Generate SEO content using LLM
    result = await seo.optimize_with_llm(
        script_text=script_text,
        topic=script.get("title", "Video"),
        niche=niche,
        background_image=background_image,
        output_dir=Path("/tmp")
    )
    
    return {
        "title": result.title,
        "description": result.description,
        "tags": result.tags,
        "thumbnail_path": str(result.thumbnail_path) if result.thumbnail_path else None
    }


async def upload_thumbnail(thumbnail_path: str, script: dict) -> str:
    """Upload thumbnail to R2."""
    from pathlib import Path
    
    storage = R2Storage()
    thumbnail_key = f"thumbnails/{script['niche_id']}/{script['title'].replace(' ', '_')}.jpg"
    storage.upload(Path(thumbnail_path), thumbnail_key, content_type="image/jpeg")
    
    return thumbnail_key


async def upload_to_youtube(video_key: str, script: dict, channel_config: dict, seo_result: dict = None, thumbnail_key: str = None) -> dict:
    """Upload video to YouTube as Private with SEO optimization and thumbnail."""
    from .youtube_uploader import YouTubeUploader
    
    storage = R2Storage()
    uploader = YouTubeUploader(niche_id=script['niche_id'])
    
    # Download final video
    local_video = storage.download(video_key, "/tmp/upload_video.mp4")
    
    # Download thumbnail if provided
    local_thumbnail = None
    if thumbnail_key:
        from pathlib import Path
        local_thumbnail = Path("/tmp/upload_thumbnail.jpg")
        storage.download(thumbnail_key, local_thumbnail)
    elif seo_result and seo_result.get("thumbnail_path"):
        from pathlib import Path
        local_thumbnail = Path(seo_result["thumbnail_path"])
    
    # --- Metadata Logic ---
    yt_data = script.get("youtube_upload") or {}
    metadata = yt_data.get("metadata", {})
    engagement = yt_data.get("engagement", {})
    
    # Priority 1: YouTubeUpload (Manual/Json)
    # Priority 2: SEO Result (LLM)
    # Priority 3: Fallback (Script/Config)
    
    title = metadata.get("title") or (seo_result.get("title") if seo_result else script['title'])
    description = metadata.get("description") or (seo_result.get("description") if seo_result else script['description'])
    
    tags = metadata.get("tags")
    if not tags:
        tags = seo_result.get("tags") if seo_result else channel_config.get("defaultTags", [])
        
    # Extended Metadata
    privacy_status = metadata.get("privacyStatus", "private")
    publish_at = metadata.get("publishAt")
    made_for_kids = metadata.get("madeForKids", False)
    category_id = metadata.get("categoryId", "22")
    playlist_name = metadata.get("playlistTitle")
    
    # Upload to YouTube
    result = await uploader.upload(
        video_path=local_video,
        title=title,
        description=description,
        tags=tags,
        thumbnail_path=local_thumbnail,
        privacy_status=privacy_status,
        category_id=category_id,
        made_for_kids=made_for_kids,
        publish_at=publish_at,
        playlist_name=playlist_name
    )
    
    # Engagement
    pinned_comment = engagement.get("pinnedComment")
    if pinned_comment:
        uploader.post_comment(result["video_id"], pinned_comment, pin=True)
    
    return result


async def update_video_status(video_id: str, status: str, metadata: dict = None):
    """Update video record in database."""
    from prisma import Prisma
    
    db = Prisma()
    await db.connect()
    
    update_data = {"status": status}
    if metadata:
        update_data["assets"] = metadata
    
    await db.video.update(
        where={"id": video_id},
        data=update_data
    )
    
    await db.disconnect()


# ============================================
# RATE LIMIT RECOVERY WORKFLOW
# ============================================

@inngest_client.create_function(
    fn_id="video-generation-recovery",
    trigger={"event": "video/generation.rate_limited"},
    retries=1,
)
async def rate_limit_recovery(ctx: Context) -> dict:
    """
    Handle rate limits by waiting and resuming.
    
    When Grok or HuggingFace rate limits hit:
    1. Save checkpoint (current scene index)
    2. Wait for rate limit reset (2 hours for Grok, varies for HF)
    3. Resume from checkpoint
    """
    video_id = ctx.event.data.get("video_id")
    checkpoint = ctx.event.data.get("checkpoint", {})
    wait_seconds = ctx.event.data.get("wait_seconds", 7200)  # Default 2 hours
    
    logger.warning(f"⏳ Rate limited on {video_id}, waiting {wait_seconds}s...")
    
    # Wait for rate limit reset
    await ctx.step.sleep("wait-for-reset", wait_seconds)
    
    # Re-trigger the main workflow with checkpoint
    await ctx.step.send_event(
        "resume-generation",
        {
            "name": "video/generation.started",
            "data": {
                "video_id": video_id,
                "resume_from_checkpoint": checkpoint,
                **ctx.event.data
            }
        }
    )
    
    return {"status": "resumed", "video_id": video_id}


async def _generate_dynamic_soundtrack(soundtrack_config: dict, script: dict, duration: float) -> Optional[Path]:
    """
    Generate soundtrack based on Final Assembly config.
    Decides between Stock Music (Mood) and AI Music (Prompt).
    """
    from .music_generator import generate_background_music, generate_music_with_ai, MusicLibrary
    
    bg_desc = soundtrack_config.get("background_music", "")
    if not bg_desc:
        return None
        
    logger.info(f"🎵 Generating Soundtrack: '{bg_desc}'")
    
    # 1. Analyze if it's a Stock Mood or Custom Prompt
    # Check if the description matches any known mood keys
    # specific moods often used: horror, happy, cinematic, etc.
    
    # Simple heuristic: If it's a single word, check stock first
    # If it's a sentence, use AI
    
    is_stock = False
    mood_candidate = bg_desc.lower().split(" ")[0].strip() # First word
    if mood_candidate in MusicLibrary.TRACKS:
        is_stock = True
        
    # Also check if user explicitly requested "Stock" or "AI" in metadata (advanced)
    
    generated_path = None
    
    if is_stock:
        logger.info(f"   ↳ Detected Stock Mood: {mood_candidate}")
        try:
            generated_path = generate_background_music(duration, mood_candidate)
        except Exception as e:
            logger.error(f"   ❌ Stock generation failed: {e}")
    else:
        logger.info(f"   ↳ Detected Custom Prompt. Attempting AI Generation...")
        try:
            # AI Music Gen is slow and has length limits (usually 30s max on free tier HF)
            # We might need to loop it if the video is long
            # For now, we generate a 10-30s clip and the editor will loop it if needed?
            # Actually simple editor just loops inputs.
            
            # Use 30s as standard generation length for background loop
             generated_path = await generate_music_with_ai(bg_desc, duration=30)
             
             if not generated_path:
                 logger.warning("   ⚠️ AI Generation returned None. Falling back to Stock 'Cinematic'.")
                 generated_path = generate_background_music(duration, "cinematic")
                 
        except Exception as e:
            logger.error(f"   ❌ AI Generation failed: {e}")
            logger.info("   ↳ Fallback to Stock 'Cinematic'")
            generated_path = generate_background_music(duration, "cinematic")
            
    return generated_path
