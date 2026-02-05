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
from typing import Any
from inngest import Inngest, Function, Context

from .inngest_client import inngest_client
from .cloud_storage import R2Storage

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
            animated_clips = partial_results["animated_clips"]
        
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
                seo_result
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


async def animate_scenes_with_grok(image_keys: list[str], script: dict) -> list[str]:
    """Animate scene images using Grok Imagine."""
    from .grok_agent import GrokAnimator
    
    animator = GrokAnimator()
    storage = R2Storage()
    clip_keys = []
    
    for i, (image_key, scene) in enumerate(zip(image_keys, script.get("scenes", []))):
        logger.info(f"🎥 Animating scene {i+1}")
        
        # Download image from R2
        local_image = storage.download(image_key, f"/tmp/scene_{i}.png")
        
        # Animate with Grok
        video_path = await animator.animate(
            image_path=local_image,
            motion_prompt=scene.get("motion_description", ""),
            duration=scene.get("duration_in_seconds", 10)
        )
        
        # Upload animated clip to R2
        clip_key = f"clips/{script['niche_id']}/scene_{i:03d}_animated.mp4"
        storage.upload(video_path, clip_key)
        clip_keys.append(clip_key)
    
    return clip_keys


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


async def render_final_video(
    clip_keys: list[str], 
    audio_keys: list[str], 
    script: dict,
    channel_config: dict
) -> str:
    """
    Render final video with transitions, audio, and subtitles.
    
    Modes:
    - story: Clips already have dialogue audio from Grok, just stitch them
    - documentary: Mix voiceover audio with clips
    """
    from .video_editor import FFmpegVideoEditor
    from .subtitle_engine import SubtitleEngine
    
    storage = R2Storage()
    editor = FFmpegVideoEditor()
    subtitle_engine = SubtitleEngine()
    
    video_type = script.get("video_type", "story")
    
    # Ensure we have storage space
    storage.ensure_storage_available(required_gb=1.0)
    
    # Download all clips
    local_clips = []
    for i, clip_key in enumerate(clip_keys):
        local_clips.append(storage.download(clip_key, f"/tmp/clip_{i}.mp4"))
    
    # Determine Output Resolution
    is_shorts = "shorts" in channel_config.get("nicheId", "").lower() or "shorts" in channel_config.get("styleSuffix", "").lower()
    target_res = (1080, 1920) if is_shorts else (1920, 1080)
    logger.info(f"📐 Stitching Resolution: {target_res} (Shorts={is_shorts})")

    # Stitch clips with transitions
    # Stitch clips with transitions
    stitched_path = editor.stitch_clips_with_transitions(
        local_clips, 
        "/tmp/stitched.mp4",
        target_resolution=target_res,
        transition_duration=0.4 # User requested 0.4s
    )
    
    # Calculate total duration for music generation
    # Estimate from clips count * 5s if unknown, or rely on actual video length later?
    # Better to probe the stitched video.
    try:
        import ffmpeg
        probe = ffmpeg.probe(str(stitched_path))
        total_duration = float(probe['format']['duration'])
    except:
        total_duration = len(local_clips) * 10.0 # Fallback
    
    if video_type == "documentary" and audio_keys:
        # DOCUMENTARY MODE: Mix voiceover with video
        logger.info("📚 Documentary mode: Adding voiceover audio")
        
        # Download audio files
        local_audio = []
        for i, audio_key in enumerate(audio_keys):
            local_audio.append(storage.download(audio_key, f"/tmp/audio_{i}.mp3"))
        
        # Generate subtitles
        srt_path = subtitle_engine.generate_srt(script, "/tmp/subtitles.srt")
        
        # Mix audio with background music
        bg_music = channel_config.get("bgMusic")
        bg_music_local = None
        
        if bg_music:
             # Manual Override
             try:
                bg_music_local = storage.download(bg_music, "/tmp/bg_music.mp3")
             except: None
        else:
             # Intelligent Selection
             from .music_generator import generate_background_music
             mood = script.get("music_mood", "calm") # Fallback to calm
             logger.info(f"🎶 Auto-selecting music for mood: {mood}")
             try:
                 bg_music_local = generate_background_music(total_duration, mood)
             except Exception as e:
                 logger.error(f"⚠️ Music generation failed: {e}. Skipping BGM.")
                 bg_music_local = None
        
        final_audio = editor.mix_audio(local_audio, bg_music_local, "/tmp/final_audio.mp3")
        
        # Combine video + audio + subtitles
        final_path = editor.finalize(
            video_path=stitched_path,
            audio_path=final_audio,
            subtitle_path=srt_path,
            output_path="/tmp/final_video.mp4"
        )
        
        # Cleanup audio files
        for audio_key in audio_keys:
            storage.delete_file(audio_key)
    else:
        # STORY MODE: Clips already have Grok's dialogue audio
        logger.info("🎭 Story mode: Using Grok's built-in audio, just stitching clips")
        
        # Optionally add background music (ducked under Grok audio)
        bg_music = channel_config.get("bgMusic")
        bg_music_local = None
        
        if bg_music:
             try:
                bg_music_local = storage.download(bg_music, "/tmp/bg_music.mp3")
             except: None
        else:
             from .music_generator import generate_background_music
             mood = script.get("music_mood", "calm")
             logger.info(f"🎶 Auto-selecting music for mood: {mood}")
             try:
                 bg_music_local = generate_background_music(total_duration, mood)
             except Exception as e:
                 logger.error(f"⚠️ Music generation failed: {e}. Skipping BGM.")
                 bg_music_local = None

        if bg_music_local:
            final_audio_path = editor.add_background_music(
                stitched_path,
                bg_music_local,
                "/tmp/final_video_music.mp4",
                music_volume=0.15  # Keep low so dialogue is clear
            )
        else:
            final_audio_path = stitched_path

        # Generate Subtitles (Even for Story Mode)
        # Use dialogue if present, otherwise voiceover_text
        logger.info("📝 Generating subtitles for Story Mode...")
        # Note: generate_from_script expects 'voiceover_text' usually. 
        # We need to map 'dialogue' to 'voiceover_text' if missing.
        subtitle_scenes = []
        for s in script.get("scenes", []):
            scene_copy = s.copy()
            if not scene_copy.get("voiceover_text") and scene_copy.get("dialogue"):
                 scene_copy["voiceover_text"] = scene_copy["dialogue"]
            subtitle_scenes.append(scene_copy)

        srt_path = subtitle_engine.generate_from_script(subtitle_scenes, "/tmp/subtitles.srt")
        
        # Burn Subtitles
        final_path = editor.finalize(
            video_path=final_audio_path,
            audio_path=final_audio_path, # Audio is already in the video file
            subtitle_path=srt_path,
            output_path="/tmp/final_video.mp4"
        )
    
    # Upload final video to R2
    final_key = f"videos/{script['niche_id']}/{script['title'].replace(' ', '_')}.mp4"
    storage.upload(final_path, final_key)
    
    # Cleanup raw clip files
    for clip_key in clip_keys:
        storage.delete_file(clip_key)
    
    return final_key


async def generate_seo_content(script: dict, channel_config: dict, background_image_key: str = None) -> dict:
    """Generate SEO-optimized title, description, tags, and thumbnail."""
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
    
    # Generate SEO content
    result = seo.optimize(
        topic=script.get("title", "Video"),
        niche=niche,
        script_summary=script.get("description", ""),
        background_image=background_image,
        base_tags=channel_config.get("defaultTags", []),
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


async def upload_to_youtube(video_key: str, script: dict, channel_config: dict, seo_result: dict = None) -> dict:
    """Upload video to YouTube as Private with SEO optimization."""
    from .youtube_uploader import YouTubeUploader
    
    storage = R2Storage()
    uploader = YouTubeUploader(niche_id=script['niche_id'])
    
    # Download final video
    local_video = storage.download(video_key, "/tmp/upload_video.mp4")
    
    # Use SEO-optimized data if available
    title = seo_result.get("title", script['title']) if seo_result else script['title']
    description = seo_result.get("description", script['description']) if seo_result else script['description']
    tags = seo_result.get("tags", channel_config.get("defaultTags", [])) if seo_result else channel_config.get("defaultTags", [])
    
    # Upload to YouTube
    result = await uploader.upload(
        video_path=local_video,
        title=title,
        description=description,
        tags=tags,
        privacy_status="private"  # Always start as private
    )
    
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
