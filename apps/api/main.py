"""
AI Video Factory - FastAPI Orchestrator

Main application entry point with endpoints for script submission,
job status, and Inngest webhook handling.
"""
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import os
import sys
import asyncio
import uuid
from dotenv import load_dotenv

# Fix for Playwright NotImplementedError on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load env vars from root .env
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

# Add packages to path
sys.path.insert(0, str(os.path.dirname(__file__) + "/../../packages"))

from contextlib import asynccontextmanager
from prisma import Prisma
from services.cloud_storage import R2Storage
from services.script_generator import ScriptGenerator
from services.email_service import email_service

# Global Prisma client
db = Prisma()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to DB on startup
    await db.connect()
    yield
    # Disconnect on shutdown
    await db.disconnect()

app = FastAPI(
    title="AI Video Factory",
    description="Automated video production pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Lock for Browser Automation (Playwright Profile Serialization)
BROWSER_LOCK = asyncio.Lock()

# ============================================
# Models
# ============================================
class SFXMarker(BaseModel):
    sfx_key: str
    timestamp: float


class Scene(BaseModel):
    voiceover_text: str
    character_pose_prompt: str
    background_description: str
    duration_in_seconds: int = 10
    camera_angle: str = "medium shot"
    motion_description: str = ""
    dialogue: Optional[str] = None
    character_name: str = "Character"
    emotion: str = "neutrally"
    characterId: Optional[str] = None # Support for multi-character cast
    sfx_markers: list[SFXMarker] = []

class VideoScript(BaseModel):
    niche_id: str
    title: str
    description: str
    scenes: list[Scene]
    video_type: str = "story"  # "story" (Grok audio) or "documentary" (voiceover needed)
    youtube_upload: Optional[dict] = None
    final_assembly: Optional[dict] = None

class JobStatus(BaseModel):
    job_id: str
    status: str
    current_scene: int = 0
    total_scenes: int = 0
    message: Optional[str] = None

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    voiceId: Optional[str] = None
    styleSuffix: Optional[str] = None
    nicheId: Optional[str] = None


# ============================================
# Endpoints
# ============================================

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "video-factory-api"}


@app.get("/health/full")
async def full_health_check():
    """
    Comprehensive health check for all services.
    
    Returns status of:
    - Database connection
    - R2 storage
    - HuggingFace API
    - Gemini API
    - Inngest dev server
    """
    from services.production import HealthChecker
    
    checker = HealthChecker()
    results = await checker.run_all()
    
    return {
        "healthy": checker.is_healthy(results),
        "checks": [r.to_dict() for r in results],
        "timestamp": results[0].timestamp.isoformat() if results else None
    }


@app.get("/metrics")
async def get_metrics():
    """
    Get monitoring metrics for dashboard.
    
    Returns:
    - Job statistics (total, completed, failed, processing)
    - Storage usage
    - GPU quota remaining
    """
    from services.production import MonitoringData
    
    monitor = MonitoringData()
    return await monitor.get_dashboard_stats()


# --- Storage Management ---

@app.get("/storage/stats")
async def get_storage_stats():
    """Get R2 storage usage statistics."""
    try:
        storage = R2Storage()
        stats = storage.get_bucket_size()
        return {
            "total_gb": stats['total_gb'],
            "object_count": stats['object_count'],
            "free_tier_remaining_gb": stats['free_tier_remaining_gb'],
            "free_tier_limit_gb": storage.FREE_TIER_LIMIT_GB,
            "usage_percent": round((stats['total_gb'] / storage.FREE_TIER_LIMIT_GB) * 100, 1)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get storage stats: {str(e)}")


@app.post("/storage/cleanup")
async def trigger_storage_cleanup(
    clips_older_than_days: int = 7,
    videos_older_than_days: int = 30
):
    """Manually trigger storage cleanup."""
    try:
        storage = R2Storage()
        
        clips_result = storage.cleanup_old_clips(older_than_days=clips_older_than_days)
        videos_result = storage.cleanup_uploaded_videos(older_than_days=videos_older_than_days)
        
        new_stats = storage.get_bucket_size()
        
        return {
            "clips_deleted": clips_result['deleted_count'],
            "videos_deleted": videos_result['deleted_count'],
            "total_freed_gb": round(
                (clips_result['freed_bytes'] + videos_result['freed_bytes']) / (1024**3), 
                2
            ),
            "new_total_gb": new_stats['total_gb'],
            "free_tier_remaining_gb": new_stats['free_tier_remaining_gb']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.post("/tools/swap-audio")
async def swap_audio_tool(
    video1: UploadFile = File(...),
    video2: UploadFile = File(...)
):
    """
    Swap audio streams between two video files.
    """
    try:
        from services.video_editor import FFmpegVideoEditor
        
        editor = FFmpegVideoEditor()
        storage = R2Storage()
        
        # 1. Save uploads
        print(f"DEBUG: Receiving uploads. V1: {video1.filename}, V2: {video2.filename}")
        v1_path = editor.output_dir / f"{uuid.uuid4()}_{video1.filename}"
        v2_path = editor.output_dir / f"{uuid.uuid4()}_{video2.filename}"
        
        content1 = await video1.read()
        content2 = await video2.read()
        print(f"DEBUG: Saved V1 ({len(content1)} bytes) to {v1_path}")
        print(f"DEBUG: Saved V2 ({len(content2)} bytes) to {v2_path}")

        with open(v1_path, "wb") as f:
            f.write(content1)
        with open(v2_path, "wb") as f:
            f.write(content2)
            
        # 2. Swap
        print(f"DEBUG: calling swap_audio_streams...")
        out1_path, out2_path = editor.swap_audio_streams(v1_path, v2_path)
        
        if out1_path.exists():
            print(f"DEBUG: Out1 created at {out1_path}, size: {out1_path.stat().st_size} bytes")
        else:
            print(f"DEBUG: Out1 MISSING at {out1_path}")

        if out2_path.exists():
            print(f"DEBUG: Out2 created at {out2_path}, size: {out2_path.stat().st_size} bytes")
        else:
            print(f"DEBUG: Out2 MISSING at {out2_path}")

        # 3. Upload results
        # Use simple filenames for keys
        timestamp = uuid.uuid4().hex[:8]
        key1 = f"tools/swapped_{timestamp}_1.mp4"
        key2 = f"tools/swapped_{timestamp}_2.mp4"
        
        print(f"DEBUG: Uploading to keys: {key1}, {key2}")
        storage.upload(out1_path, remote_key=key1)
        storage.upload(out2_path, remote_key=key2)
        
        # 4. Get URLs
        url1 = storage.get_url(key1)
        url2 = storage.get_url(key2)
        print(f"DEBUG: Generated URLs: \n  {url1}\n  {url2}")
        
        # Cleanup temp files
        def safe_delete(p):
            try:
                if p.exists(): p.unlink()
            except: pass
            
        safe_delete(v1_path)
        safe_delete(v2_path)
        safe_delete(out1_path)
        safe_delete(out2_path)
        
        return {
            "video1_url": url1,
            "video2_url": url2
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Notifications ---

class EmailNotification(BaseModel):
    type: str  # 'success' or 'error'
    project_name: str
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    step: Optional[str] = None


@app.post("/notifications/email")
async def send_email_notification(notification: EmailNotification):
    """
    Send email notification for video completion or error.
    
    Used by frontend 1-click automation to notify user when done.
    """
    if not email_service.is_configured():
        return {"success": False, "message": "Email not configured - check SMTP env vars"}
    
    if notification.type == "success":
        success = email_service.send_video_complete(
            project_name=notification.project_name,
            video_url=notification.video_url or "N/A"
        )
    elif notification.type == "error":
        success = email_service.send_video_error(
            project_name=notification.project_name,
            error_message=notification.error_message or "Unknown error",
            step=notification.step
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid notification type")
    
    return {"success": success}


@app.get("/notifications/status")
async def get_notification_status():
    """Check if email notifications are configured."""
    return {
        "configured": email_service.is_configured(),
        "smtp_server": email_service.smtp_server,
        "notification_email": email_service.notification_email or "Not set"
    }


@app.get("/channels")
async def list_channels():
    """List all available niche configurations from DB."""
    channels = await db.channel.find_many()
    
    # Generate presigned URLs for thumbnails/anchors
    storage = R2Storage()
    response = []
    
    for c in channels:
        anchor_url = storage.get_url(c.anchorImage) if c.anchorImage else None
        response.append({
            "id": c.nicheId,
            "name": c.name,
            "style": c.styleSuffix[:50] + "...",
            "anchor_url": anchor_url
        })
        
    print(f"🔍 Found {len(channels)} channels in DB")
    return {"channels": response}


@app.get("/channels/{niche_id}")
async def get_channel_config(niche_id: str):
    """Get configuration for a specific niche from DB."""
    channel = await db.channel.find_unique(where={"nicheId": niche_id})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    data = channel.model_dump()
    
    # Sign URLs
    storage = R2Storage()
    if data.get("anchorImage"):
        data["anchorImageUrl"] = storage.get_url(data["anchorImage"])
    if data.get("bgMusic"):
        data["bgMusicUrl"] = storage.get_url(data["bgMusic"])
        
    return data


@app.post("/channels")
async def create_channel(channel: ChannelUpdate):
    """Create a new channel configuration."""
    if not channel.nicheId:
        # Auto-generate nicheId from name if not provided
        channel.nicheId = channel.name.lower().replace(" ", "-") if channel.name else "new-channel"

    # Check if exists
    existing = await db.channel.find_unique(where={"nicheId": channel.nicheId})
    if existing:
         raise HTTPException(status_code=400, detail="Channel ID already exists")

    new_channel = await db.channel.create(
        data={
            "nicheId": channel.nicheId,
            "name": channel.name or "New Channel",
            "voiceId": channel.voiceId or "en-US-AriaNeural",
            "styleSuffix": channel.styleSuffix or "Cinematic style",
            "defaultTags": []
        }
    )
    return new_channel


@app.put("/channels/{niche_id}")
async def update_channel(niche_id: str, channel: ChannelUpdate):
    """Update textual configuration for a channel."""
    existing = await db.channel.find_unique(where={"nicheId": niche_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    updated = await db.channel.update(
        where={"nicheId": niche_id},
        data={
            k: v for k, v in channel.model_dump().items() 
            if v is not None and k != "nicheId"
        }
    )
    return updated


# --- Character Management Endpoints ---

@app.get("/channels/{niche_id}/characters")
async def list_characters(niche_id: str):
    """List all characters for a specific channel."""
    channel = await db.channel.find_unique(
        where={"nicheId": niche_id},
        include={"characters": True}
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    storage = R2Storage()
    response = []
    
    for char in channel.characters:
        response.append({
            "id": char.id,
            "name": char.name,
            "imageUrl": storage.get_url(char.imageUrl)
        })
        
    return {"characters": response}


@app.post("/channels/{niche_id}/characters")
async def create_character(
    niche_id: str,
    name: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload character image and create record."""
    channel = await db.channel.find_unique(where={"nicheId": niche_id})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    # 1. Upload to R2
    storage = R2Storage()
    ext = file.filename.split('.')[-1]
    safe_name = name.lower().replace(" ", "_")
    key = f"assets/{niche_id}/characters/{safe_name}_{uuid.uuid4().hex[:8]}.{ext}"
    
    content = await file.read()
    storage.upload_asset(content, key, file.content_type)
    
    # 2. Create DB record
    char = await db.character.create(
        data={
            "channelId": channel.id,
            "name": name,
            "imageUrl": key,
        }
    )
    
    return {
        "id": char.id,
        "name": char.name,
        "imageUrl": storage.get_url(key)
    }

@app.delete("/characters/{char_id}")
async def delete_character(char_id: str):
    """Delete a character."""
    await db.character.delete(where={"id": char_id})
    return {"status": "deleted"}


# --- Asset Upload & Script Submission ---

@app.post("/channels/{niche_id}/upload")
async def upload_channel_asset(
    niche_id: str,
    file: UploadFile = File(...),
    asset_type: str = Form(...) # 'anchor' or 'music'
):
    """Upload channel assets (anchor image or bg music) to R2."""
    channel = await db.channel.find_unique(where={"nicheId": niche_id})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # 1. Upload to R2
    storage = R2Storage()
    ext = file.filename.split('.')[-1]
    key = f"assets/{niche_id}/{asset_type}.{ext}"
    
    content = await file.read()
    storage.upload_asset(content, key, file.content_type)
    
    # 2. Update DB record
    update_data = {}
    if asset_type == "anchor":
        update_data["anchorImage"] = key
    elif asset_type == "music":
        update_data["bgMusic"] = key
        
    updated_channel = await db.channel.update(
        where={"nicheId": niche_id},
        data=update_data
    )
    
    # 3. Get Presigned URL for immediate display
    url = storage.get_url(key)
    
    return {
        "key": key,
        "url": url,
        "updated_channel": updated_channel.model_dump() 
    }


# --- Script Generation ---

class GenerateScriptRequest(BaseModel):
    topic: str
    niche_id: str
    scene_count: int = 5
    video_type: str = "story"  # "story" or "documentary"

class GenerateStoryRequest(BaseModel):
    story_idea: str
    video_length: str  # "short" or "long"
    niche_id: str

class GenerateBreakdownRequest(BaseModel):
    story_narrative: str
    video_length: str
    video_type: str
    niche_id: str

class AnalyzeMoodRequest(BaseModel):
    script: str
    title: str = ""
    niche: str = ""

class GenerateImageRequest(BaseModel):
    character_name: str
    prompt: str
    niche_id: str
    is_shorts: bool = False

class GenerateSceneImageRequest(BaseModel):
    scene_index: int
    prompt: str
    niche_id: str
    character_images: list[dict]  # list of {name, imageUrl}
    is_shorts: bool = False

class GenerateVideoRequest(BaseModel):
    scene_index: int
    imageUrl: str
    prompt: str
    dialogue: Optional[str] = None
    camera_angle: Optional[str] = "Medium Shot"
    niche_id: str

@app.post("/scripts/generate")
async def generate_script(request: GenerateScriptRequest):
    """Generate a video script using Gemini 2.0 Flash."""
    # ... existing implementation ...
    # Get channel config for style
    channel = await db.channel.find_unique(
        where={"nicheId": request.niche_id},
        include={"characters": True}
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    try:
        generator = ScriptGenerator()
        script = await generator.generate(
            topic=request.topic,
            niche_style=channel.styleSuffix or "Cinematic style",
            scene_count=request.scene_count
        )
        
        # Map characters to scenes if available
        characters = []
        if channel.characters:
            storage = R2Storage()
            for char in channel.characters:
                characters.append({
                    "id": char.id,
                    "name": char.name,
                    "imageUrl": storage.get_url(char.imageUrl)
                })
        
        return {
            "title": script.title,
            "description": script.description,
            "scenes": [s.model_dump() for s in script.scenes],
            "characters": characters,
            "niche_id": request.niche_id,
            "video_type": request.video_type  # Include video type in response
        }
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Script generation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")


@app.post("/scripts/generate-story")
async def generate_story(request: GenerateStoryRequest):
    """Stage 1: Generate story narrative."""
    channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # scene_count = 12 if request.video_length == "short" else 45
    scene_count = 5  # Increased to 5 per user request
    
    try:
        generator = ScriptGenerator()
        narrative = await generator.generate_story_narrative(
            story_idea=request.story_idea,
            scene_count=scene_count,
            style=channel.styleSuffix or "Pixar/Disney 3D animation"
        )
        print(f"✅ Generated narrative length: {len(narrative)}")
        print(f"📝 Narrative preview: {narrative[:100]}...")
        
        return {"narrative": narrative}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR in generate-story: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scripts/generate-breakdown")
async def generate_breakdown(request: GenerateBreakdownRequest):
    """Stage 2: Generate technical breakdown from narrative."""
    channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Dynamic scene count based on format
    scene_count = 12 if request.video_length == "short" else 40
    
    try:
        generator = ScriptGenerator()
        
        # 0. Check for JSON Script (Explicit Structure)
        if request.story_narrative.strip().startswith("{"):
            try:
                print("ℹ️ JSON Script detected. Attempting direct parse...")
                breakdown = generator.parse_json_script(request.story_narrative)
            except Exception as e:
                print(f"⚠️ JSON parse failed: {e}. Falling back to standard detection.")
                breakdown = None
        else:
            breakdown = None

        if not breakdown:
            # Check for ANY structured script markers (very flexible detection)
            narrative_upper = request.story_narrative.upper()
            
            # Extended list of markers that indicate a structured storyboard/script
            structure_markers = [
                "CHARACTER MASTER PROMPTS", "MASTER CHARACTER", "CHARACTER BIOS",
                "PART 1", "PART 2", "PART 3",
                "STEP 1", "STEP 2", "STORYBOARD",
                "SCENE 1", "SCENE 2", "SCENE:", 
                "TEXT-TO-IMAGE PROMPT", "IMAGE-TO-VIDEO PROMPT",
                "MASTER TEXT-TO-IMAGE", "TEXT TO IMAGE",
                "DIALOGUE:", "SHOT:", "SHOT TYPE:",
                "— MASTER", "- MASTER", "– MASTER",
            ]
            
            is_manual = any(marker in narrative_upper for marker in structure_markers)
            
            # USER REQUEST: Directly use Hugging Face LLM to parse the script (Skip Regex)
            if is_manual:
                print(f"ℹ️ Structured Script Detected! Directly using LLM extraction...")
                try:
                    # 1. Try Hugging Face
                    breakdown = await generator.parse_manual_script_llm(request.story_narrative)
                except Exception as e_hf:
                    print(f"⚠️ Hugging Face Extraction Failed: {e_hf}")
                    
                    try:
                        # 2. Try Gemini Fallback
                        print(f"ℹ️ Attempting Gemini Fallback...")
                        breakdown = await generator.parse_manual_script_gemini(request.story_narrative)
                    except Exception as e_gemini:
                        print(f"⚠️ Gemini Extraction Failed: {e_gemini}")
                        
                        # 3. Fallback to Regex Parser
                        print(f"ℹ️ Falling back to Regex Parser...")
                        breakdown = generator.parse_manual_script(request.story_narrative)
            else:
                print(f"⚠️ No known structure markers found. Attempting LLM extraction as fallback...")
                try:
                    breakdown = await generator.parse_manual_script_llm(request.story_narrative)
                except Exception as llm_error:
                    print(f"⚠️ LLM extraction failed: {llm_error}. Falling back to AI generation...")
                    breakdown = await generator.generate_technical_breakdown(
                        story_narrative=request.story_narrative,
                        scene_count=scene_count,
                        style=channel.styleSuffix or "High-quality Pixar/Disney 3D Render"
                    )
        
        # Implement Thumbnail Prompt Generation
        thumbnail_prompt = await generator.generate_viral_thumbnail_prompt(
            request.story_narrative,
            niche=channel.nicheId if 'channel' in locals() and channel else "general"
        )
        
        # DEBUG: Log what we're returning
        result = breakdown.model_dump()
        result["thumbnail_prompt"] = thumbnail_prompt
        
        print(f"📊 Returning breakdown with {len(result.get('scenes', []))} scenes and {len(result.get('characters', []))} characters")
        print(f"   🖼️ Thumbnail Prompt: {thumbnail_prompt[:50]}...")
        
        if result.get('characters'):
            print(f"   👥 Characters: {', '.join([c['name'] for c in result['characters']])}")
        for i, scene in enumerate(result.get('scenes', [])):
            cpp = scene.get('character_pose_prompt', '')[:50] or 'EMPTY'
            img = scene.get('text_to_image_prompt', '')[:50] or 'EMPTY'
            print(f"   Scene {i+1}: character_pose_prompt={cpp}... | text_to_image_prompt={img}...")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR in generate-breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scripts/analyze-mood")
async def analyze_mood(request: AnalyzeMoodRequest):
    """Stage 3: Analyze script mood to recommend background music."""
    try:
        from services.mood_analyzer import MoodAnalyzer
        print(f"🧠 AI Mood Analysis requested for script: '{request.title}'")
        analyzer = MoodAnalyzer()
        
        # Analyze Based on script content
        mood = analyzer.analyze_mood(
            title=request.title or "Untitled",
            niche=request.niche or "general",
            description=request.script
        )
        
        print(f"   💡 Recommendation: {mood}")
        return {"mood": mood}
    except Exception as e:
        print(f"⚠️ Mood analysis failed: {e}")
        return {"mood": "auto"}


class GenerateBatchRequest(BaseModel):
    prompts: list[str]
    niche_id: str
    style_suffix: str = ""
    is_shorts: bool = False
    character_images: list[dict] = [] # Added for character consistency

@app.post("/scenes/generate-batch")
async def generate_scene_batch(request: GenerateBatchRequest):
    """Generate multiple scene images using WhiskAgent (Bulk Mode)."""
    try:
        from services.whisk_agent import WhiskAgent
        from services.cloud_storage import R2Storage
        import uuid
        
        print(f"🚀 Starting Batch Generation for {len(request.prompts)} scenes...")
        
        # Initialize Agent
        # headless=False allows user to see/debug, but for pure automation True is better.
        # headless=False allows user to see/debug.
        # For bulk stability, we can run headless, but visible is often safer for Whisk.
        # Let's verify WhiskAgent default. It defaults to False (Headful).
        agent = WhiskAgent(headless=False) 
        
        # Character Reference Downloads
        char_local_paths = []
        import httpx
        import tempfile
        from pathlib import Path
        
        if request.character_images:
            print(f"📥 Downloading {len(request.character_images)} character references for bulk run...")
            async with httpx.AsyncClient() as client:
                for char in request.character_images:
                    url = char.get("imageUrl")
                    if not url: continue
                    try:
                        resp = await client.get(url, follow_redirects=True)
                        resp.raise_for_status()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            tmp.write(resp.content)
                            char_local_paths.append(Path(tmp.name))
                    except Exception as e:
                        print(f"⚠️ Failed to download character ref {url}: {e}")

        # Run Batch
        images_bytes = await agent.generate_batch(
            prompts=request.prompts,
            is_shorts=request.is_shorts,
            style_suffix=request.style_suffix,
            delay_seconds=5,
            character_paths=char_local_paths
        )
        
        # Process & Upload Results
        storage = R2Storage()
        results = []
        
        for i, img_bytes in enumerate(images_bytes):
            if not img_bytes:
                results.append(None)
                continue
                
            image_key = f"scenes/{request.niche_id}/batch_{uuid.uuid4().hex[:8]}_scene_{i}.png"
            storage.upload_asset(img_bytes, image_key, content_type="image/png")
            image_url = storage.get_url(image_key)
            results.append(image_url)
            print(f"✅ Batch Image {i+1} uploaded: {image_url}")
            
        return {"imageUrls": results}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await agent.close()
        # Clean up character temp files
        for p in char_local_paths:
            if p.exists():
                try: p.unlink() 
                except: pass

@app.post("/characters/generate-image")
async def generate_character_image(request: GenerateImageRequest):
    """Generate a character reference image using WhiskAgent."""
    agent = None
    try:
        from services.whisk_agent import WhiskAgent
        from services.cloud_storage import R2Storage
        import uuid
        
        print(f"🎨 Generating master character image for: {request.character_name}")
        print(f"   Prompt: {request.prompt[:100]}...")
        
        # Determine Style Suffix (Fetch from DB based on Niche)
        channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
        style_suffix = channel.styleSuffix if (channel and channel.styleSuffix) else ""
        
        # Initialize Agent and Generate with Global Lock
        async with BROWSER_LOCK:
            agent = WhiskAgent(headless=False)
            image_bytes = await agent.generate_image(
                prompt=request.prompt,
                is_shorts=request.is_shorts,
                style_suffix=style_suffix
            )
        
        if not image_bytes:
            raise HTTPException(status_code=500, detail="Whisk failed to generate character image")

        # Upload
        storage = R2Storage()
        image_key = f"characters/{request.niche_id}/{request.character_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
        storage.upload_asset(image_bytes, image_key, content_type="image/png")
        image_url = storage.get_url(image_key)
        
        print(f"✅ Character image uploaded: {image_url}")
        
        return {"image_url": image_url}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating character image: {e}")
    finally:
        if agent:
            await agent.close()

async def generate_scene_image(request: GenerateSceneImageRequest):
    """Generate scene image using WhiskAgent (Single Mode)."""
    agent = None
    try:
        from services.whisk_agent import WhiskAgent
        from services.cloud_storage import R2Storage
        import uuid
        
        print(f"🎨 Generating single scene image for scene {request.scene_index}")
        print(f"   Prompt: {request.prompt[:100]}...")
        
        # Determine Style Suffix (Fetch from DB based on Niche)
        channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
        style_suffix = channel.styleSuffix if (channel and channel.styleSuffix) else ""
        
        # Character Reference Downloads
        char_local_paths = []
        import httpx
        import tempfile
        from pathlib import Path
        
        if request.character_images:
            print(f"📥 Downloading {len(request.character_images)} character references...")
            async with httpx.AsyncClient() as client:
                for char in request.character_images:
                    url = char.get("imageUrl")
                    if not url: continue
                    try:
                        resp = await client.get(url, follow_redirects=True)
                        resp.raise_for_status()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            tmp.write(resp.content)
                            char_local_paths.append(Path(tmp.name))
                    except Exception as e:
                        print(f"⚠️ Failed to download character ref {url}: {e}")

        # Initialize Agent
        agent = WhiskAgent(headless=False)
        
        # Generate
        image_bytes = await agent.generate_image(
            prompt=request.prompt,
            is_shorts=request.is_shorts, # Use passed value
            style_suffix=style_suffix,
            character_paths=char_local_paths
        )
        
        if not image_bytes:
            raise HTTPException(status_code=500, detail="Whisk failed to generate image")

        # Upload
        storage = R2Storage()
        image_key = f"scenes/{request.niche_id}/{uuid.uuid4().hex[:8]}_scene_{request.scene_index}.png"
        storage.upload_asset(image_bytes, image_key, content_type="image/png")
        image_url = storage.get_url(image_key)
        
        print(f"✅ Image uploaded: {image_url}")
        
        return {"imageUrl": image_url}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating scene image: {e}")
    finally:
        if agent:
            await agent.close()
        # Clean up character temp files
        for p in char_local_paths:
            if p.is_file():
                try: os.unlink(str(p))
                except: pass



class GenerateBatchSceneImagesRequest(BaseModel):
    niche_id: str
    scenes: list[dict] # {index: int, prompt: str}
    character_images: list[dict] = [] # {name: str, imageUrl: string}
    video_type: str = "story" # "story" (default/landscape) or "shorts" (9:16)
    thumbnail_prompt: Optional[str] = None # Optional viral thumbnail prompt

class GenerateCharacterBatchRequest(BaseModel):
    niche_id: str
    characters: list[dict] # {index: int, name: str, prompt: str}
    video_type: str = "story"

@app.post("/scenes/generate-images-batch")
async def generate_images_batch(request: GenerateBatchSceneImagesRequest):
    """Generate multiple scene images in one browser session."""
    agent = None
    results = []
    
    try:
        from services.whisk_agent import WhiskAgent
        from services.cloud_storage import R2Storage
        import uuid
        import httpx
        import tempfile
        from pathlib import Path

        print(f"🎨 Starting Batch Generation for {len(request.scenes)} scenes...")

        # Determine Style Suffix
        channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
        style_suffix = channel.styleSuffix if (channel and channel.styleSuffix) else ""
        
        # Determine format
        is_shorts = request.video_type and "short" in request.video_type.lower()
        print(f"   📐 Batch Format: {'Shorts (9:16)' if is_shorts else 'Landscape (16:9)'}")

        # Download Character References (Once for all scenes)
        char_local_paths = []
        if request.character_images:
            print(f"📥 Downloading {len(request.character_images)} character references...")
            async with httpx.AsyncClient() as client:
                for char in request.character_images:
                    url = char.get("imageUrl")
                    if not url: continue
                    try:
                        resp = await client.get(url, follow_redirects=True)
                        resp.raise_for_status()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            tmp.write(resp.content)
                            char_local_paths.append(Path(tmp.name))
                    except Exception as e:
                        print(f"⚠️ Failed to download character ref {url}: {e}")

        # Initialize Agent (Single Session)
        agent = WhiskAgent(headless=False)
        storage = R2Storage()

        # Track if setup (login, upload, etc) has been done successfully
        setup_done = False

        for i, scene in enumerate(request.scenes):
            idx = scene.get("index")
            prompt = scene.get("prompt")
            # DEBUG: Log what we're receiving to diagnose empty prompts
            print(f"   > Generating Scene {idx+1} (Batch {i+1}/{len(request.scenes)})...")
            print(f"     DEBUG: Scene keys: {list(scene.keys())}")
            print(f"     DEBUG: Prompt value: '{prompt}' (type: {type(prompt).__name__}, len: {len(prompt) if prompt else 0})")
            
            # Retry loop for robust generation
            MAX_RETRIES = 3
            
            for attempt in range(MAX_RETRIES):
                try:
                    if attempt > 0:
                        print(f"     🔄 Retry Attempt {attempt+1}/{MAX_RETRIES} for Scene {idx+1}...")
                        import asyncio
                        await asyncio.sleep(2) # Wait a bit before retry

                    # Reuse agent for each scene. 
                    # Skip setup (refresh + uploads) if we have already done it once in this batch.
                    # BUT if we are retrying, maybe forcing setup (skip_setup=False) is safer?
                    # For now, let's trust the page state unless it crashes hard.
                    should_skip_setup = setup_done
                    
                    image_bytes = await agent.generate_image(
                        prompt=prompt,
                        is_shorts=is_shorts, # Pass correct ratio
                        style_suffix=style_suffix,
                        character_paths=char_local_paths,
                        skip_setup=should_skip_setup
                    )
                    
                    if image_bytes:
                        image_key = f"scenes/{request.niche_id}/{uuid.uuid4().hex[:8]}_scene_{idx}.png"
                        storage.upload_asset(image_bytes, image_key, content_type="image/png")
                        image_url = storage.get_url(image_key)
                        results.append({"index": idx, "imageUrl": image_url})
                        print(f"     ✅ Scene {idx+1} done: {image_url}")
                        
                        # Mark setup as done since we successfully generated an image (implies setup worked)
                        setup_done = True
                        break # Success, exit retry loop
                    
                    else:
                        print(f"     ⚠️ Scene {idx+1} returned no bytes (Attempt {attempt+1})")
                        if attempt == MAX_RETRIES - 1:
                            results.append({"index": idx, "error": "No image generated after retries"})
                        
                        # If failed, we might keep setup_done as True if we believe session is okay,
                        # or set to False to force refresh? 
                        # Let's keep it True to avoid re-uploading characters needlessly.
                        
                except Exception as e:
                    print(f"     ❌ Scene {idx+1} failed (Attempt {attempt+1}): {e}")
                    if attempt == MAX_RETRIES - 1:
                        results.append({"index": idx, "error": str(e)})
                    # Wait before next attempt
            
            # End of retry loop



        # --- THUMBNAIL GENERATION ---
        if request.thumbnail_prompt:
            print(f"🖼️ Transitioning to Thumbnail Generation for Batch. (setup_done={setup_done})")
            try:
                thumb_bytes = await agent.generate_image(
                    prompt=request.thumbnail_prompt,
                    is_shorts=is_shorts,
                    style_suffix=style_suffix,
                    character_paths=char_local_paths,
                    skip_setup=setup_done
                )
                if thumb_bytes:
                    thumb_key = f"thumbnails/{request.niche_id}/{uuid.uuid4().hex[:8]}_thumb.png"
                    storage.upload_asset(thumb_bytes, thumb_key, content_type="image/png")
                    thumb_url = storage.get_url(thumb_key)
                    results.append({"index": -1, "type": "thumbnail", "imageUrl": thumb_url})
                    print(f"✅ Batch Thumbnail done: {thumb_url}")
            except Exception as e:
                print(f"⚠️ Batch Thumbnail failed: {e}")

        return {"results": results}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {e}")
    finally:
        if agent:
            # Add a tiny delay before closing to ensure any pending network activity is settled
            import asyncio
            await asyncio.sleep(1)
            await agent.close()
        # Clean up character temp files
        for p in char_local_paths:
            if p.is_file():
                try: os.unlink(str(p))
                except: pass


@app.post("/characters/generate-images-stream")
async def generate_character_images_stream(request: GenerateCharacterBatchRequest):
    """Generate all master cast images in one chrome session and stream results."""
    from services.whisk_agent import WhiskAgent
    from services.cloud_storage import R2Storage
    import json
    import asyncio
    import uuid
    import httpx
    import tempfile
    from pathlib import Path

    async def generate_generator():
        agent = None
        try:
            print(f"🚀 [Streaming] Starting Character Batch Generation for {len(request.characters)} characters...")

            # Determine Style Suffix
            channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
            style_suffix = channel.styleSuffix if (channel and channel.styleSuffix) else ""
            
            # Determine format
            is_shorts = request.video_type and "short" in request.video_type.lower()

            # Initialize Agent
            agent = WhiskAgent(headless=False)
            storage = R2Storage()
            setup_done = False

            for i, char_req in enumerate(request.characters):
                idx = char_req.get("index") # Character index
                char_name = char_req.get("name", f"Character_{idx}")
                prompt = char_req.get("prompt")
                
                # Retry loop
                MAX_RETRIES = 3
                success = False
                
                for attempt in range(MAX_RETRIES):
                    try:
                        if attempt > 0:
                            await asyncio.sleep(2)

                        image_bytes = await agent.generate_image(
                            prompt=prompt,
                            is_shorts=is_shorts,
                            style_suffix=style_suffix,
                            skip_setup=setup_done
                        )
                        
                        if image_bytes:
                            # Use character-specific key
                            image_key = f"characters/{request.niche_id}/{char_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
                            storage.upload_asset(image_bytes, image_key, content_type="image/png")
                            image_url = storage.get_url(image_key)
                            
                            # Yield result
                            yield json.dumps({"index": idx, "imageUrl": image_url}) + "\n"
                            
                            setup_done = True
                            success = True
                            break
                    except Exception as e:
                        print(f"❌ Character {char_name} failed (Attempt {attempt+1}): {e}")

                if not success:
                    yield json.dumps({"index": idx, "error": "Failed after retries"}) + "\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"error": str(e)}) + "\n"
        finally:
            if agent:
                await asyncio.sleep(1)
                await agent.close()

    return StreamingResponse(generate_generator(), media_type="application/x-ndjson")


@app.post("/scenes/generate-images-stream")
async def generate_images_stream(request: GenerateBatchSceneImagesRequest):
    """Generate multiple scene images in one browser session and stream results."""
    from services.whisk_agent import WhiskAgent
    from services.cloud_storage import R2Storage
    import json
    import asyncio
    import uuid
    import httpx
    import tempfile
    from pathlib import Path

    async def generate_generator():
        agent = None
        char_local_paths = []
        try:
            print(f"🚀 [Streaming] Starting Batch Generation for {len(request.scenes)} scenes...")
            print(f"   🖼️ Thumbnail Prompt Status: {'PRESET' if request.thumbnail_prompt else 'EMPTY'}")

            # Determine Style Suffix
            channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
            style_suffix = channel.styleSuffix if (channel and channel.styleSuffix) else ""
            
            # Determine format
            is_shorts = request.video_type and "short" in request.video_type.lower()

            # Download Character References
            if request.character_images:
                async with httpx.AsyncClient() as client:
                    for char in request.character_images:
                        url = char.get("imageUrl")
                        if not url: continue
                        try:
                            resp = await client.get(url, follow_redirects=True)
                            resp.raise_for_status()
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                tmp.write(resp.content)
                                char_local_paths.append(Path(tmp.name))
                        except Exception as e:
                            print(f"⚠️ Failed to download character ref {url}: {e}")

            # Initialize Agent
            agent = WhiskAgent(headless=False)
            storage = R2Storage()
            setup_done = False

            for i, scene in enumerate(request.scenes):
                idx = scene.get("index")
                prompt = scene.get("prompt")
                print(f"[STREAM] Generating Scene {i+1}/{len(request.scenes)} (Index {idx})...")
                
                # Retry loop
                MAX_RETRIES = 3
                success = False
                
                for attempt in range(MAX_RETRIES):
                    try:
                        if attempt > 0:
                            await asyncio.sleep(2)

                        image_bytes = await agent.generate_image(
                            prompt=prompt,
                            is_shorts=is_shorts,
                            style_suffix=style_suffix,
                            character_paths=char_local_paths,
                            skip_setup=setup_done
                        )
                        
                        if image_bytes:
                            image_key = f"scenes/{request.niche_id}/{uuid.uuid4().hex[:8]}_scene_{idx}.png"
                            storage.upload_asset(image_bytes, image_key, content_type="image/png")
                            image_url = storage.get_url(image_key)
                            
                            # Yield result as individual JSON object per line
                            yield json.dumps({"index": idx, "imageUrl": image_url}) + "\n"
                            print(f"[SUCCESS] Scene {idx} generated: {image_url}")
                            
                            setup_done = True
                            success = True
                            break
                        else:
                            print(f"⚠️ Scene {idx} attempt {attempt+1} returned no bytes")
                    except Exception as e:
                        print(f"❌ Scene {idx+1} failed (Attempt {attempt+1}): {e}")

                if not success:
                    print(f"[ERROR] Scene {idx} failed after all retries")
                    yield json.dumps({"index": idx, "error": "Failed after retries"}) + "\n"

            # --- THUMBNAIL GENERATION ---
            if request.thumbnail_prompt:
                print(f"[STREAM] Transitioning to Thumbnail Generation. (setup_done={setup_done})")
                try:
                    # YouTube thumbnails are always 16:9 (1280x720)
                    thumb_bytes = await agent.generate_image(
                        prompt=request.thumbnail_prompt,
                        is_shorts=is_shorts,
                        style_suffix=style_suffix,
                        character_paths=char_local_paths,
                        skip_setup=setup_done
                    )
                    
                    if thumb_bytes:
                        thumb_key = f"thumbnails/{request.niche_id}/{uuid.uuid4().hex[:8]}_thumb.png"
                        storage.upload_asset(thumb_bytes, thumb_key, content_type="image/png")
                        thumb_url = storage.get_url(thumb_key)
                        
                        # Yield special thumbnail event
                        yield json.dumps({"type": "thumbnail", "imageUrl": thumb_url}) + "\n"
                        print(f"[SUCCESS] Thumbnail generated: {thumb_url}")
                    else:
                        print("⚠️ Thumbnail generation returned no bytes")
                        yield json.dumps({"type": "thumbnail", "error": "Failed to generate thumbnail"}) + "\n"
                        
                except Exception as e:
                    print(f"❌ Thumbnail generation failed: {e}")
                    import traceback
                    traceback.print_exc()
                    yield json.dumps({"type": "thumbnail", "error": str(e)}) + "\n"
            else:
                print("ℹ️ No thumbnail_prompt requested, skipping thumbnail phase.")

        except Exception as e:
            print(f"❌ Global streaming error: {e}")
            import traceback
            traceback.print_exc()
            yield json.dumps({"error": str(e)}) + "\n"
        finally:
            print("🛑 [Streaming] Generation stream ending. Cleaning up agent...")
            if agent:
                await asyncio.sleep(1)
                await agent.close()
            for p in char_local_paths:
                if p.is_file():
                    try: os.unlink(str(p))
                    except: pass


    return StreamingResponse(generate_generator(), media_type="application/x-ndjson")


class VerifyVideoRequest(BaseModel):
    video_url: str

@app.post("/videos/verify")
async def verify_video(request: VerifyVideoRequest):
    """Check if a video file on R2 exists and is valid (size > 10KB)."""
    try:
        from services.cloud_storage import R2Storage
        storage = R2Storage()
        
        # Parse key from URL
        if "videos/" not in request.video_url:
            return {"valid": False, "error": "Invalid video URL format"}
            
        key_part = request.video_url.split("/videos/", 1)[1].split("?")[0]
        full_key = f"videos/{key_part}"
        
        # Check existence and size using head_object
        try:
            response = storage.client.head_object(Bucket=storage.bucket, Key=full_key)
            size = response.get('ContentLength', 0)
            
            if size < 10000: # 10KB
                return {"valid": False, "error": f"Video too small ({size} bytes)"}
                
            return {"valid": True, "size": size}
        except Exception:
            return {"valid": False, "error": "File not found on R2"}
            
    except Exception as e:
        return {"valid": False, "error": str(e)}


# Request model for video generation
class GenerateVideoRequest(BaseModel):
    scene_index: int
    image_url: str
    prompt: str | dict | None = "" # Add default to prevent 422
    niche_id: str
    dialogue: str | dict | None = "" # Add default to prevent 422
    text_to_audio_prompt: str | None = None # New field for scene audio
    camera_angle: str | dict | None = None
    is_shorts: bool = False
    sound_effect: str | list | None = None
    emotion: str | None = None


def smart_coerce(val: any) -> str:
    """Extract actual text from potentially structured objects (dicts/lists)."""
    if val is None: return ""
    if isinstance(val, str): return val
    if isinstance(val, dict):
        # Common keys for dialogue/text
        for key in ["text", "content", "dialogue", "prompt", "value"]:
            if key in val and val[key]:
                return str(val[key])
        # Fallback: just use first value if possible
        if val.values():
            return str(list(val.values())[0])
    return str(val)


@app.post("/scenes/generate-video")
async def generate_video(request: GenerateVideoRequest):
    """Generate video from image using Grok Playwright automation."""
    try:
        from services.grok_agent import GrokAnimator
        from services.cloud_storage import R2Storage
        
        # Coerce any non-string fields to strings carefully
        request.prompt = smart_coerce(request.prompt)
        request.dialogue = smart_coerce(request.dialogue)
        request.camera_angle = smart_coerce(request.camera_angle)
        
        if isinstance(request.sound_effect, list):
            request.sound_effect = ", ".join([str(s) for s in request.sound_effect])
        else:
            request.sound_effect = str(request.sound_effect) if request.sound_effect is not None else ""
        import httpx
        import tempfile
        import uuid
        from pathlib import Path
        
        print(f"🎥 Generating video for scene {request.scene_index}")
        print(f"   Image: {request.image_url[:60]}...")
        print(f"   Motion: {request.prompt[:80]}...")
        
        # Download the scene image to a temp file
        async with httpx.AsyncClient() as client:
            target_url = request.image_url
            # Fix placehold.co URLs to ensure PNG (Grok detects SVG as invalid)
            if "placehold.co" in target_url and ".png" not in target_url:
                target_url = target_url.replace("?", ".png?") if "?" in target_url else f"{target_url}.png"
                print(f"🔄 Adjusted placeholder URL to force PNG: {target_url}")

            response = await client.get(target_url, follow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            print(f"📥 Downloaded image type: {content_type}")
            
            if "image" not in content_type:
                print("⚠️ Warning: Downloaded content might not be an image!")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(response.content)
                image_path = Path(tmp.name)
        
        try:
            # Determine aspect ratio
            aspect_ratio = "9:16" if request.is_shorts else "16:9"
            print(f"   📐 Aspect Ratio: {aspect_ratio} (shorts={request.is_shorts})")
            
            from services.grok_agent import GrokAnimator, PromptBuilder, ModerationError
            animator = GrokAnimator()
            from services.script_generator import ScriptGenerator
            gen = ScriptGenerator()
            
            async def generate_and_verify(prompt: str) -> Path:
                """Inner helper to generate and immediately verify integrity."""
                path = await animator.animate(
                    image_path=image_path,
                    motion_prompt=prompt,
                    style_suffix="Cinematic, Pixar-style 3D animation",
                    duration=10,
                    camera_angle=request.camera_angle or "Medium Shot",
                    aspect_ratio=aspect_ratio,
                    dialogue=request.dialogue,
                    sound_effect=request.sound_effect,
                    emotion=request.emotion or "neutrally"
                )
                # Strict Integrity check
                file_size = os.path.getsize(path)
                is_html = False
                if file_size > 0:
                    with open(path, "rb") as f:
                        head = f.read(200)
                        if b"<!DOCTYPE html>" in head or b"<html" in head:
                            is_html = True
                            
                if is_html or file_size < 100000:
                    status_reason = "Grok Moderation (HTML Error Page)" if is_html else f"Corrupt/Too Small ({file_size}b)"
                    print(f"⚠️ {status_reason} detected. Grok refused the prompt.")
                    if path.exists(): os.unlink(path)
                    raise ModerationError(f"Generated video is content-moderated or corrupt HTML ({file_size} bytes).")
                return path

            try:
                # ATTEMPT 1
                video_path = await generate_and_verify(request.prompt)
                sent_prompt = request.prompt
            except ModerationError as e:
                # AUTO-HEAL
                print(f"🛡️ Safety System: Moderation detected. Attempting to sanitize and rewrite prompt...")
                new_prompt = await gen.rewrite_moderated_prompt(request.prompt)
                
                if new_prompt != request.prompt:
                    print(f"♻️ Retrying with 'Safe Mode' prompt: {new_prompt}")
                    # ATTEMPT 2 (Final Retry)
                    video_path = await generate_and_verify(new_prompt)
                    sent_prompt = new_prompt
                else:
                    print("❌ Safety System: Rewrite failed or returned identical prompt. Giving up.")
                    raise e # Give up if rewrite failed
            except Exception as e:
                print(f"❌ Critical error in animation flow: {e}")
                raise e
            
            # Recalculate formatted prompt based on what was ACTUALLY sent (if it was rewritten)
            # or just use the PromptBuilder to get the final "Director's Script" version of whatever we sent
            formatted_prompt = PromptBuilder.build(
                character_pose="",
                camera_angle=request.camera_angle or "",
                style_suffix="",
                motion_description=sent_prompt if isinstance(sent_prompt, str) else "",
                dialogue=request.dialogue,
                character_name="Character",
                emotion=request.emotion or "neutrally",
                grok_video_prompt=sent_prompt if isinstance(sent_prompt, dict) else None,
                sfx=request.sound_effect.split(", ") if isinstance(request.sound_effect, str) else request.sound_effect
            )

            # --- High Quality Stage: 4K Upscale ---
            # NOTE: Disabled per user request
            # try:
            #     from services.video_editor import FFmpegVideoEditor
            #     editor = FFmpegVideoEditor()
            #     
            #     # Determine target resolution for 4K
            #     # Long format: 3840x2160, Shorts: 2160x3840
            #     target_res = (2160, 3840) if request.is_shorts else (3840, 2160)
            #     
            #     print(f"🚀 Starting 4K Upscale for scene {request.scene_index} ({target_res[0]}x{target_res[1]})...")
            #     upscaled_path = editor.upscale_video(video_path, target_resolution=target_res)
            #     
            #     # Replace original path with upscaled path if successful
            #     if upscaled_path.exists() and upscaled_path != video_path:
            #         # Original video_path will be cleaned up in finally block if it was different
            #         video_path = upscaled_path

            # --- Scene Audio Generation (New) ---
            if request.text_to_audio_prompt:
                print(f"🔊 generating audio for scene {request.scene_index} -> '{request.text_to_audio_prompt[:30]}...'")
                from services.audio_engine import AudioEngine
                from services.video_editor import FFmpegVideoEditor
                
                audio_engine = AudioEngine()
                video_editor = FFmpegVideoEditor()
                
                # Check if prompt is meaningful dialogue or just SFX
                # Heuristic: If prompt has no words outside brackets [], it's likely SFX/Atmosphere
                # If it has words, use TTS.
                text = request.text_to_audio_prompt
                import re
                # Remove content in brackets to see if there's spoken text
                clean_text = re.sub(r'\[.*?\]', '', text).strip()
                
                if clean_text:
                    # Case A: Dialogue exists -> Use TTS
                    print(f"   🗣️ Dialogue detected: '{clean_text}'")
                    # Use a default voice or one from request (not yet in request, could add later)
                    # For now, default to standard narrative voice
                    tts_path = await audio_engine.generate_narration(clean_text, provider="edge-tts")
                    
                    # Merge this audio into the video
                    # 1. Start with original video audio (or silence)
                    # 2. Add TTS audio
                    # Since we want to supporting "original audio" + "new audio", we should mix.
                    # BUT `replace_audio_track` REPLACES it. 
                    # For this feature, we likely want to REPLACE the video audio with the TTS, 
                    # because the "original audio" from Grok/Hunyuan is usually silence or garbage.
                    # If user wants "original audio" they wouldn't provide a text_to_audio_prompt for dialogue.
                    
                    # If prompt was ONLY brackets (e.g. [breathing]), clean_text is empty -> we skip TTS.
                    
                    print(f"   video_path: {video_path}")
                    print(f"   tts_path: {tts_path}")
                    
                    # Create mixed video
                    mixed_video = video_path.parent / f"{video_path.stem}_with_audio.mp4"
                    
                    # If video has no audio stream, this adds it.
                    # If video has audio, we might want to keep it? 
                    # User said: "if no [prompt] then use original audio".
                    # Implication: If prompt EXISTS, we use generated audio.
                    
                    # We use ffmpeg to replace/add audio
                    final_scene_path = video_editor.replace_audio_track(video_path, tts_path, mixed_video)
                    video_path = final_scene_path
                    print(f"   ✅ Audio added to scene {request.scene_index}")

                else:
                    print(f"   🎵 SFX-only prompt detected: '{text}'. Keeping original audio (no TTS generated).")
                    # In future: Call SFX generation model here.
            else:
                 print(f"   🔇 No audio prompt for scene {request.scene_index}. Keeping original audio.")

            #         print(f"✨ 4K Upscale complete: {video_path.name}")
            # except Exception as e:
            #     print(f"⚠️ 4K Upscale failed (falling back to original): {e}")

            # --- Success Path: Upload ---
            storage = R2Storage()
            video_key = f"videos/{request.niche_id}/scene_{request.scene_index}_{uuid.uuid4().hex[:8]}.mp4"
            
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            
            storage.upload_asset(video_bytes, video_key, content_type="video/mp4")
            video_url = storage.get_url(video_key)
            
            print(f"✅ Video generated and uploaded: {video_url}")
            return {"videoUrl": video_url, "formattedPrompt": formatted_prompt}
            
        finally:
            # Clean up temp image and local video
            if 'image_path' in locals() and image_path.exists():
                try:
                    image_path.unlink()
                except Exception:
                    pass
                    
            if 'video_path' in locals() and video_path.exists():
                try:
                    os.unlink(video_path)
                    print(f"🧹 Deleted local video: {video_path}")
                except Exception as e:
                    print(f"⚠️ Failed to delete local video: {e}")
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error generating video: {e}")
        
        # Check for specific ModerationError from grok_agent
        from services.grok_agent import ModerationError
        if isinstance(e, HTTPException): # If it's already an HTTPException, re-raise it
            raise e
        elif isinstance(e, ModerationError):
            raise HTTPException(status_code=403, detail=str(e))
            
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# SIMPLE VIDEO STITCH (Bypass Inngest)
# ============================================

class StitchVideosRequest(BaseModel):
    video_urls: list[str]
    niche_id: str
    title: str = "Stitched Video"
    niche_type: str = "general"
    music: Optional[str] = None  # Frontend sends this field
    music_mood: Optional[str] = None  # Legacy/alternative field
    is_shorts: bool = False # Explicit aspect ratio control
    script: Optional[str] = None # Full script for AI context
    auto_upload: bool = False # 1-Click Automation: Upload to YouTube
    thumbnail_url: Optional[str] = None # Thumbnail to set if auto_upload is True
    video_id: Optional[str] = None # Database ID for the video job (to allow easy repair)
    youtube_upload: Optional[dict] = None
    final_assembly: Optional[dict] = None
    audio_config: Optional[dict] = None # { mute_source_audio: bool, provider: str, voice_id: str, voice_sample_key: str }

@app.post("/videos/stitch")
async def stitch_videos(request: StitchVideosRequest):
    """
    Stitch existing scene videos into a final video.
    
    This endpoint bypasses the full Inngest pipeline and simply:
    1. Downloads all video URLs
    2. Stitches them with FFmpeg
    3. Uploads final video to R2
    4. Returns the final video URL
    """
    import httpx
    import tempfile
    import uuid
    from pathlib import Path
    from services.video_editor import FFmpegVideoEditor
    from services.cloud_storage import R2Storage
    
    # Filter out empty or None URLs
    video_urls = [url for url in request.video_urls if url and url.strip()]
    
    if not video_urls:
        raise HTTPException(status_code=400, detail="No valid video URLs provided")
    
    print(f"🎬 Stitching {len(video_urls)} videos...")
    
    local_clips = []
    valid_clips = [] # Store clips that passed validation
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # 1. Download videos directly from R2 (bypassing URL expiration)
        storage_downloader = R2Storage()
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            for i, url in enumerate(video_urls):
                print(f"📥 Downloading video {i+1}/{len(video_urls)}...")
                try:
                    local_path = temp_dir / f"clip_{i:03d}.mp4"
                    
                    # Try to parse key from URL to use direct R2 download (more robust)
                    # Expected URL format: .../videos/niche/filename.mp4...
                    # We look for 'videos/' in the URL path
                    if "videos/" in url:
                        # Extract key starting from 'videos/'
                        # e.g. https://.../video-clips/videos/pets/scene.mp4 -> videos/pets/scene.mp4
                        key_part = url.split("/videos/", 1)[1]
                        # Clean off query params if any
                        key_part = key_part.split("?")[0]
                        full_key = f"videos/{key_part}"
                        
                        print(f"   🔑 Parsed R2 key: {full_key}")
                        storage_downloader.download(full_key, local_path)
                    else:
                        # Fallback to HTTP download if key parsing fails
                        print(f"   ⚠️ Could not parse R2 key, falling back to HTTP download")
                        resp = await client.get(url, follow_redirects=True)
                        resp.raise_for_status()
                        local_path.write_bytes(resp.content)
                        
                    local_clips.append(local_path)
                    print(f"   ✅ Downloaded: {local_path.name}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to download video {i+1}: {e}. Skipping.")
                    continue
        
        if not local_clips:
            raise HTTPException(status_code=400, detail="No videos could be downloaded")

        # 1.5 Validate Clips (Check for corruption)
        print(f"🕵️ Validating {len(local_clips)} clips...")
        import ffmpeg as ffprobe_lib
        corrupt_indices = []
        corrupt_urls = []
        
        # Support custom FFmpeg paths
        ffmpeg_cmd = os.getenv("FFMPEG_PATH", "ffmpeg")
        ffprobe_cmd = os.getenv("FFPROBE_PATH", "ffprobe")
        
        for i, clip_path in enumerate(local_clips):
            is_valid = False
            head = b""
            size = -1
            try:
                size = clip_path.stat().st_size
                with open(clip_path, "rb") as f:
                    head = f.read(200)
                
                # 1. HTML HEAD CHECK (Critical)
                if b"<!DOCTYPE html>" in head or b"<html" in head:
                     print(f"   ❌ Clip {i} {clip_path.name} is HTML content (Corrupt)!")
                # 2. SIZE CHECK
                elif size < 50000: # 50KB is very small for an mp4
                     print(f"   ❌ Clip {i} {clip_path.name} is too small ({size} bytes)")
                else:
                    # 3. FFPROBE CHECK
                    try:
                        ffprobe_lib.probe(str(clip_path), cmd=ffprobe_cmd)
                        is_valid = True
                    except Exception as probe_err:
                        print(f"      🔍 Probe fallack check: {probe_err}")
                        # If ffprobe fails with "file not found", it's likely a system PATH issue
                        if "winerror 2" in str(probe_err).lower():
                             raise RuntimeError(f"FFprobe not found at '{ffprobe_cmd}'. Please install FFmpeg and add to PATH or set FFPROBE_PATH in .env")
                        raise probe_err

            except Exception as e:
                print(f"   ❌ Clip {i} {clip_path.name} validation failed: {e}")
                print(f"      Size: {size} bytes. Head: {head[:50]}...")
            
            if not is_valid:
                corrupt_indices.append(i)
                corrupt_urls.append(video_urls[i])
                print(f"   ⚠️ Skipping corrupt clip {i}")
            else:
                valid_clips.append(clip_path)

        if not valid_clips:
            print(f"❌ No valid video clips remains after validation! Aborting stitch.")
            # Cleanup
            for p in local_clips:
                try: p.unlink() 
                except: pass
                
            raise HTTPException(status_code=422, detail="All provided video clips are corrupt or invalid.")

        # Use only valid clips for stitching
        final_clips_to_stitch = valid_clips
        print(f"✅ Proceeding to stitch {len(final_clips_to_stitch)} valid clips (Skipped {len(corrupt_indices)} corrupt clips).")

        # 2. Stitch with FFmpeg
        # Fetch actual Channel Config to determine format accurately
        target_res = (1920, 1080) # Default to Landscape
        channel_config = None
        
        try:
             # We can't access 'db' directly easily since it's global in main.py but we are inside a function.
             # Actually, 'db' is available in global scope.
             channel = await db.channel.find_unique(where={"nicheId": request.niche_id})
             if channel:
                 channel_config = channel # Assign for later use
                 print(f"🔧 System Config: Name='{channel.name}', Niche='{channel.nicheId}', Style='{channel.styleSuffix}'")
                 
                 # Logic: Use request.is_shorts (Frontend) > Channel Config > Default
                 is_shorts_channel = (
                     "shorts" in channel.nicheId.lower() or 
                     "shorts" in (channel.styleSuffix or "").lower()
                 )
                 
                 if request.is_shorts or is_shorts_channel:
                     target_res = (1080, 1920)
                     print(f"📐 Aspect Ratio: 9:16 Vertical ({'Explicit' if request.is_shorts else 'Channel Config'})")
                 else:
                     target_res = (1920, 1080) 
                     print(f"📐 Aspect Ratio: 16:9 Landscape (Standard)")
             else:
                 # Fallback if channel not found but request specifies shorts
                 if request.is_shorts:
                     target_res = (1080, 1920)
                     print(f"📐 Aspect Ratio: 9:16 Vertical (Explicit)")
                 else:
                     print(f"⚠️ Channel config not found for {request.niche_id}, falling back to default Landscape")
                 # Fallback logic
                 if "shorts" in request.niche_type.lower() or "vertical" in request.niche_type.lower():
                      target_res = (1080, 1920)
                      print(f"📐 Aspect Ratio Fallback: 9:16 Vertical")
                 else:
                      print(f"📐 Aspect Ratio Fallback: 16:9 Landscape")

        except Exception as e:
            print(f"⚠️ Error fetching channel config: {e}. Defaulting to Landscape.")
        
        print(f"🔧 Stitching {len(local_clips)} clips with 0.4s black fade transitions (Target: {target_res})...")
        
        print(f"🔧 Stitching {len(local_clips)} clips with 0.4s black fade transitions (Target: {target_res})...")
        editor = FFmpegVideoEditor(output_dir=temp_dir)
        stitched_path = temp_dir / "stitched_no_music.mp4"
        
        # We need to update VideoEditor to support target_resolution
        audio_config = request.audio_config or {}
        mute_source = audio_config.get("mute_source_audio", False)
        remove_speakers = audio_config.get("remove_speakers", False) # New flag from frontend
        
        # If "Deep Remove Vocals" is selected, we MUST NOT mute the source during stitching
        # because we need the audio to process it.
        stitch_mute = mute_source
        if remove_speakers:
            print("🔊 Smart Vocal Removal requested: Preserving source audio for processing...")
            stitch_mute = False
        
        stitched_path = editor.stitch_clips_with_fade(
            final_clips_to_stitch, 
            stitched_path, 
            fade_duration=0.3,
            target_resolution=target_res,
            mute_audio=stitch_mute
        )
        print(f"   ✅ Stitched video created: {stitched_path}")
        
        # --- SMART VOCAL REMOVAL (Demucs) ---
        if remove_speakers and not mute_source:
             print(f"🧬 Performing Smart Vocal Removal (Demucs)...")
             try:
                 from services.audio_engine import AudioEngine
                 engine = AudioEngine()
                 
                 # 1. Extract audio from stitched video
                 full_audio = engine.extract_audio_from_clip(stitched_path)
                 
                 # 2. Separate (remove vocals)
                 bg_audio = engine.remove_vocals(full_audio)
                 
                 # 3. Replace video audio with the instrumental version
                 clean_video = temp_dir / "stitched_clean.mp4"
                 stitched_path = editor.replace_audio_track(stitched_path, bg_audio, clean_video)
                 print(f"   ✅ Replaced audio with instrumental track.")
                 
             except Exception as e:
                 print(f"   ⚠️ Smart Vocal Removal failed: {e}. Falling back to original audio.")

        current_video_path = stitched_path
        
        # --- AUDIO GENERATION (TTS / Cloning) ---
        audio_provider = audio_config.get("provider")
        voice_id = audio_config.get("voice_id")
        voice_sample_key = audio_config.get("voice_sample_key")
        
        fresh_audio_paths = []
        if audio_provider:
            print(f"🎙️ Generating fresh Voiceover using {audio_provider}...")
            from services.audio_engine import AudioEngine
            engine = AudioEngine()
            
            # Download reference audio if XTTS
            ref_audio_path = None
            if audio_provider == "xtts" and voice_sample_key:
                 from services.cloud_storage import R2Storage
                 storage_downloader = R2Storage()
                 ref_audio_path = temp_dir / "ref_voice_sample.wav"
                 try:
                     print(f"   📥 Downloading voice sample: {voice_sample_key}")
                     storage_downloader.download(voice_sample_key, ref_audio_path)
                 except Exception as e:
                     print(f"   ⚠️ Failed to download voice sample for XTTS: {e}")
            
            # We need the script text for each scene. 
            # Ideally the frontend sends the *text* to be spoken for each clip, but here we only have URLs.
            # However, the frontend sends request.script (full text) usually.
            # Or we can iterate if we had scene-level data. But StitchVideosRequest is "Simple".
            # If we don't have per-scene text, we might just generate one long audio track from request.script?
            # Or assume the frontend passed a way to map?
            # Wait, `StitchVideosRequest` has `script: Optional[str]`. This is usually the full text.
            # If we want per-scene sync, we need per-scene text.
            # BUT, the user usually only changes this on the "Final" tab where they see the full script?
            # Actually, `Step5Final` has access to `scenes`.
            # If we want to support this properly, `StitchVideosRequest` needs `scene_texts` list or we use `script` as one block.
            # Using `script` as one block is risky for sync.
            # Let's check `StitchVideosRequest` again. It has `script`.
            # For now, if we use TTS here, we'll generate one audio track from `request.script` and let it run over the video?
            # Or we just support it if we can map it.
            # BETTER: The frontend should send `scenes` with text.
            # BUT `StitchVideosRequest` is designed to be simple.
            # Let's stick to generating from `request.script` (full text) as a single narration track for now.
            # This handles the "Voiceover for the whole video" use case.
            
            # if request.script:
            #      try:
            #         full_audio_path = await engine.generate_narration(
            #             text=request.script,
            #             voice_id=voice_id or "en-US-AriaNeural",
            #             provider=audio_provider,
            #             reference_audio=ref_audio_path,
            #             output_path=temp_dir / "full_narration.mp3"
            #         )
            #         fresh_audio_paths.append(full_audio_path)
            #         print(f"   ✅ Generated full narration: {full_audio_path.name}")
            #      except Exception as e:
            #         print(f"   ❌ TTS Generation failed: {e}")

        # --- FINAL ASSEMBLY (Color Grading) ---
        if request.final_assembly and request.final_assembly.get("color_grading"):
            print(f"🎨 Applying Color Grading...")
            try:
                grading_config = request.final_assembly["color_grading"]
                graded_path = temp_dir / "graded_video.mp4"
                editor.apply_color_grading(current_video_path, grading_config, graded_path)
                current_video_path = graded_path
                print(f"   ✅ Color grading applied.")
            except Exception as e:
                print(f"   ⚠️ Color grading failed: {e}")

        # 3. Get video duration and generate background music
        print(f"🎵 Generating ambient background music...")
        import ffmpeg as ffprobe_lib
        
        # Support custom FFmpeg paths
        ffprobe_cmd = os.getenv("FFPROBE_PATH", "ffprobe")
        
        probe = ffprobe_lib.probe(str(current_video_path), cmd=ffprobe_cmd)
        video_duration = float(probe['streams'][0]['duration'])
        
        from services.music_generator import generate_background_music
        from services.mood_analyzer import MoodAnalyzer
        
        # Determine music mood using LLM (smart matching)
        # Check for Manual Music Override from Channel Config
        music_path = None
        # Use either 'music' (frontend) or 'music_mood' (legacy) field
        music_selection = request.music or request.music_mood or "auto"
        music_mood = "auto" # Default
        
        # 0. Check if Music is Disabled
        if music_selection.lower() == "none":
            print("🚫 Music explicitly disabled by user.")
            music_path = None
            music_mood = "none"

        # 1. Check for Explicit User Selection (Render UI)
        elif music_selection.lower() != "auto":
            print(f"🎵 Manual selection detected: '{music_selection}'")
            music_mood = music_selection
            try:
                music_path = generate_background_music(video_duration, mood=music_selection)
            except Exception as e:
                print(f"   ⚠️ Failed to generate manual music: {e}. Falling back to config/auto.")
                music_path = None

        # 2. Auto-Analyze Mood (High Priority for 'auto')
        if not music_path and music_mood == "auto":
            print(f"🧠 Analyzing video context for music selection...")
            analyzer = MoodAnalyzer()
            # Use script if available, otherwise title
            context_text = request.script if request.script else request.title
            music_mood = analyzer.analyze_mood(title=request.title, niche=request.niche_type, description=context_text)
            print(f"   📎 Context: '{request.title}' -> Music mood: {music_mood}")
            
            # If niche is 'pets', force 'happy' instead of 'cute' which maps to Carefree (Toon style)
            if "pet" in request.niche_type.lower() and music_mood == "cute":
                 music_mood = "happy" # Wallpaper is less annoying than Carefree
            
            try:
                music_path = generate_background_music(video_duration, mood=music_mood)
            except Exception as e:
                print(f"   ❌ AI Music generation failed: {e}")
                music_path = None

        # 3. Check for Channel Config Override (Fallback if AI failed or skipped)
        if not music_path and channel_config and channel_config.bgMusic:
             print(f"🎵 Found manual background music override for channel (Using as fallback).")
             try:
                 storage_downloader = R2Storage()
                 music_path = temp_dir / "manual_bgm.mp3"
                 storage_downloader.download(channel_config.bgMusic, music_path)
                 print(f"   ✅ Downloaded manual BGM: {music_path.name}")
                 music_mood = "channel_config"
             except Exception as e:
                 print(f"   ⚠️ Failed to download manual BGM: {e}")
        
        if music_path:
            music_size = music_path.stat().st_size / 1024
            print(f"   ✅ Generated {video_duration:.1f}s of '{music_mood}' ambient music ({music_size:.1f} KB)")
        else:
            print(f"   🚫 No background music generated/selected.")
        
        # 4. Mix background music with video (low volume: 30%)
        final_path = temp_dir / "final_with_music.mp4"
        
        # Determine audio mix strategy
        # A. Fresh TTS + BGM (Documentary Style)
        if fresh_audio_paths:
            print("🎛️ Mixing Fresh TTS Audio + BGM...")
            mixed_audio = temp_dir / "final_audio_mix.mp3"
            
            if music_path:
                # Mix narration with BGM (ducking handled by mix_audio usually?)
                # Editor.mix_audio handles list of narration + bgm
                mixed_audio = editor.mix_audio(fresh_audio_paths, music_path, mixed_audio)
            else:
                # Just narration
                 import shutil
                 shutil.copy(fresh_audio_paths[0], mixed_audio)
            
            # Combine with video (which might be silent if mute_source was True)
            # Finalize expects separate audio path
            # We can use editor.finalize logic here or just a direct ffmpeg merge
            # Let's use editor.finalize if we can import it? 
            # finalize takes (video, audio, subtitle, output)
            
            # Since we are in main, editor is instantiated.
            # But duplicate logic is messy. editor.finalize matches lengths.
            # Let's use editor.finalize. We need to create dummy subtitle path if none?
            # Or wait, finalize handles optional subtitles.
            
            final_path = editor.finalize(current_video_path, mixed_audio, None, final_path)
            
        # B. Original Audio + BGM (Story Style)
        elif music_path:
            print(f"🔊 Mixing background music at 30% volume...")
            if mute_source:
                 # If source muted and no fresh audio, it's just BGM
                 # add_background_music might preserve original audio track even if empty?
                 # If we used `mute_audio=True` in stitch, the video track has `anullsrc` text?
                 # Actually `stitch_clips_with_fade` adds `anullsrc`.
                 # So `add_background_music` will mix BGM with that silence.
                 editor.add_background_music(current_video_path, music_path, final_path, music_volume=0.30)
            else:
                 editor.add_background_music(current_video_path, music_path, final_path, music_volume=0.30)
            print(f"   ✅ Background music mixed")
            
        # C. No New Audio
        else:
            print(f"   ℹ️ No background music/TTS to mix. Using stitched video.")
            import shutil
            shutil.copy(current_video_path, final_path)
        
        # 5. Upload to R2
        storage = R2Storage()
        safe_title = request.title.replace(" ", "_")[:30]
        final_key = f"videos/{request.niche_id}/{safe_title}_{uuid.uuid4().hex[:8]}.mp4"
        
        with open(final_path, "rb") as f:
            video_bytes = f.read()
        
        storage.upload_asset(video_bytes, final_key, content_type="video/mp4")
        final_url = storage.get_url(final_key)
        
        print(f"✅ Final video uploaded: {final_url}")

        # --- AUTO-UPLOAD TO YOUTUBE (1-Click Automation) ---
        youtube_info = None
        if request.auto_upload:
            print(f"🚀 1-Click Automation: Triggering YouTube Upload...")
            try:
                from services.youtube_uploader import YouTubeUploader
                uploader = YouTubeUploader(niche_id=request.niche_id)
                
                # Use request metadata with fallback
                yt_meta = request.youtube_upload.get("metadata", {}) if request.youtube_upload else {}
                
                final_title = yt_meta.get("title") or request.title
                final_desc = yt_meta.get("description") or request.script or f"Narrative for {request.title}"
                final_tags = yt_meta.get("tags") or ["AI Video", "Shorts", "Automation"]
                privacy_status = yt_meta.get("privacyStatus", "unlisted")
                publish_at = yt_meta.get("publishAt")
                made_for_kids = yt_meta.get("madeForKids", False)
                playlist_name = yt_meta.get("playlistTitle")
                
                # Trigger upload logic (blocking for simplicity in stitch endpoint)
                result = uploader.upload_with_copyright_check(
                    video_path=final_path,
                    title=final_title,
                    description=final_desc,
                    tags=final_tags,
                    privacy_status=privacy_status,
                    publish_at=publish_at,
                    made_for_kids=made_for_kids,
                    playlist_name=playlist_name,
                    wait_minutes=1 # Very short wait for 1-click feedback
                )
                
                # Set Thumbnail if available
                if request.thumbnail_url and result.video_id:
                    # Download thumb to temp file
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp_thumb = await client.get(request.thumbnail_url)
                        if resp_thumb.status_code == 200:
                            thumb_path = temp_dir / "automation_thumbnail.jpg"
                            thumb_path.write_bytes(resp_thumb.content)
                            uploader.set_thumbnail(result.video_id, thumb_path)
                
                youtube_info = {
                    "video_id": result.video_id,
                    "status": result.status,
                    "message": result.message
                }
                print(f"✅ 1-Click Upload Success: {result.video_id}")
            except Exception as e:
                print(f"⚠️ 1-Click Upload Failed: {e}")
                youtube_info = {"error": str(e)}
        # Upload separate music track for debugging
        music_url = None
        if music_path:
            try:
                music_key = f"music/{request.niche_id}/{safe_title}_bgm_{uuid.uuid4().hex[:8]}.wav"
                with open(music_path, "rb") as f:
                    music_bytes = f.read()
                storage.upload_asset(music_bytes, music_key, content_type="audio/wav")
                music_url = storage.get_url(music_key)
                print(f"✅ Music track uploaded: {music_url}")
            except Exception as e:
                print(f"⚠️ Music track upload failed: {e}")

        return {
            "status": "success",
            "final_video_url": final_url,
            "final_video_key": final_key,
            "music_url": music_url,
            "clips_stitched": len(final_clips_to_stitch),
            "skipped_clips": len(corrupt_indices),
            "youtube_upload": youtube_info
        }
        
    finally:
        # Cleanup temp files
        for clip in local_clips:
            try:
                clip.unlink()
            except:
                pass
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


@app.post("/scripts/submit")
async def submit_script(script: VideoScript):
    """Submit a video script for processing."""
    # Validate niche exists in DB
    channel = await db.channel.find_unique(where={"nicheId": script.niche_id})
    if not channel:
        raise HTTPException(status_code=400, detail="Invalid niche_id")
    
    # Create Video record in DB
    video = await db.video.create(
        data={
            "channelId": channel.id,
            "title": script.title,
            "status": "QUEUED",
            "script": script.model_dump_json(),
        }
    )
    
    # Trigger Inngest workflow
    try:
        from services.inngest_client import inngest_client
        from inngest import Event
        
        # Build clean JSON-serializable channel config
        channel_data = {
            "nicheId": channel.nicheId,
            "name": channel.name,
            "voiceId": channel.voiceId or "en-US-AriaNeural",
            "styleSuffix": channel.styleSuffix or "",
            "anchorImage": channel.anchorImage,
            "bgMusic": channel.bgMusic,
            "defaultTags": list(channel.defaultTags) if channel.defaultTags else [],
        }
        
        # Fully serialize script to plain dict (avoid nested Pydantic models)
        import json
        script_data = json.loads(script.model_dump_json())
        
        # Create proper Inngest Event object (required for SDK v0.5.x)
        event = Event(
            name="video/generation.started",
            data={
                "video_id": video.id,
                "script": script_data,
                "channel_config": channel_data
            }
        )
        
        await inngest_client.send(event)
        
        # Update status to PROCESSING
        await db.video.update(
            where={"id": video.id},
            data={"status": "PROCESSING"}
        )
        
    except Exception as e:
        # If Inngest fails, log but don't fail the request
        print(f"❌ CRITICAL ERROR: Failed to trigger Inngest! Is the Inngest Dev Server running on port 8288?")
        print(f"   Error: {e}")
        import logging
        logging.error(f"Failed to trigger Inngest: {e}")
    
    return {
        "job_id": video.id,
        "status": "queued",
        "total_scenes": len(script.scenes),
        "message": f"Video '{script.title}' queued for processing",
    }


# --- Job Status ---

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a video generation job."""
    video = await db.video.find_unique(where={"id": job_id})
    if not video:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Sign the final video URL if available
    final_video_url = None
    # NOTE: Schema uses 'assets' but code/frontend expects 'metadata'
    metadata = video.assets 
    
    if metadata and metadata.get("final_video_key"):
        from services.cloud_storage import R2Storage
        storage = R2Storage()
        final_video_url = storage.get_url(metadata.get("final_video_key"))

    return {
        "job_id": video.id,
        "title": video.title,
        "status": video.status,
        "created_at": video.createdAt.isoformat() if video.createdAt else None,
        "updated_at": video.updatedAt.isoformat() if video.updatedAt else None,
        "metadata": metadata, # Alias assets to metadata for frontend
        "final_video_url": final_video_url
    }


@app.get("/jobs")
async def list_jobs(limit: int = 20, status: Optional[str] = None):
    """List recent video generation jobs."""
    where_clause = {}
    if status:
        where_clause["status"] = status
    
    videos = await db.video.find_many(
        where=where_clause if where_clause else None,
        order={"createdAt": "desc"},
        take=limit
    )
    
    return {
        "jobs": [
            {
                "job_id": v.id,
                "title": v.title,
                "status": v.status,
                "created_at": v.createdAt.isoformat() if v.createdAt else None,
            }
            for v in videos
        ]
    }


# --- Inngest Webhook ---

@app.api_route("/inngest", methods=["GET", "POST", "PUT"])
async def inngest_webhook(request):
    """
    Inngest webhook handler for background jobs.
    
    This endpoint is called by the Inngest dev server to:
    - GET: Fetch registered functions
    - POST: Execute function steps
    - PUT: Handle function completions
    """
    from inngest.fast_api import serve
    from services.video_workflow import video_generation_workflow, rate_limit_recovery, video_upload_workflow
    from services.inngest_client import inngest_client
    
    # Serve Inngest functions
    handler = serve(
        inngest_client,
        [video_generation_workflow, rate_limit_recovery, video_upload_workflow]
    )
    
    return await handler(request)

@app.post("/videos/{video_id}/upload")
async def trigger_video_upload(video_id: str):
    """Manually trigger YouTube upload for a reviewed video."""
    video = await db.video.find_unique(where={"id": video_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    if video.status != "REVIEW_PENDING":
        raise HTTPException(status_code=400, detail=f"Video status is {video.status}, must be REVIEW_PENDING")
        
    # Get metadata from the video record
    import json
    metadata = video.assets or {}
    script_data = json.loads(video.script)
    
    # Trigger upload workflow
    from services.inngest_client import inngest_client
    
    # Get channel config from DB helper
    channel_data = await get_channel_config(script_data['niche_id'])
    
    await inngest_client.send({
        "name": "video/upload.requested",
        "data": {
            "video_id": video.id,
            "final_video_key": metadata.get("final_video_key"),
            "thumbnail_key": metadata.get("thumbnail_key"),
            "script": script_data,
            "channel_config": channel_data,
            "seo_result": metadata.get("seo")
        }
    })
    
    # Update status to UPLOADING
    await db.video.update(
        where={"id": video.id},
        data={"status": "UPLOADING"}
    )
    
    return {"status": "upload_queued", "message": "Upload workflow started"}


@app.post("/videos/{video_id}/repair")
async def repair_video_job(video_id: str):
    """
    Manually trigger the 'Self-Healing' repair flow for a video job.
    This will:
    1. Scan R2 for existing clips.
    2. Deep check them for corruption (HTML).
    3. Re-animate ONLY the missing or corrupt scenes.
    """
    video = await db.video.find_unique(where={"id": video_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    import json
    script_data = json.loads(video.script)
    
    # Trigger generation workflow again with same data
    # The new Deep Integrity Check in video_workflow.py will handle the selective repair
    from services.inngest_client import inngest_client
    from inngest import Event
    
    # Get channel config from DB helper
    channel_data = await get_channel_config(script_data['niche_id'])
    
    event = Event(
        name="video/generation.started",
        data={
            "video_id": video.id,
            "script": script_data,
            "channel_config": channel_data,
            "resume_from_checkpoint": {
                "completed_steps": ["scene_images"], # Assume images are fine, start at animation
                "partial_results": {
                    "scene_images": [f"scenes/{script_data['niche_id']}/scene_{i:03d}.png" for i in range(len(script_data['scenes']))]
                }
            }
        }
    )
    
    await inngest_client.send(event)
    
    # Update status to PROCESSING
    await db.video.update(
        where={"id": video.id},
        data={"status": "REPAIRING"}
    )
    
    return {"status": "repair_started", "message": f"Repair flow started for {video_id}. Checking integrity..."}


class YouTubeUploadRequest(BaseModel):
    video_url: str
    niche_id: str
    title: str
    description: str
    tags: Optional[list[str]] = []
    thumbnail_url: Optional[str] = None
    generate_metadata: bool = False # If true, use AI to generate title/desc/tags
    script_context: Optional[str] = None # Required if generate_metadata is True


class ClonePreviewRequest(BaseModel):
    text: str
    provider: str = "xtts" # xtts, elevenlabs
    voice_id: Optional[str] = None
    voice_sample_url: Optional[str] = None

@app.post("/audio/clone-preview")
async def clone_audio_preview(request: ClonePreviewRequest):
    """Generate a short preview of the cloned voice."""
    import tempfile
    from pathlib import Path
    from services.audio_engine import AudioEngine
    from services.cloud_storage import R2Storage
    import httpx
    import uuid

    engine = AudioEngine()
    storage = R2Storage()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ref_path = None
        
        # Download sample if needed
        if request.provider == "xtts" and request.voice_sample_url:
            ref_path = tmp_path / "sample.wav"
            async with httpx.AsyncClient() as client:
                resp = await client.get(request.voice_sample_url)
                if resp.status_code == 200:
                    with open(ref_path, "wb") as f:
                        f.write(resp.content)
                        
        output_path = tmp_path / f"preview_{uuid.uuid4().hex}.mp3"
        try:
            await engine.generate_narration(
                text=request.text,
                voice_id=request.voice_id or "en-US-AriaNeural",
                provider=request.provider,
                reference_audio=ref_path,
                output_path=output_path
            )
            
            # Upload
            key = f"previews/audio/{output_path.name}"
            with open(output_path, "rb") as f:
                storage.upload_asset(f.read(), key, "audio/mpeg")
                
            return {"url": storage.get_url(key)}
            
        except Exception as e:
            print(f"Preview generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            

@app.post("/upload/youtube")
async def upload_to_youtube(request: YouTubeUploadRequest):
    """
    Manually upload a video URL to YouTube for a specific channel.
    Downloads the video from R2 to a temp file, then uploads via YouTubeUploader.
    """
    import tempfile
    import httpx
    from pathlib import Path
    from services.youtube_uploader import YouTubeUploader
    from services.script_generator import ScriptGenerator

    # 1. Generate Metadata if requested
    final_title = request.title
    final_desc = request.description
    final_tags = request.tags or ["AI Video", "Shorts", "Automation"]

    if request.generate_metadata and request.script_context:
        try:
            generator = ScriptGenerator()
            metadata = await generator.generate_viral_metadata(request.script_context, niche=request.niche_type)
            final_title = metadata.get("title", final_title)
            final_desc = metadata.get("description", final_desc)
            final_tags = metadata.get("tags", final_tags)
            print(f"✨ AI Generated Metadata: {final_title}")
        except Exception as e:
            print(f"⚠️ Metadata generation failed: {e}")

    # 2. Download video to temp file
    video_path = None
    thumb_path = None
    
    try:
        print(f"📥 Downloading video for YouTube upload: {request.video_url}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(request.video_url, follow_redirects=True)
            resp.raise_for_status()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(resp.content)
                video_path = Path(tmp.name)
        
            print(f"✅ Downloaded to {video_path} ({video_path.stat().st_size} bytes)")
            
            # Download Thumbnail if provided
            if request.thumbnail_url:
                try:
                    print(f"🖼️ Downloading thumbnail: {request.thumbnail_url}")
                    resp_thumb = await client.get(request.thumbnail_url, follow_redirects=True)
                    if resp_thumb.status_code == 200:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_thumb:
                            tmp_thumb.write(resp_thumb.content)
                            thumb_path = Path(tmp_thumb.name)
                            print(f"✅ Downloaded thumbnail to {thumb_path}")
                except Exception as e:
                    print(f"⚠️ Failed to download thumbnail: {e}")
        
        # 3. Upload to YouTube
        uploader = YouTubeUploader(niche_id=request.niche_id)
        
        result = uploader.upload_with_copyright_check(
            video_path=video_path,
            title=final_title,
            description=final_desc,
            tags=final_tags,
            wait_minutes=2, # Short wait for manual trigger
            promote_to="unlisted" # Safety first
        )

        # 4. Set Thumbnail
        if thumb_path and result.video_id:
            uploader.set_thumbnail(result.video_id, thumb_path)
        
        return {
            "status": "success",
            "video_id": result.video_id,
            "youtube_status": result.status,
            "message": result.message,
            "metadata_used": {
                "title": final_title,
                "description": final_desc[:50] + "...",
                "tags": final_tags
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"YouTube Upload Failed: {str(e)}")
        
    finally:
        # Cleanup
        if 'video_path' in locals() and video_path.exists():
            try:
                video_path.unlink()
                print(f"🧹 Cleaned up temp video: {video_path}")
            except:
                pass
        if 'thumb_path' in locals() and thumb_path and thumb_path.exists():
            try:
                thumb_path.unlink()
            except:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

