# Multi-Niche AI Video Factory - Implementation Plan

Build a scalable, topic-agnostic AI video production system with full post-production and YouTube distribution capabilities. Switch between niches (pets, history, sci-fi) by updating configuration without changing core code.

## User Review Required

> [!IMPORTANT]
> **Credentials Needed**: Before execution, you'll need credentials from 5 platforms. See the **Credentials Setup Guide** section below for detailed instructions.

> [!TIP]
> **Free Tier Strategy**: All services use FREE tiers except Hugging Face Pro ($9/month). Neon Postgres, Cloudflare R2, and Inngest all offer generous free quotas.

> [!WARNING]
> **Grok Automation**: The Playwright agent will automate your browser. Ensure you:
> 1. Have a Grok account with valid session
> 2. Understand rate limits (~10 generations per 2 hours, not 100/day)
> 3. Use **non-headless mode** or stealth settings to avoid bot detection
> 4. Accept responsibility for automated interactions

> [!CAUTION]
> **YouTube Uploads**: Videos are uploaded as 'Unlisted' by default. 
> - **CRITICAL**: Toggle the **"Altered Content" AI Disclosure** flag for synthetic videos (YouTube 2025/2026 policy requirement to avoid demonetization)
> - Review before making public to avoid policy violations

---

## Credentials Setup Guide

### 1. Google Cloud Console (YouTube Data API v3) — FREE

> [!NOTE]
> You do **not** use a simple API Key for uploads. You must use **OAuth 2.0** to act on behalf of your channel.

| Credential | Description |
|------------|-------------|
| `client_secrets.json` | Downloaded from Google Cloud Console. Contains your Client ID and Client Secret. |
| **YouTube Scope** | Your app must be authorized for `https://www.googleapis.com/auth/youtube.upload` |
| **OAuth Refresh Token** | Stored after first manual login. Enables 24/7 uploads without re-authentication. |

**Setup Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **YouTube Data API v3**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Select "Desktop app" as application type
6. Download the JSON file and rename to `client_secrets.json`
7. Place in `./secrets/client_secrets.json`

---

### 2. Neon Postgres Database — FREE TIER

| Credential | Format |
|------------|--------|
| `DATABASE_URL` | `postgresql://[user]:[password]@[hostname]/neondb?sslmode=require` |
| **Pooled Connection** (optional) | Use `-pooler` endpoint for high-traffic scenarios |

**Free Tier Limits:**
- 0.5 GB storage
- 1 project
- Shared compute

**Setup Steps:**
1. Go to [Neon Console](https://console.neon.tech/)
2. Create a new project
3. Copy the connection string from the dashboard

> [!WARNING]
> **Free Tier Management Strategy:**
> - Only store **job metadata** (not video files) — typically ~1KB per job
> - At 0.5GB limit, you can store ~500,000 job records
> - Implement **90-day data retention**: Auto-delete completed jobs older than 90 days
> - Archive important job data to JSON files in R2 before deletion
> - Run cleanup cron: `DELETE FROM jobs WHERE status = 'completed' AND created_at < NOW() - INTERVAL '90 days'`

---

### 3. Cloudflare R2 Storage — FREE TIER

Because you're using the `boto3` library, you need S3-style credentials:

| Credential | Description |
|------------|-------------|
| `R2_ACCESS_KEY_ID` | Generated in R2 → Manage API Tokens |
| `R2_SECRET_ACCESS_KEY` | Long secret key (only shown once during creation!) |
| `R2_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `R2_BUCKET` | Your bucket name (e.g., `youtube-automation-clips`) |

**Free Tier Limits:**
- 10 GB storage
- 1 million Class A operations/month
- 10 million Class B operations/month
- No egress fees!

**Setup Steps:**
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → R2
2. Create a new bucket
3. Go to **Manage R2 API Tokens** → Create API Token
4. Save both keys immediately (secret only shown once)
5. Get your Account ID from the R2 overview page

> [!CAUTION]
> **Free Tier Management Strategy — AUTO-CLEANUP AT 9GB:**
> - Monitor bucket size before each upload
> - When storage reaches **9GB**, trigger automatic cleanup:
>   1. Delete **raw clips** (individual 10s segments) — these are transient
>   2. Keep only **final rendered videos** (the YouTube-ready files)
>   3. Delete final videos older than **30 days** (already uploaded to YouTube)
> - Estimated usage per video: ~50MB final + ~200MB raw clips = ~250MB
> - At 9GB limit with cleanup: Can process ~36 videos before needing cleanup
>
> **Cleanup Priority Order:**
> 1. Raw clips (highest priority to delete — regenerable)
> 2. Final videos already uploaded to YouTube (30+ days old)
> 3. Failed/incomplete job artifacts

---

### 4. Hugging Face Pro — $9/MONTH (PAID)

| Credential | Description |
|------------|-------------|
| `HF_TOKEN` | User Access Token with "Write" permissions from PRO account |

**Why PRO?**
- Access to PuLID-FLUX-v1 and other gated models
- Higher rate limits for Inference API
- ZeroGPU access for Spaces

**Setup Steps:**
1. Subscribe to [Hugging Face Pro](https://huggingface.co/pricing)
2. Go to **Settings** → **Access Tokens**
3. Create new token with **Write** permission
4. Copy the `hf_xxxx` token

---

### 5. Inngest (Workflow Management) — FREE TIER

| Credential | Description |
|------------|-------------|
| `INNGEST_EVENT_KEY` | Used by FastAPI to trigger video jobs |
| `INNGEST_SIGNING_KEY` | Secures communication between Inngest and your server |

**Free Tier Limits:**
- 5,000 function runs/month
- Unlimited functions
- 7-day history

**Setup Steps:**
1. Go to [Inngest Dashboard](https://app.inngest.com/)
2. Create a new app
3. Copy both keys from the **Manage** → **Keys** section

> [!IMPORTANT]
> **Free Tier Management Strategy — RUN BUDGETING:**
> - Each full video pipeline = **9 step runs** (image gen → animate → upload → stitch → audio → subtitles → combine → R2 → YouTube)
> - 5,000 runs ÷ 9 steps = **~555 videos/month** on free tier
> - That's **~18 videos/day** — more than enough for most channels!
> - If you hit limits: Batch multiple scenes into single steps to reduce run count
> - Monitor usage at [Inngest Dashboard](https://app.inngest.com/) → Usage

---

### 6. Grok (Browser Automation) — FREE

| Resource | Limit |
|----------|-------|
| Daily video generations | Limited (rate-limited after ~10-20 videos) |
| Session persistence | Via Playwright browser profile |

> [!WARNING]
> **Rate Limit Management Strategy:**
> - Grok enforces daily limits on video generation
> - When "Daily Limit Reached" detected → Agent sleeps **2 hours**, then retries
> - Best practice: Run video generation during **off-peak hours** (night/early morning)
> - If consistently hitting limits: Spread generation across multiple days
> - The Inngest retry system handles this automatically with exponential backoff

---

## Consolidated Environment Configuration

#### [NEW] [.env.example](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/.env.example)

```env
# ============================================
# MULTI-NICHE AI VIDEO FACTORY - ENVIRONMENT
# ============================================

# Gemini 2.0 Flash (Scripting) - FREE
GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxx

# Hugging Face PRO (Flux.1-dev + PuLID) - $9/month
HF_TOKEN=hf_xxxxxxxxxxxxxxxxx

# Cloudflare R2 (S3-Compatible Storage) - FREE
R2_ACCESS_KEY_ID=xxxxxxxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxx
R2_ENDPOINT=https://[account_id].r2.cloudflarestorage.com
R2_BUCKET=youtube-automation

# Neon Postgres Database - FREE
DATABASE_URL=postgresql://user:pass@ep-cool-darkness.neon.tech/neondb?sslmode=require

# Inngest (Workflow Management) - FREE
INNGEST_EVENT_KEY=xxxxxxxxxxxxxxxxx
INNGEST_SIGNING_KEY=xxxxxxxxxxxxxxxxx

# YouTube (OAuth2 - requires client_secrets.json file)
GOOGLE_CLIENT_SECRETS_PATH=./secrets/client_secrets.json
YT_CHANNEL_ID=UCxxxxxxxxxxxxxxxxx

# Grok Browser Automation
# WARNING: Set to 'false' for reliability - headless mode triggers bot detection!
GROK_HEADLESS=false
```

---

## Tech Stack Overview

| Category | Technology | Purpose | Tier |
|----------|------------|---------|------|
| **Scripting** | Gemini 2.0 Flash | Structured JSON scene generation | FREE |
| **Backend** | FastAPI + Python 3.12 | API orchestration and job management | — |
| **Image Gen** | Flux.1-dev + PuLID (HF PRO) | Consistent character face generation | **PAID** |
| **Animation** | Grok Imagine (Playwright) | AI video generation from images | FREE |
| **Video Editing** | **ffmpeg-python** / fmov | 3.7x faster than MoviePy | — |
| **Audio** | Edge-TTS + Sidechain | Narration with auto-ducking | FREE |
| **Subtitles** | Pysrt + FFmpeg | Hardcoded captions for retention | — |
| **Thumbnails** | PIL + AI Generation | Click-optimized thumbnails | — |
| **Storage** | Cloudflare R2 (boto3) | Cloud clip warehouse | FREE |
| **Database** | Neon Postgres | Job tracking and metadata | FREE |
| **YouTube** | google-api-python-client | Uploads with AI disclosure flag | FREE |
| **Jobs** | Inngest | Background workflow orchestration | FREE |
| **Frontend** | Next.js 15 | Dashboard and monitoring | — |

> [!CAUTION]
> **MoviePy Performance Warning**: MoviePy can take **2+ hours** to build a 5-minute video due to frame-by-frame Python processing. Use **ffmpeg-python** or **MovieLite** (3.7x faster via JIT compilation) for production workloads.

> [!IMPORTANT]
> **Hugging Face Pro Quota**: Your $9/month plan provides ~**25 minutes of H200 GPU time per day**. Flux.1 is heavy — for 50+ scene videos, optimize prompts or split across multiple days.

---

## Video Type: Story vs Documentary

> [!IMPORTANT]
> **Audio Source Selection**: The system supports two video types that determine how audio is handled. This is selectable in the UI when generating a script.

| Mode | Audio Source | Use Case |
|------|--------------|----------|
| 🎭 **Story** (default) | Grok generates dialogue audio | Characters talking to each other (e.g., "cat meets tiger") |
| 📚 **Documentary** | Edge-TTS voiceover narration | Narrator explaining content (e.g., "Top 10 Roman Emperors") |

### Story Mode Workflow
1. Generate scene images (PuLID/Flux)
2. Animate with Grok (Grok generates dialogue audio in the video)
3. **Skip voiceover generation** — clips already have audio
4. Stitch clips together (preserve Grok's audio)
5. Optionally add background music at low volume (15%)
6. Upload to YouTube

### Documentary Mode Workflow
1. Generate scene images (PuLID/Flux)
2. Animate with Grok (video may be silent or have ambient audio)
3. **Generate voiceover with Edge-TTS** (narrator reads script)
4. Stitch clips together
5. Mix voiceover with background music (auto-ducking)
6. Burn subtitles
7. Upload to YouTube

### Implementation Files

| File | Changes |
|------|---------|
| [script-editor.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/components/script-editor.tsx) | Video Type selector radio buttons in UI |
| [main.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/api/main.py) | `video_type` field in `VideoScript` and `GenerateScriptRequest` models |
| [video_workflow.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/video_workflow.py) | Conditional voiceover generation based on `video_type` |
| [video_editor.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/video_editor.py) | `add_background_music()` method for story mode |

### UI Component
```tsx
{/* Video Type Selector */}
<div className="space-y-2">
  <label className="text-sm font-medium">Video Type</label>
  <div className="flex gap-4">
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        name="videoType"
        value="story"
        checked={videoType === "story"}
        onChange={() => setVideoType("story")}
      />
      <div>
        <span className="font-medium">🎭 Story</span>
        <p className="text-xs text-muted-foreground">Characters speak with dialogue (Grok generates audio)</p>
      </div>
    </label>
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        name="videoType"
        value="documentary"
        checked={videoType === "documentary"}
        onChange={() => setVideoType("documentary")}
      />
      <div>
        <span className="font-medium">📚 Documentary</span>
        <p className="text-xs text-muted-foreground">Narrator voiceover (Edge-TTS audio added)</p>
      </div>
    </label>
  </div>
</div>
```

### API Model
```python
class VideoScript(BaseModel):
    niche_id: str
    title: str
    description: str
    scenes: list[Scene]
    video_type: str = "story"  # "story" (Grok audio) or "documentary" (voiceover needed)
```

### Workflow Conditional Logic
```python
# Step 3: Generate voiceover audio (ONLY for documentary videos)
video_type = script.get("video_type", "story")

if video_type == "documentary":
    audio_files = await ctx.step.run(
        "generate-voiceover",
        lambda: generate_voiceover(script, channel_config)
    )
else:
    # Story mode: no separate voiceover needed, Grok generates dialogue
    audio_files = []
    logger.info("📹 Story mode: Using Grok's built-in audio")
```

---

## Proposed Changes

### Next.js Dashboard with shadcn/ui (`apps/web/`)

> [!TIP]
> **Modern React UI**: Built with Next.js 14, shadcn/ui components, and TailwindCSS for a professional, responsive dashboard with human-in-the-loop controls.

#### [NEW] Project Setup
```bash
# Initialize Next.js with shadcn/ui
npx -y create-next-app@latest apps/web --typescript --tailwind --eslint --app --src-dir
cd apps/web
npx -y shadcn@latest init
npx -y shadcn@latest add button card tabs select slider progress textarea badge separator
```

#### [NEW] [layout.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/app/layout.tsx)
```tsx
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <div className="flex h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
```

#### [NEW] [sidebar.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/components/sidebar.tsx)
```tsx
"use client";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export function Sidebar() {
  return (
    <aside className="w-72 border-r bg-card p-4 flex flex-col gap-4">
      <h1 className="text-xl font-bold">🎬 AI Video Factory</h1>
      
      <div className="space-y-3">
        <label className="text-sm font-medium">Video Format</label>
        <Select defaultValue="long-vertical">
          <SelectTrigger>
            <SelectValue placeholder="Select format" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="short">Short (9:16) - TikTok/Reels</SelectItem>
            <SelectItem value="long-vertical">Long Vertical (9:16)</SelectItem>
            <SelectItem value="standard">Standard (16:9)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-3">
        <label className="text-sm font-medium">Niche/Channel</label>
        <Select defaultValue="history">
          <SelectTrigger>
            <SelectValue placeholder="Select niche" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pets">🐕 Pets</SelectItem>
            <SelectItem value="history">📜 History</SelectItem>
            <SelectItem value="scifi">🚀 Sci-Fi</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Separator />
      
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Session Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">GPU Time</span>
            <Badge variant="secondary">~23 min</Badge>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">Grok Gens</span>
            <Badge variant="outline">7/10</Badge>
          </div>
        </CardContent>
      </Card>
    </aside>
  );
}
```

#### [NEW] [page.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/app/page.tsx)
```tsx
"use client";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScriptEditor } from "@/components/script-editor";
import { AssetGallery } from "@/components/asset-gallery";
import { RenderPanel } from "@/components/render-panel";

export default function Dashboard() {
  return (
    <Tabs defaultValue="script" className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="script">📝 Script Editor</TabsTrigger>
        <TabsTrigger value="assets">🖼️ Asset Approval</TabsTrigger>
        <TabsTrigger value="render">🎬 Render & Export</TabsTrigger>
      </TabsList>

      <TabsContent value="script">
        <ScriptEditor />
      </TabsContent>

      <TabsContent value="assets">
        <AssetGallery />
      </TabsContent>

      <TabsContent value="render">
        <RenderPanel />
      </TabsContent>
    </Tabs>
  );
}
```

#### [NEW] [script-editor.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/components/script-editor.tsx)
```tsx
"use client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";

export function ScriptEditor() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Generate Script</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input placeholder="e.g., 'Top 10 Roman Emperors'" />
          <Button className="w-full">🤖 Generate with Gemini 2.0 Flash</Button>
        </CardContent>
      </Card>

      {/* Scene Editor - Rendered for each scene */}
      <Card>
        <CardHeader>
          <CardTitle>Scene 1</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Narration</label>
            <Textarea placeholder="Voiceover text..." rows={4} />
            <label className="text-sm font-medium">Duration: 10s</label>
            <Slider defaultValue={[10]} max={20} min={5} step={1} />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Character Pose</label>
            <Textarea placeholder="Character pose prompt..." rows={2} />
            <label className="text-sm font-medium">Background</label>
            <Textarea placeholder="Background description..." rows={2} />
          </div>
        </CardContent>
      </Card>

      <Button className="w-full" size="lg">✅ Approve Script & Generate Images</Button>
    </div>
  );
}
```

#### [NEW] [asset-gallery.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/components/asset-gallery.tsx)
```tsx
"use client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Image from "next/image";

export function AssetGallery() {
  const scenes = Array(8).fill(null); // Placeholder for generated images

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {scenes.map((_, i) => (
          <Card key={i} className="overflow-hidden">
            <div className="aspect-video bg-muted flex items-center justify-center">
              <span className="text-muted-foreground">Scene {i + 1}</span>
            </div>
            <CardContent className="p-2">
              <Button variant="outline" size="sm" className="w-full">
                🔄 Regenerate
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <Button className="w-full" size="lg">✅ Approve All & Start Animation</Button>
    </div>
  );
}
```

#### [NEW] [render-panel.tsx](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/web/src/components/render-panel.tsx)
```tsx
"use client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function RenderPanel() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Render Settings</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Checkbox id="ken-burns" defaultChecked />
              <label htmlFor="ken-burns">Enable Ken Burns Effect</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="sidechain" defaultChecked />
              <label htmlFor="sidechain">Enable Sidechain Compression</label>
            </div>
          </div>
          <div className="space-y-4">
            <Select defaultValue="1080p">
              <SelectTrigger>
                <SelectValue placeholder="Quality" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="720p">720p</SelectItem>
                <SelectItem value="1080p">1080p</SelectItem>
                <SelectItem value="4k">4K</SelectItem>
              </SelectContent>
            </Select>
            <Select defaultValue="yellow">
              <SelectTrigger>
                <SelectValue placeholder="Subtitle Style" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="yellow">Yellow + Black Stroke</SelectItem>
                <SelectItem value="white">White + Shadow</SelectItem>
                <SelectItem value="none">None</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Render Progress</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Progress value={0} />
          <p className="text-sm text-muted-foreground">Ready to start render pipeline</p>
        </CardContent>
      </Card>

      <Button className="w-full" size="lg">🚀 Start Full Render Pipeline</Button>
    </div>
  );
}
```

#### Video Type Resolution Mapping
| Format | Resolution | Aspect | Use Case |
|--------|------------|--------|----------|
| Short (9:16) | 1080x1920 | Vertical | TikTok, Reels, Shorts |
| Long Vertical (9:16) | 1080x1920 | Vertical | Mobile-first YouTube |
| Standard (16:9) | 1920x1080 | Landscape | Desktop YouTube |

---

### Project Foundation

#### [NEW] [turbo.json](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/turbo.json)
Monorepo configuration for Turborepo. Defines build, dev, and lint pipelines.

#### [NEW] [docker-compose.yml](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/docker-compose.yml)
Local development stack:
- **Inngest Dev Server**: Local workflow testing (no cloud needed for dev)
- **API Service**: FastAPI backend (hot-reload enabled)

> [!NOTE]
> For production, use **Neon Postgres** (cloud) instead of local PostgreSQL. This simplifies deployment and provides automatic backups.

---

### Scripting Engine (`packages/services/script_generator.py`)

#### [NEW] Gemini 2.0 Flash Integration

Use **Gemini 2.0 Flash** for structured JSON scene generation. This ensures machine-parseable output without human intervention.

```python
import google.generativeai as genai
from pydantic import BaseModel

class SceneOutput(BaseModel):
    voiceover_text: str
    character_pose_prompt: str
    background_description: str
    duration_in_seconds: int

class ScriptGenerator:
    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(
            "gemini-2.0-flash",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": list[SceneOutput]
            }
        )
    
    async def generate_script(self, topic: str, niche_config: NicheConfig) -> list[SceneOutput]:
        prompt = f"""
        Create a {niche_config.optimal_length_minutes}-minute video script about: {topic}
        
        For each scene, provide:
        - voiceover_text: The narration (2-3 sentences)
        - character_pose_prompt: Description for image generation
        - background_description: Scene setting
        - duration_in_seconds: How long this scene lasts (8-12 seconds)
        
        Style: {niche_config.style_suffix}
        Target audience: {niche_config.target_audience}
        
        IMPORTANT: First scene must be a strong hook (15-20 seconds engagement window)
        """
        response = await self.model.generate_content_async(prompt)
        return response.parsed
```

> [!TIP]
> **Structured Output**: Gemini 2.0 Flash's `response_schema` ensures every scene has exact fields needed for downstream processing. No regex parsing required.

---

### Configuration Layer (`packages/shared/`)

#### [NEW] [channels.json](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/shared/channels.json)
The "brain" of the system. Stores complete niche DNA:

```json
{
  "niches": {
    "mochi_pets": {
      "anchor_image": "assets/niche_pets/anchor.png",
      "voice_id": "en-US-AriaNeural",
      "style_suffix": "cute, warm lighting, cozy atmosphere",
      "bg_music": "./assets/audio/happy_ukulele.mp3",
      "transition_type": "crossfade",
      "yt_category_id": "15",
      "yt_channel_id": "UC_PETS_CHANNEL_ID",
      "tags": ["pets", "mochi", "cats", "funny"],
      "sfx": {
        "meow": "./assets/sfx/cat_meow.mp3"
      },
      "youtube_optimization": {
        "thumbnail_template": "assets/niche_pets/thumbnail_template.png",
        "title_patterns": [
          "{emoji} {hook} | Mochi the Cat",
          "You Won't Believe What {subject} Did!"
        ],
        "description_template": "assets/niche_pets/description.txt",
        "target_audience": {
          "age_range": "18-35",
          "interests": ["pets", "cats", "cute animals", "comedy"]
        },
        "optimal_length_minutes": 8,
        "hook_duration_seconds": 15
      }
    },
    "roman_history": {
      "anchor_image": "assets/niche_history/anchor.png",
      "voice_id": "en-US-GuyNeural",
      "style_suffix": "sepia tones, documentary style, cinematic",
      "bg_music": "./assets/audio/epic_orchestra.mp3",
      "transition_type": "fade",
      "yt_category_id": "27",
      "yt_channel_id": "UC_HISTORY_CHANNEL_ID",
      "tags": ["history", "rome", "documentary"],
      "sfx": {
        "sword": "./assets/sfx/sword_clash.mp3"
      },
      "youtube_optimization": {
        "thumbnail_template": "assets/niche_history/thumbnail_template.png",
        "title_patterns": [
          "The {adjective} History of {subject}",
          "Why {event} Changed Everything"
        ],
        "description_template": "assets/niche_history/description.txt",
        "target_audience": {
          "age_range": "25-55",
          "interests": ["history", "documentaries", "education"]
        },
        "optimal_length_minutes": 12,
        "hook_duration_seconds": 20
      }
    }
  }
}
```

> [!IMPORTANT]
> **YouTube Success Patterns** (from review):
> - **Thumbnail**: Must be click-worthy — use faces, contrast, minimal text
> - **Title**: Pattern-based hooks that create curiosity
> - **Intro/Hook**: First 15-20 seconds must engage or viewers leave
> - **Target Audience**: Know your demographics — age, gender, interests

#### [NEW] [config_schema.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/shared/config_schema.py)
Pydantic models for config validation:

```python
class NicheConfig(BaseModel):
    anchor_image: str
    voice_id: str
    style_suffix: str
    bg_music: str
    transition_type: Literal["crossfade", "fade", "none"]
    yt_category_id: str
    yt_channel_id: str
    tags: list[str]
    sfx: dict[str, str] = {}
```

---

### FastAPI Orchestrator (`apps/api/`)

#### [NEW] [pyproject.toml](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/api/pyproject.toml)
Python 3.12 project with full dependencies:
```toml
[project]
name = "youtube-automation-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # Core
    "fastapi>=0.115.0",
    "uvicorn[standard]",
    "pydantic>=2.0",
    "pydantic-settings",
    "httpx",
    
    # AI/ML
    "google-generativeai",  # Gemini 2.0 Flash
    "huggingface-hub",
    
    # Storage & DB
    "boto3",
    "asyncpg",
    
    # Browser Automation
    "playwright",
    "playwright-stealth",  # Anti-bot detection
    
    # Video Processing (FFmpeg-based, NOT MoviePy)
    "ffmpeg-python",  # 3.7x faster than MoviePy
    "fmov",           # Alternative fast renderer
    
    # Audio
    "edge-tts",
    "pydub",          # For sidechain compression
    
    # Subtitles & Images
    "pysrt",
    "Pillow",
    
    # YouTube
    "google-api-python-client",
    "google-auth-oauthlib",
    
    # Background Jobs
    "inngest",
]
```

#### [NEW] [main.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/api/main.py)
FastAPI application entry point with endpoints:
- `GET /health` - Health check
- `POST /scripts/submit` - Submit video script
- `GET /jobs/{job_id}` - Job status
- `POST /inngest` - Inngest webhook handler

#### [NEW] [models/script.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/api/models/script.py)
Extended Pydantic models:

```python
class SFXMarker(BaseModel):
    sfx_key: str
    timestamp: float  # seconds

class Scene(BaseModel):
    prompt: str
    narration: str
    duration: int = 10
    sfx_markers: list[SFXMarker] = []

class VideoScript(BaseModel):
    niche_id: str
    title: str
    description: str
    scenes: list[Scene]
```

#### [NEW] [Dockerfile](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/api/Dockerfile)
Production container with Python 3.12-slim, FFmpeg, and Playwright browsers.

---

### Identity Engine (`packages/services/`)

#### [NEW] [ai_identity.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/ai_identity.py)

**PuLIDGenerator Class**
```python
import os
import httpx
from pathlib import Path
import base64
import logging

logger = logging.getLogger(__name__)

class PuLIDGenerator:
    """Generate consistent character images using PuLID-FLUX-v1 via Hugging Face API."""
    
    API_URL = "https://api-inference.huggingface.co/models/InstantX/PuLID-FLUX-v1"
    
    def __init__(self):
        self.token = os.getenv("HF_TOKEN")
        if not self.token:
            raise ValueError("HF_TOKEN environment variable is required")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    async def generate(
        self,
        anchor_image_path: Path,
        prompt: str,
        style_suffix: str = ""
    ) -> bytes:
        """Generate image with consistent character identity."""
        # Combine prompt with niche style suffix
        full_prompt = f"{prompt}, {style_suffix}" if style_suffix else prompt
        
        # Load anchor image as base64
        anchor_b64 = base64.b64encode(anchor_image_path.read_bytes()).decode()
        
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "id_image": anchor_b64,
                "num_inference_steps": 20,
                "guidance_scale": 7.5,
            }
        }
        
        async with httpx.AsyncClient(timeout=120) as client:
            for attempt in range(3):
                try:
                    response = await client.post(
                        self.API_URL,
                        headers=self.headers,
                        json=payload
                    )
                    response.raise_for_status()
                    return response.content
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 503:  # Model loading
                        logger.info(f"Model loading, retrying in {2 ** attempt}s...")
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise
        
        raise RuntimeError("Failed to generate image after 3 attempts")
```

**Key Features:**
- Uses single `HF_TOKEN` environment variable
- Accepts anchor image path from channel config
- Applies style suffix to scene prompts
- Retry with exponential backoff (3 attempts)

#### [NEW] [quota_tracker.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/quota_tracker.py)

**ZeroGPU Quota Monitor (Hugging Face Pro Tier)**
```python
import httpx
import os
from datetime import datetime

class QuotaTracker:
    """
    Monitor ZeroGPU usage for Hugging Face Pro ($9/month).
    Prevents batch operations from crashing mid-video when quota runs out.
    """
    
    HF_API = "https://huggingface.co/api/quota"
    DAILY_LIMIT_SECONDS = 1500  # ~25 minutes of H200 GPU time
    
    def __init__(self):
        self.token = os.getenv("HF_TOKEN")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    async def get_remaining_seconds(self) -> int:
        """Fetch remaining ZeroGPU seconds for today."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.HF_API, headers=self.headers)
            data = resp.json()
            used = data.get("compute_seconds_used", 0)
            return max(0, self.DAILY_LIMIT_SECONDS - used)
    
    async def can_generate_batch(self, scene_count: int, avg_seconds_per_scene: int = 30) -> bool:
        """Check if quota is sufficient for a batch of scenes."""
        remaining = await self.get_remaining_seconds()
        required = scene_count * avg_seconds_per_scene
        return remaining >= required
    
    async def get_status_display(self) -> dict:
        """Return data for dashboard display."""
        remaining = await self.get_remaining_seconds()
        return {
            "remaining_seconds": remaining,
            "remaining_minutes": remaining // 60,
            "percent_used": int((1 - remaining / self.DAILY_LIMIT_SECONDS) * 100),
            "can_generate_50_scenes": remaining >= 1500,  # 50 * 30s
        }
```

> [!IMPORTANT]
> **Quota Warning**: Before starting a 50-scene video, check `can_generate_batch(50)`. If False, split across multiple days or optimize prompts to reduce GPU time.

---

### Animation Agent with Full Automation Resilience (`packages/services/`)

> [!WARNING]
> **5 Automation Loopholes Addressed**: This agent handles prompt syntax, URL navigation changes, duration detection, bot detection, and rate limit recovery.

#### [NEW] [grok_agent.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/grok_agent.py)

**Loophole #1: 5-Layer Prompt Formula**
```python
class PromptBuilder:
    """
    Combines motion and dialogue into Grok-optimized prompt.
    Format: [Scene] + [Camera] + [Style] + [Motion] + [Audio/Dialogue]
    """
    
    @staticmethod
    def build(scene: Scene, niche_config: NicheConfig) -> str:
        """
        Example output:
        "Medium shot of Boy A and Boy B near a dying fire. Pixar 3D style.
         The fire flickers weakly. Boy A says in a worried voice: 'The fire is dying.'"
        """
        layers = [
            f"{scene.camera_angle} of {scene.character_pose_prompt}",  # Scene + Camera
            f"{niche_config.style_suffix}.",                           # Style (e.g., "Pixar 3D style")
            f"{scene.motion_description}.",                            # Motion
        ]
        
        # Add dialogue if present
        if scene.dialogue:
            layers.append(f"{scene.character_name} says {scene.emotion}: '{scene.dialogue}'")
        
        return " ".join(layers)
```

**Loophole #2: URL Listener for New Post Navigation**
```python
class URLListener:
    """
    Grok (Jan 2026 update) navigates to a NEW post URL after successful generation.
    We must capture this new URL to find the download button.
    """
    
    @staticmethod
    async def wait_for_post_navigation(page: Page, timeout: int = 120000) -> str:
        """Wait for URL to change to a post page after clicking Generate."""
        original_url = page.url
        
        async def wait_for_new_url():
            while True:
                current_url = page.url
                # Grok post URLs contain /post/ or /status/
                if current_url != original_url and ("/post/" in current_url or "/status/" in current_url):
                    return current_url
                await asyncio.sleep(0.5)
        
        try:
            new_url = await asyncio.wait_for(wait_for_new_url(), timeout=timeout/1000)
            logger.info(f"✅ Navigated to new post: {new_url}")
            return new_url
        except asyncio.TimeoutError:
            raise TimeoutError("Video generation did not navigate to post URL")
```

**Loophole #3: Duration & Aspect Ratio Detection**
```python
class VideoSettings:
    """Detect and select duration/aspect ratio before generation."""
    
    DURATION_SELECTORS = {
        "6s": ["[data-duration='6']", "button:has-text('6s')", ".duration-6"],
        "10s": ["[data-duration='10']", "button:has-text('10s')", ".duration-10"],
    }
    
    ASPECT_SELECTORS = {
        "9:16": ["[data-aspect='9:16']", "button:has-text('9:16')", ".aspect-vertical"],
        "16:9": ["[data-aspect='16:9']", "button:has-text('16:9')", ".aspect-landscape"],
    }
    
    @classmethod
    async def configure(cls, page: Page, duration: str = "10s", aspect: str = "9:16"):
        """Set duration and aspect ratio before generating."""
        # Try to find and click duration selector
        for selector in cls.DURATION_SELECTORS.get(duration, []):
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.click()
                    logger.info(f"Set duration: {duration}")
                    break
            except Exception:
                continue
        
        # Try to find and click aspect selector
        for selector in cls.ASPECT_SELECTORS.get(aspect, []):
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.click()
                    logger.info(f"Set aspect ratio: {aspect}")
                    break
            except Exception:
                continue
    
    @staticmethod
    def verify_clip_duration(clip_path: Path, expected_duration: float) -> bool:
        """Use ffprobe to verify actual clip duration matches expected."""
        import ffmpeg
        probe = ffmpeg.probe(str(clip_path))
        actual = float(probe['streams'][0]['duration'])
        tolerance = 0.5  # 500ms tolerance
        
        if abs(actual - expected_duration) > tolerance:
            logger.warning(f"⚠️ Duration mismatch: expected {expected_duration}s, got {actual}s")
            return False
        return True
```

**Loophole #4: Stealth File Upload (Anti-Bot Detection)**
```python
import random

class StealthUploader:
    """
    Human-like file upload to avoid bot detection.
    Uses mouse jitter and randomized delays.
    """
    
    @staticmethod
    async def upload_with_jitter(page: Page, file_input_selector: str, file_path: Path):
        """Upload file with human-like behavior."""
        file_input = page.locator(file_input_selector)
        
        # Random delay before interaction (500-1500ms)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Move mouse near the upload area with jitter
        box = await file_input.bounding_box()
        if box:
            # Add random offset (human imprecision)
            target_x = box['x'] + box['width'] / 2 + random.randint(-10, 10)
            target_y = box['y'] + box['height'] / 2 + random.randint(-10, 10)
            
            # Move mouse in small steps (not instant teleport)
            await page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Use setInputFiles (doesn't trigger file picker dialog)
        await file_input.set_input_files(str(file_path))
        
        # Random delay after upload (human pause to verify)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        logger.info(f"✅ Uploaded file with stealth: {file_path.name}")
```

**Loophole #5: Inngest-Driven Rate Limit Recovery**
```python
from inngest import Inngest
from datetime import datetime, timedelta

inngest = Inngest(app_id="video-factory")

class RateLimitError(Exception):
    """Raised when Grok rate limit is hit."""
    pass

@inngest.create_function(
    fn_id="grok-generate-with-retry",
    retries=5,
)
async def generate_video_durable(ctx, step, *, scene_index: int, job_id: str):
    """
    Durable video generation with automatic rate limit recovery.
    Saves progress to database and resumes after 2-hour sleep.
    """
    
    # Step 1: Load job state
    job = await step.run("load-job", lambda: load_job_from_db(job_id))
    
    if scene_index < job.current_scene_index:
        # Already processed this scene, skip
        return {"status": "skipped", "scene": scene_index}
    
    # Step 2: Attempt generation
    try:
        result = await step.run("generate", lambda: _generate_single_clip(
            job.scenes[scene_index],
            job.niche_config
        ))
        
        # Step 3: Update progress in database
        await step.run("save-progress", lambda: update_job_progress(job_id, scene_index + 1))
        
        return {"status": "success", "clip_path": result}
        
    except RateLimitError:
        logger.warning(f"🚨 Rate limit hit at scene {scene_index}. Sleeping 2 hours...")
        
        # Save current progress
        await step.run("save-checkpoint", lambda: save_checkpoint(job_id, scene_index))
        
        # Sleep for 2 hours using Inngest's built-in sleep
        await step.sleep("rate-limit-cooldown", timedelta(hours=2))
        
        # Retry this scene after waking up
        raise  # Inngest will retry this function

async def _generate_single_clip(scene: Scene, config: NicheConfig) -> Path:
    """Core generation logic with all stealth features."""
    browser, pw = await get_browser_context()
    try:
        page = await browser.new_page()
        await stealth_async(page)
        await page.goto("https://grok.x.com/")
        
        # Check rate limit FIRST
        if await check_rate_limit(page):
            raise RateLimitError("Rate limit detected")
        
        # Configure video settings
        await VideoSettings.configure(page, duration="10s", aspect="9:16")
        
        # Build 5-layer prompt
        prompt = PromptBuilder.build(scene, config)
        
        # Stealth upload
        await StealthUploader.upload_with_jitter(page, "input[type=file]", scene.image_path)
        
        # Fill prompt
        await page.fill("textarea", prompt)
        await page.click("button[type=submit]")
        
        # Wait for URL navigation (new Grok behavior)
        new_url = await URLListener.wait_for_post_navigation(page)
        
        # Navigate and download
        await page.goto(new_url)
        async with page.expect_download(timeout=60000) as dl:
            await page.click("button:has-text('Download')")
        download = await dl.value
        
        output = Path(tempfile.mkdtemp()) / f"clip_{scene.index}.mp4"
        await download.save_as(output)
        
        # Verify duration
        VideoSettings.verify_clip_duration(output, expected_duration=10.0)
        
        return output
    finally:
        await browser.close()
        await pw.stop()
```

**Rate-Limit Detection**
```python
async def check_rate_limit(page: Page) -> bool:
    """Detect rate limit indicators on page."""
    content = await page.content()
    indicators = ["limit reached", "rate limit", "too many requests", "slow down", "try again later"]
    return any(ind.lower() in content.lower() for ind in indicators)

---

### Cloud Storage (`packages/services/`)

#### [NEW] [cloud_storage.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/cloud_storage.py)

```python
class R2Storage:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        )
        self.bucket = os.getenv("R2_BUCKET")
    
    def upload_clip(self, local_path: Path, niche_id: str, clip_name: str) -> str:
        key = f"{niche_id}/clips/{clip_name}"
        self.client.upload_file(
            str(local_path),
            self.bucket,
            key,
            ExtraArgs={"Metadata": {"niche": niche_id}}
        )
        return f"r2://{self.bucket}/{key}"
    
    def download_clips(self, niche_id: str, local_dir: Path) -> list[Path]:
        """Download all clips for a niche to local directory."""
        paginator = self.client.get_paginator("list_objects_v2")
        paths = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{niche_id}/clips/"):
            for obj in page.get("Contents", []):
                local_path = local_dir / Path(obj["Key"]).name
                self.client.download_file(self.bucket, obj["Key"], str(local_path))
                paths.append(local_path)
        return sorted(paths)
```

---

### High-Speed Rendering Engine (`packages/services/`)

> [!CAUTION]
> **MoviePy Not Used**: MoviePy is too slow for long-form content (2+ hours for 5-minute video). We use native **FFmpeg filter graphs** via `ffmpeg-python` for 3.5-4.5x faster rendering.

#### [NEW] [video_editor.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/video_editor.py)

```python
import ffmpeg
from pathlib import Path

class FFmpegVideoEditor:
    """High-speed video editor using native FFmpeg filter graphs."""
    
    def __init__(self, niche_config: NicheConfig):
        self.config = niche_config
    
    def stitch_clips_with_transitions(self, clip_paths: list[Path], output_path: Path) -> Path:
        """Stitch clips using FFmpeg concat with crossfade transitions."""
        # Create file list for concat
        file_list = output_path.parent / "concat_list.txt"
        with open(file_list, "w") as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")
        
        # Apply crossfade transitions between clips
        if self.config.transition_type == "crossfade":
            # Build complex filter graph for crossfade
            inputs = [ffmpeg.input(str(p)) for p in clip_paths]
            filter_complex = self._build_crossfade_filter(inputs, duration=1.0)
            (
                ffmpeg
                .output(filter_complex, str(output_path), vcodec='libx264', acodec='aac')
                .overwrite_output()
                .run()
            )
        else:
            # Simple concat without transitions
            (
                ffmpeg
                .input(str(file_list), format='concat', safe=0)
                .output(str(output_path), c='copy')
                .overwrite_output()
                .run()
            )
        
        return output_path
    
    def apply_ken_burns(self, input_path: Path, output_path: Path, zoom_ratio: float = 1.1) -> Path:
        """
        Apply Ken Burns (zoom/pan) effect using FFmpeg zoompan filter.
        Creates subtle movement to maintain visual engagement.
        """
        # Get video duration
        probe = ffmpeg.probe(str(input_path))
        duration = float(probe['streams'][0]['duration'])
        fps = 24
        total_frames = int(duration * fps)
        
        # zoompan filter: slowly zoom from 1.0 to zoom_ratio over duration
        (
            ffmpeg
            .input(str(input_path))
            .filter(
                'zoompan',
                z=f'min(zoom+0.001,{zoom_ratio})',  # Gradual zoom
                d=total_frames,
                s='1920x1080',
                fps=fps
            )
            .output(str(output_path), vcodec='libx264', pix_fmt='yuv420p')
            .overwrite_output()
            .run()
        )
        return output_path
    
    def _build_crossfade_filter(self, inputs: list, duration: float = 1.0):
        """Build FFmpeg filter graph for crossfade transitions."""
        # Chain crossfade filters between consecutive clips
        if len(inputs) < 2:
            return inputs[0].video
        
        result = inputs[0]
        for i, inp in enumerate(inputs[1:], 1):
            result = ffmpeg.filter(
                [result, inp],
                'xfade',
                transition='fade',
                duration=duration,
                offset=i * 10 - duration  # Adjust based on clip durations
            )
        return result
```

**Performance Comparison:**
| Method | 5-min Video | 1-hour Video | 5-hour Video |
|--------|-------------|--------------|---------------|
| MoviePy | ~2 hours | ~24 hours | **Crashes** |
| FFmpeg | ~30 min | ~6 hours | ~30 hours |

---

### Audio Engine with Sidechain Compression (`packages/services/`)

> [!TIP]
> **Professional Audio Ducking**: Uses FFmpeg `sidechaincompress` filter to automatically lower music when narration is active — the same technique used in broadcast.

#### [NEW] [audio_engine.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/audio_engine.py)

```python
import ffmpeg
import edge_tts
from pathlib import Path

class AudioEngine:
    """Audio processing with FFmpeg sidechain compression for professional ducking."""
    
    def __init__(self, niche_config: NicheConfig):
        self.config = niche_config
    
    async def generate_narration(self, scenes: list[Scene], output_dir: Path) -> list[Path]:
        """Generate TTS audio for each scene using Edge-TTS."""
        paths = []
        for i, scene in enumerate(scenes):
            output_path = output_dir / f"narration_{i:03d}.mp3"
            communicate = edge_tts.Communicate(scene.narration, self.config.voice_id)
            await communicate.save(str(output_path))
            paths.append(output_path)
        return paths
    
    def concat_narrations(self, narration_paths: list[Path], output_path: Path, gap_seconds: float = 0.5) -> Path:
        """Concatenate narration clips with gaps between them."""
        # Create file list with silence gaps
        inputs = []
        for path in narration_paths:
            inputs.append(ffmpeg.input(str(path)))
            # Add silence gap
            inputs.append(ffmpeg.input(f'anullsrc=r=44100:cl=stereo', f='lavfi', t=gap_seconds))
        
        (
            ffmpeg
            .concat(*inputs, v=0, a=1)
            .output(str(output_path))
            .overwrite_output()
            .run()
        )
        return output_path
    
    def mix_with_sidechain_compression(
        self,
        narration_path: Path,
        music_path: Path,
        output_path: Path,
        video_duration: float
    ) -> Path:
        """
        Mix narration with background music using FFmpeg sidechaincompress.
        Music automatically ducks when narration is active.
        """
        # Input streams
        narration = ffmpeg.input(str(narration_path))
        music = (
            ffmpeg
            .input(str(music_path), stream_loop=-1)  # Loop music
            .filter('atrim', duration=video_duration)  # Trim to video length
            .filter('volume', volume=0.3)  # Base volume at 30%
        )
        
        # Apply sidechain compression: music is compressed when narration is present
        # Parameters:
        # - threshold: -20dB (when narration exceeds this, compression starts)
        # - ratio: 4:1 (how much to reduce music)
        # - attack: 200ms (how fast to duck)
        # - release: 1000ms (how fast to recover)
        ducked_music = ffmpeg.filter(
            [music, narration],
            'sidechaincompress',
            threshold=0.1,    # -20dB
            ratio=4,
            attack=200,
            release=1000,
            level_sc=1
        )
        
        # Mix ducked music with narration
        mixed = ffmpeg.filter([ducked_music, narration], 'amix', inputs=2, duration='longest')
        
        (
            ffmpeg
            .output(mixed, str(output_path), acodec='aac')
            .overwrite_output()
            .run()
        )
        return output_path
    
    def insert_sfx(self, audio_path: Path, sfx_markers: list[SFXMarker], output_path: Path) -> Path:
        """Insert sound effects at specified timestamps using FFmpeg."""
        inputs = [ffmpeg.input(str(audio_path))]
        delays = ['0']
        
        for marker in sfx_markers:
            sfx_path = self.config.sfx.get(marker.sfx_key)
            if sfx_path:
                inputs.append(ffmpeg.input(sfx_path))
                delays.append(str(int(marker.timestamp * 1000)))  # Convert to ms
        
        # Use adelay filter to position SFX at correct timestamps
        mixed = ffmpeg.filter(inputs, 'amix', inputs=len(inputs), dropout_transition=0)
        
        (
            ffmpeg
            .output(mixed, str(output_path))
            .overwrite_output()
            .run()
        )
        return output_path
```

**Sidechain Compression Explained:**
```
Narration:  ___/‾‾‾‾\___/‾‾‾‾‾‾\___
Music Vol:  ‾‾‾\_____/‾‾\_________/‾‾‾
            ↑         ↑             ↑
        Full vol  Ducked       Full vol
```

---

### Subtitle Engine (`packages/services/`)

#### [NEW] [subtitle_engine.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/subtitle_engine.py)

```python
import pysrt
from moviepy import TextClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip

class SubtitleEngine:
    STYLE = {
        "font": "Arial-Bold",
        "fontsize": 48,
        "color": "yellow",
        "stroke_color": "black",
        "stroke_width": 2,
    }
    
    def generate_srt(self, scenes: list[Scene], output_path: Path) -> Path:
        """Generate SRT file from scene timings."""
        subs = pysrt.SubRipFile()
        current_time = 0
        
        for i, scene in enumerate(scenes):
            sub = pysrt.SubRipItem(
                index=i + 1,
                start=pysrt.SubRipTime(seconds=current_time),
                end=pysrt.SubRipTime(seconds=current_time + scene.duration),
                text=self._wrap_text(scene.narration, max_chars=40)
            )
            subs.append(sub)
            current_time += scene.duration
        
        subs.save(str(output_path), encoding="utf-8")
        return output_path
    
    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        """Burn subtitles into video with high-contrast styling."""
        video = VideoFileClip(str(video_path))
        
        def make_text(txt):
            return TextClip(
                text=txt,
                font=self.STYLE["font"],
                font_size=self.STYLE["fontsize"],
                color=self.STYLE["color"],
                stroke_color=self.STYLE["stroke_color"],
                stroke_width=self.STYLE["stroke_width"],
            )
        
        subtitles = SubtitlesClip(str(srt_path), make_text)
        subtitles = subtitles.with_position(("center", "bottom"))
        
        final = CompositeVideoClip([video, subtitles])
        final.write_videofile(str(output_path), codec="libx264")
        return output_path
```

---

### YouTube Distribution with Copyright Pre-Check (`packages/services/`)

> [!CAUTION]
> **Content ID Protection**: Videos are uploaded as **Private** first. After 15-minute processing, we check for copyright claims#### [NEW] [video_editor.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/video_editor.py)
#### [NEW] [youtube_uploader.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/packages/services/youtube_uploader.py)

### Flexible Cast System (Multi-Character Support)
**Goal**: Allow users to define a "Cast" of characters for a channel and assign specific characters to scenes.

#### Database Changes
- **[MODIFY] schema.prisma**:
    - Add `Character` model (id, name, imageUrl, channelId).
    - Update `Channel` to have `characters Character[]`.

#### API Changes (`apps/api/main.py`)
- `POST /channels/{niche_id}/characters`: Upload character image & create record.
- `DELETE /characters/{char_id}`: Remove a character.
- Update `VideoScript` model to include `characterId` per `Scene`.

#### Frontend Changes
- **[MODIFY] channel-manager.tsx**:
    - Replace single anchor image upload with a "Cast Grid".
    - "Add Character" card with file upload and name input.
- **[MODIFY] script-editor.tsx**:
    - Add "Character" select dropdown to each Scene card.
    - Default to "Environment Only" or a specific character.

## Verification Plan
```python
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import asyncio
import logging

logger = logging.getLogger(__name__)

class YouTubeUploader:
    # Include force-ssl scope for status updates
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl"
    ]
    
    def __init__(self, niche_id: str):
        self.niche_id = niche_id
        self.credentials = self._load_credentials()
        self.youtube = build("youtube", "v3", credentials=self.credentials)
    
    def _load_credentials(self) -> Credentials:
        """Load niche-specific OAuth tokens."""
        token_path = Path(f"./secrets/{self.niche_id}_token.json")
        if token_path.exists():
            return Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
        
        # First-time auth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            os.getenv("GOOGLE_CLIENT_SECRETS_PATH"),
            self.SCOPES
        )
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
        return creds
    
    async def upload_with_copyright_check(
        self,
        video_path: Path,
        title: str,
        description: str,
        niche_config: NicheConfig,
        auto_publish: bool = True
    ) -> dict:
        """
        Safe upload workflow:
        1. Upload as PRIVATE
        2. Wait 15 minutes for processing
        3. Check copyright status via API
        4. Only make PUBLIC if no claims detected
        """
        # Step 1: Upload as PRIVATE
        video_id = await self._upload_private(video_path, title, description, niche_config)
        logger.info(f"✅ Uploaded as PRIVATE: {video_id}")
        
        if not auto_publish:
            return {"video_id": video_id, "status": "private", "message": "Manual review required"}
        
        # Step 2: Wait for YouTube processing (15 minutes)
        logger.info("⏳ Waiting 15 minutes for YouTube processing...")
        await asyncio.sleep(900)  # 15 minutes
        
        # Step 3: Check copyright and upload status
        status_check = await self._check_video_status(video_id)
        
        if status_check["has_issues"]:
            logger.warning(f"⚠️ Issues detected: {status_check['issues']}")
            return {
                "video_id": video_id,
                "status": "private",
                "issues": status_check["issues"],
                "message": "Video kept PRIVATE due to detected issues"
            }
        
        # Step 4: Make PUBLIC (or UNLISTED for safety)
        await self._update_privacy(video_id, "unlisted")
        logger.info(f"🎉 Video published as UNLISTED: {video_id}")
        
        return {
            "video_id": video_id,
            "status": "unlisted",
            "url": f"https://youtube.com/watch?v={video_id}"
        }
    
    async def _upload_private(
        self,
        video_path: Path,
        title: str,
        description: str,
        niche_config: NicheConfig
    ) -> str:
        """Upload video as PRIVATE with AI disclosure flag."""
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": niche_config.tags,
                "categoryId": niche_config.yt_category_id,
            },
            "status": {
                "privacyStatus": "private",  # Always start PRIVATE
                "selfDeclaredMadeForKids": False,
                # CRITICAL: AI Disclosure for YouTube 2025/2026 policy
                "containsSyntheticMedia": True  # Toggle "Altered Content" flag
            }
        }
        
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True
        )
        
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = self._resumable_upload(request)
        return response["id"]
    
    async def _check_video_status(self, video_id: str) -> dict:
        """
        Check video processing status and copyright claims.
        Returns dict with 'has_issues' bool and 'issues' list.
        """
        response = self.youtube.videos().list(
            part="status,contentDetails",
            id=video_id
        ).execute()
        
        if not response.get("items"):
            return {"has_issues": True, "issues": ["Video not found"]}
        
        video = response["items"][0]
        status = video.get("status", {})
        
        issues = []
        
        # Check upload status
        upload_status = status.get("uploadStatus")
        if upload_status != "processed":
            issues.append(f"Upload status: {upload_status}")
        
        # Check for rejection
        rejection_reason = status.get("rejectionReason")
        if rejection_reason:
            issues.append(f"Rejected: {rejection_reason}")
        
        # Check privacy status issues
        failure_reason = status.get("failureReason")
        if failure_reason:
            issues.append(f"Failure: {failure_reason}")
        
        # Note: Full Content ID claims require YouTube Content ID API access
        # which is separate from Data API. We check what's available.
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues
        }
    
    async def _update_privacy(self, video_id: str, privacy: str):
        """Update video privacy status."""
        self.youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {"privacyStatus": privacy}
            }
        ).execute()
    
    def _resumable_upload(self, request) -> dict:
        """Handle resumable upload with retries."""
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload progress: {int(status.progress() * 100)}%")
        return response
```

---

### Extended Inngest Pipeline

#### [NEW] [inngest_client.py](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/apps/api/inngest_client.py)

```python
import inngest

client = inngest.Inngest(app_id="youtube-factory")

@client.create_function(
    fn_id="full-video-pipeline",
    trigger=inngest.TriggerEvent(event="video/generation.started"),
    retries=3
)
async def full_video_pipeline(ctx: inngest.Context) -> dict:
    script = ctx.event.data["script"]
    niche_id = script["niche_id"]
    
    # Step 1: Generate consistent images for each scene
    image_paths = await ctx.step.run("generate-images", lambda: 
        generate_all_images(script["scenes"], niche_id)
    )
    
    # Step 2: Animate each image with Grok
    clip_paths = await ctx.step.run("animate-scenes", lambda:
        animate_all_scenes(image_paths, script["scenes"])
    )
    
    # Step 3: Upload raw clips to R2
    r2_urls = await ctx.step.run("upload-clips-to-r2", lambda:
        upload_clips(clip_paths, niche_id)
    )
    
    # Step 4: Download clips and stitch with MoviePy
    stitched_path = await ctx.step.run("stitch-video", lambda:
        stitch_video(niche_id)
    )
    
    # Step 5: Generate narration with Edge-TTS
    audio_path = await ctx.step.run("generate-audio", lambda:
        generate_audio(script["scenes"], niche_id)
    )
    
    # Step 6: Burn subtitles
    subtitled_path = await ctx.step.run("burn-subtitles", lambda:
        burn_subtitles(stitched_path, script["scenes"])
    )
    
    # Step 7: Combine video + audio
    final_path = await ctx.step.run("combine-av", lambda:
        combine_audio_video(subtitled_path, audio_path)
    )
    
    # Step 8: Upload final video to R2
    final_r2_url = await ctx.step.run("upload-final-to-r2", lambda:
        upload_final(final_path, niche_id, script["title"])
    )
    
    # Step 9: Upload to YouTube (Unlisted)
    youtube_id = await ctx.step.run("upload-to-youtube", lambda:
        upload_to_youtube(final_path, script, niche_id)
    )
    
    return {
        "status": "complete",
        "r2_url": final_r2_url,
        "youtube_id": youtube_id,
        "youtube_url": f"https://youtube.com/watch?v={youtube_id}"
    }
```

---

### Asset Directories

#### [NEW] [assets/niche_pets/](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/assets/niche_pets/)
```
assets/niche_pets/
├── anchor.png          # Character reference image
└── README.md           # Niche-specific notes
```

#### [NEW] [assets/niche_history/](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/assets/niche_history/)
```
assets/niche_history/
├── anchor.png          # Character reference image
└── README.md           # Niche-specific notes
```

#### [NEW] [assets/audio/](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/assets/audio/)
```
assets/audio/
├── happy_ukulele.mp3   # Pets niche background music
└── epic_orchestra.mp3  # History niche background music
```

#### [NEW] [assets/sfx/](file:///c:/Users/pc/Documents/google-antigravity/youtube-automation/assets/sfx/)
```
assets/sfx/
├── cat_meow.mp3        # Pets SFX
└── sword_clash.mp3     # History SFX
```

---

### Next.js Dashboard (`apps/web/`)

#### [NEW] Next.js 15 App Router Project
```
apps/web/
├── app/
│   ├── page.tsx              # Dashboard home with stats
│   ├── submit/page.tsx       # Script submission form
│   ├── jobs/page.tsx         # Job monitoring view
│   ├── jobs/[id]/page.tsx    # Single job detail
│   ├── assets/page.tsx       # R2 asset browser
│   └── youtube/page.tsx      # YouTube upload status
├── components/
│   ├── NicheSelector.tsx     # Dropdown for niche selection
│   ├── ScriptEditor.tsx      # JSON script editor
│   ├── JobProgress.tsx       # Real-time job progress
│   └── VideoPreview.tsx      # Embedded video player
└── package.json
```

---

## Verification Plan

### Automated Tests
```bash
# Run API tests
cd apps/api && pytest tests/ -v

# Type checking
pyright packages/services/

# Test individual services
pytest tests/test_pulid_generator.py -v
pytest tests/test_video_editor.py -v
pytest tests/test_audio_engine.py -v

# Playwright test (headed mode for debugging)
GROK_HEADLESS=false pytest tests/test_grok_agent.py
```

### Integration Test: 30-Second Sample Video
1. **Submit minimal script**:
   ```bash
   curl -X POST http://localhost:8000/scripts/submit \
     -H "Content-Type: application/json" \
     -d '{
       "niche_id": "mochi_pets",
       "title": "Test Video",
       "description": "Testing the pipeline",
       "scenes": [
         {"prompt": "cat sitting on windowsill", "narration": "Meet Mochi, the curious cat.", "duration": 10},
         {"prompt": "cat playing with yarn", "narration": "She loves to play all day.", "duration": 10},
         {"prompt": "cat sleeping on couch", "narration": "But nap time is her favorite.", "duration": 10}
       ]
     }'
   ```

2. **Monitor Inngest dashboard** at `http://localhost:8288`

3. **Verify output quality**:
   - [ ] Audio ducking lowers music during speech
   - [ ] Subtitle timing matches narration
   - [ ] Transitions are smooth
   - [ ] Final video is playable

### Manual Verification Checklist
- [ ] HF_TOKEN authentication works correctly
- [ ] Grok rate-limit handler sleeps 2 hours correctly
- [ ] R2 uploads have correct `niche` metadata tag
- [ ] YouTube upload defaults to Unlisted
- [ ] Ken Burns effect visible on static segments
- [ ] SFX plays at correct timestamps

### Browser Tests (Dashboard)
- [ ] Dashboard loads correctly
- [ ] Niche selector populates from `channels.json`
- [ ] Script submission form validates input
- [ ] Job status updates in real-time
- [ ] R2 asset browser shows niche folders
