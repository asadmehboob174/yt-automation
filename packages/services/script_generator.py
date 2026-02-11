"""
Script Generator using Gemini 2.0 Flash API.

Generates structured video scripts with scenes, narration, 
character prompts, and timing information.
"""
import os
import httpx
import json
import asyncio
import re
from typing import Optional
from pydantic import BaseModel


class SceneOutput(BaseModel):
    """Output schema for a single scene."""
    voiceover_text: str
    character_pose_prompt: str
    background_description: str
    duration_in_seconds: int = 10
    camera_angle: str = "medium shot"
    motion_description: str = ""
    dialogue: Optional[str] = None
    character_name: str = "Character"
    emotion: str = "neutrally"

    def get_full_image_prompt(self, style_suffix: str = "") -> str:
        """Combine fields for a complete image generation prompt."""
        # Add cinematic keywords for realism
        cinematic_keywords = "Hyper-realistic, 8k resolution, National Geographic photography style, shot on 85mm lens, sharp focus, detailed textures, soft bokeh background, cinematic lighting"
        return f"{self.character_pose_prompt}, {self.background_description}, {self.camera_angle}, {style_suffix}, {cinematic_keywords}"


class VideoScriptOutput(BaseModel):
    """Output schema for complete video script."""
    title: str
    description: str
    scenes: list[SceneOutput]


class MasterCharacter(BaseModel):
    """Master character prompt for consistent image generation."""
    name: str  # e.g., "THE BOY", "THE DRAGON"
    prompt: str  # Detailed visual description
    imageUrl: Optional[str] = None
    locked: bool = False


class GrokVideoPrompt(BaseModel):
    """Detailed Grok-specific prompt structure for cinema-quality video."""
    main_action: str
    camera_movement: str = ""
    character_animation: str = ""
    emotion: str = ""
    pacing: str = ""
    vfx: str = ""
    lighting_changes: str = ""
    full_prompt: Optional[str] = None


class SceneBreakdown(BaseModel):
    """Scene breakdown with both image and video prompts."""
    scene_number: int
    scene_title: str = "Untitled Scene"
    voiceover_text: str = "" # Added: Required for TTS
    character_pose_prompt: str = "" # Added: Required for consistent character gen
    background_description: str = "" # Added: Background details
    text_to_image_prompt: str = ""  # Static scene description (Legacy/Combined)
    image_to_video_prompt: str = ""  # Dynamic movement (Legacy/Combined)
    motion_description: str = "" # Added: Specific motion for Grok
    duration_in_seconds: int = 10
    camera_angle: str = "Medium shot"
    dialogue: Optional[str] = None
    sound_effect: Optional[str] = None # Legacy single string
    emotion: str = "neutrally" # Legacy string
    
    # New structured fields
    grok_video_prompt: Optional[GrokVideoPrompt] = None
    sfx: Optional[list[str]] = None
    music_notes: Optional[str] = None


class YouTubeUploadMetadata(BaseModel):
    title: str
    description: str
    tags: list[str]
    privacyStatus: str = "private"
    madeForKids: bool = False
    categoryId: str = "22"
    publishAt: Optional[str] = None
    playlistId: Optional[str] = None
    playlistTitle: Optional[str] = None

class YouTubeEngagement(BaseModel):
    pinnedComment: Optional[str] = None

class YouTubeUpload(BaseModel):
    metadata: YouTubeUploadMetadata
    engagement: Optional[YouTubeEngagement] = None


class SoundtrackConfig(BaseModel):
    background_music: str
    music_timing: str
    sfx_mixing: str

class TransitionConfig(BaseModel):
    type: str
    duration: str
    effects: str

class ColorGradingConfig(BaseModel):
    overall_look: str
    consistency: str

class TitleCardsConfig(BaseModel):
    opening: str
    closing: str

class FinalAssembly(BaseModel):
    total_clips: int
    soundtrack: SoundtrackConfig
    transitions: TransitionConfig
    color_grading: ColorGradingConfig
    title_cards: TitleCardsConfig
    youtube_optimization: Optional[dict] = None


class TechnicalBreakdownOutput(BaseModel):
    """Output schema for technical breakdown (characters + scenes)."""
    characters: list[MasterCharacter]
    scenes: list[SceneBreakdown]
    youtube_upload: Optional[YouTubeUpload] = None
    final_assembly: Optional[FinalAssembly] = None


class ScriptGenerator:
    """Generate video scripts using HuggingFace Inference API (Mistral-7B)."""
    
    # Gemini API
    GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    # HuggingFace Inference API (OpenAI-compatible router endpoint)
    HF_API = "https://router.huggingface.co/v1/chat/completions"
    HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"
    
    def __init__(self):
        # Gemini key
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_key:
            print("⚠️ GEMINI_API_KEY not found. Gemini generation will fail.")
        
        # HuggingFace token
        self.hf_token = os.getenv("HF_TOKEN")
        if not self.hf_token:
            # We don't raise error here anymore to allow Gemini-only usage if HF is broken/missing
            print("⚠️ HF_TOKEN not found. Hugging Face generation will fail.")
        
        # Rate limiter: HuggingFace free tier has 300 req/hour
        self._call_semaphore = asyncio.Semaphore(1)  # One call at a time
        self._last_call_time = 0
        self._min_interval = 2.0  # 2 seconds between calls (more generous than Gemini)
    
    def _build_prompt(self, topic: str, niche_style: str, scene_count: int = 10) -> str:
        """Build the prompt for Gemini using the 'Retention-First' framework."""
        return f"""### ROLE
Act as an elite YouTube Scriptwriter and Content Strategist specializing in high-retention storytelling. Your goal is to keep viewers watching from the first second until the very end.

### WRITING STYLE RULES (STRICT)
1. NO CLICHÉS: Never start with "Welcome back," "In this video," or "Have you ever wondered."
2. SHORT SENTENCES: Use punchy, conversational language. Avoid "academic" or "robotic" flow.
3. THE HOOK: The first 5 seconds must start in the middle of a conflict, a mystery, or a bold claim.
4. PATTERN INTERRUPTS: Every 45 seconds, insert a "Curiosity Gap" (e.g., "But that was only the beginning," or "Here is where it gets weird.")
5. SHOW, DON'T TELL: Instead of saying "The dog was happy," describe the visual: "Mochi's tail was blurring from wagging so fast."

Context:
Topic: "{topic}"
Channel Style: {niche_style}

### STRUCTURAL REQUIREMENTS
- [HOOK]: 0-15 seconds. High stakes.
- [THE BUILD]: Introduce the main topic with a unique angle.
- [CONTENT BLOCKS]: Breakdown of the main points with [VISUAL CUE] tags for B-roll.
- [THE TWIST]: A piece of information the viewer didn't see coming.
- [OUTRO]: 5 seconds max. No long goodbyes.

### OUTPUT FORMAT
Return ONLY valid JSON in this exact format:
{{
  "title": "Click-worthy Title",
  "description": "YouTube description (2-3 sentences)",
  "scenes": [
    {{
      "voiceover_text": "Spoken word...",
      "character_pose_prompt": "Visual description...",
      "background_description": "Setting...",
      "duration_in_seconds": 10,
      "camera_angle": "medium shot",
      "motion_description": "Movement...",
      "dialogue": null,
      "character_name": "Character",
      "emotion": "neutrally"
    }}
  ]
}}

(Note: 'scenes' maps to 'script_segments'. 'character_pose_prompt' + 'background_description' + 'motion_description' combined act as 'visual_cue'.)
(CRITICAL: Look for "Shot Type", "Camera", "Angle" in manual scripts and map to 'camera_angle')

Generate exactly {scene_count} scenes adhering to the structure above.
"""

    async def _call_llm(self, prompt: str, gemini_model: str = "gemini-flash-latest", json_mode: bool = False) -> str:
        """
        Unified LLM caller that handles routing between providers if needed.
        Currently redirects to HF primarily, but we can use this for Gemini too.
        """
        try:
             # Default to HuggingFace if available
             if self.hf_token:
                 return await self._call_huggingface(prompt)
             elif self.gemini_key:
                 return await self._call_gemini(prompt)
             else:
                 raise ValueError("No AI credentials found (HF_TOKEN or GEMINI_API_KEY)")
        except Exception:
             # Fallback to Gemini if HF fails inside this method?
             # For now, let caller handle fallbacks to be explicit.
             if self.gemini_key:
                  return await self._call_gemini(prompt)
             raise

    async def _call_gemini(self, prompt: str, model: str = "gemini-2.0-flash") -> str:
        """Call Google Gemini API."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is missing")
            
        async with self._call_semaphore:
            # Rate limit handling
            now = asyncio.get_event_loop().time()
            if now - self._last_call_time < 0.5: # Gemini is faster
                await asyncio.sleep(0.5)
                
            headers = {"Content-Type": "application/json"}
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 8192,
                    "responseMimeType": "application/json"
                }
            }
            
            print(f"✨ Calling Gemini ({model})...")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                
                self._last_call_time = asyncio.get_event_loop().time()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    return ""
    async def _call_huggingface(self, prompt: str, max_tokens: int = 16384, timeout: float = 120.0, retries: int = 3) -> str:
        """Call HuggingFace Inference API."""
        async with self._call_semaphore:
            now = asyncio.get_event_loop().time()
            time_since_last = now - self._last_call_time
            if time_since_last < self._min_interval:
                await asyncio.sleep(self._min_interval - time_since_last)
            
            headers = {
                "Authorization": f"Bearer {self.hf_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.HF_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "stream": False
            }
            
            print(f"🤖 Calling HuggingFace ({self.HF_MODEL})...")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                for attempt in range(retries):
                    try:
                        resp = await client.post(self.HF_API, json=payload, headers=headers)
                        
                        if resp.status_code == 429:
                            wait_time = 5 * (attempt + 1)
                            print(f"⚠️ Rate limited. Waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        resp.raise_for_status()
                        result = resp.json()
                        self._last_call_time = asyncio.get_event_loop().time()
                        return result['choices'][0]['message']['content']
                        
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 403:
                            print(f"❌ HF Access Forbidden (403). Your token may not have access to {self.HF_MODEL} or the router endpoint.")
                            raise e # Propagate to allow fallback logic in caller
                        print(f"⚠️ HF HTTP Error (Attempt {attempt+1}/{retries}): {e}")
                        if attempt == retries - 1: raise e
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"⚠️ HF Call failed (Attempt {attempt+1}/{retries}): {e}")
                        if attempt == retries - 1:
                            raise e
                        await asyncio.sleep(2)
            return ""

    async def generate(
        self,
        topic: str,
        niche_style: str,
        scene_count: int = 10
    ) -> VideoScriptOutput:
        """Generate a video script for the given topic."""
        prompt = self._build_prompt(topic, niche_style, scene_count)
        
        # text = await self._call_llm(prompt)
        raise ValueError("AI generation is disabled. Please use 'Manual Script' mode.")
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        script_data = json.loads(text.strip())
        return VideoScriptOutput(**script_data)

    async def generate_story_narrative(
        self,
        story_idea: str,
        scene_count: int = 12,
        style: str = "Pixar/Disney 3D animation"
    ) -> str:
        """
        Stage 1: Generate a detailed story narrative in paragraph form.
        User reviews this before proceeding to technical breakdown.
        """
        prompt = f"""Act as a master storyteller and screenwriter for high-end animated films.
        
TASK: Create a gripping, emotional, and visually stunning story narrative based on this idea:
STORY IDEA: "{story_idea}"

CONSTRAINTS:
- Target Length: Adapted into exactly {scene_count} scenes.
- Characters: Exactly 2 MAIN CHARACTERS with distinct personalities.
- Style: {style}

STRUCTURE:
1. The Hook: Start immediately with conflict or mystery.
2. The Journey: Escalating tension and character growth.
3. The Climax: A high-stakes moment of truth.
4. Resolution: Satisfying but leaves a lingering emotion.

TONE:
- Avoid clichés. No "Once upon a time" or generic tropes.
- Focus on "Show, Don't Tell" regarding emotions.
- Write in flowing paragraphs (NOT a scene breakdown yet).
- Length: Approximately {scene_count * 2} to {scene_count * 3} paragraphs.

Output ONLY the story narrative, no headers or metadata."""

        # text = await self._call_llm(prompt)
        # return text.strip()
        raise ValueError("AI generation is disabled. Please use 'Manual Script' mode.")

    def _repair_truncated_json(self, text: str) -> str:
        """Force-closes truncated JSON by finding the last bracket/brace and adding the remainder."""
        text = text.strip()
        
        # If it already ends with }, we assume it's possibly complete
        if text.endswith("}"):
            return text
            
        print("⚠️ Detected truncated JSON. Attempting surgery...")
        
        # 1. If it ends for sure inside the 'scenes' array, try to find the last complete scene object
        if '"scenes": [' in text:
            scenes_start = text.find('"scenes": [')
            # Find the last closing brace after the scenes start
            last_brace = text.rfind("}")
            
            if last_brace != -1 and last_brace > scenes_start:
                # If there's an opening brace after the last closing, we have a partial object
                last_opening = text.rfind("{")
                if last_opening > last_brace:
                    text = text[:last_brace+1]
                else:
                    # Current object is likely partial because it doesn't end with } (handled by early return)
                    # or it might be a nested object. Let's be safe and cut at last brace.
                    text = text[:last_brace+1]
            else:
                # No complete scenes. Cut back to start of array.
                text = text[:scenes_start + len('"scenes": [')]
            
            # Strip trailing comma if we cut right after a scene
            text = text.strip()
            if text.endswith(","):
                text = text[:-1]

            # Close the structure
            if not text.endswith("]"):
                 text += "\n  ]\n}"
            if not text.endswith("}"):
                 text += "\n}"
        
        # General bracket balancer as a catch-all
        brace_count = text.count("{") - text.count("}")
        bracket_count = text.count("[") - text.count("]")
        
        for _ in range(bracket_count):
            text += "\n  ]"
        for _ in range(brace_count):
            text += "\n}"
            
        return text

    def _clean_json_text(self, text: str) -> str:
        """
        Aggressively clean JSON text to fix common LLM output issues.
        """
        # Step 1: Extract JSON if wrapped in markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        # Step 2: Trim and find JSON boundaries
        text = text.strip()
        if not text.startswith("{") and "{" in text:
            text = text[text.find("{"):]
            
        # Robustly find the matching closing brace
        brace_count = 0
        json_end_index = -1
        
        for i, char in enumerate(text):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end_index = i + 1
                    break
        
        if json_end_index != -1:
            text = text[:json_end_index]
        else:
            # If not found, it's truncated. Repair it.
            text = self._repair_truncated_json(text)
        
        # Step 3: Replace curly/smart quotes with straight quotes
        quote_chars = [
            '\u201c', '\u201d', '\u201e', '\u201f',  # Various double quotes
            '\u2033', '\u301d', '\u301e', '\u301f', '\uff02'
        ]
        for qc in quote_chars:
            text = text.replace(qc, '"')
        
        # Step 3.5: Convert single-quoted strings to double-quoted strings
        # Pattern: "key": 'value' should become "key": "value"
        def fix_single_quotes(match):
            key_part = match.group(1)  # e.g., '"prompt": '
            value = match.group(2)      # the value without quotes
            # Escape any double quotes inside the value
            value_escaped = value.replace('"', '\\"')
            return f'{key_part}"{value_escaped}"'
        
        # Match "field": 'value' pattern (single quotes around value)
        text = re.sub(r'("[\w_]+":\s*)\'([^\']*?)\'', fix_single_quotes, text)
        
        # Also handle multiline single-quoted values
        text = re.sub(r'("[\w_]+":\s*)\'(.+?)\'(?=\s*[,}\n])', fix_single_quotes, text, flags=re.DOTALL)
        
        # Step 4: AGGRESSIVE duplicate quote fixes
        # Fix pattern: "key": ""value or "key":""value (quotes after colon)
        text = re.sub(r'(":\s*)"+"', r'\1"', text)
        
        # Fix pattern: "value"" or "value""" (trailing duplicate quotes)
        text = re.sub(r'(")"+(\s*[,}\]])', r'\1\2', text)
        
        # Fix pattern: ""value at start of strings
        text = re.sub(r'(:\s*|,\s*|{\s*|"\s*:\s*)""+', r'\1"', text)
        
        # Generic catch-all: Replace any sequence of 2+ quotes with single quote
        # This is aggressive but necessary for broken LLM outputs
        before_count = text.count('""')
        text = re.sub(r'"{2,}', '"', text)
        after_count = text.count('""')
        
        if before_count > 0:
            print(f"🔧 Cleaned duplicate quotes: {before_count} → {after_count}")
        
        # Step 5: Fix internal unescaped quotes and literal newlines.
        # This is a complex multi-pass repair.
        fields = ["name", "prompt", "text_to_image_prompt", "image_to_video_prompt", 
                  "dialogue", "scene_title", "voiceover_text", "character_pose_prompt",
                  "background_description", "motion_description", "duration_in_seconds", "camera_angle"]
        
        # We search for "field": "VALUE" where VALUE might contain " that should be escaped.
        # We look ahead for the next field name to know where the current value ends.
        next_field_pattern = r'|'.join([rf'"{f}":' for f in fields]) + r'|},|\]|}$'
        
        def repair_field_value(match):
            prefix = match.group(1)   # e.g., '"field": "' or '"field": \''
            raw_value = match.group(2) # the content including potential unescaped quotes
            
            # Normalize the prefix to ALWAYS end with a double quote
            # e.g. "field": ' -> "field": "
            field_part = prefix.split(':')[0]
            prefix = f'{field_part}: "'
            
            # First, normalize newlines
            val = raw_value.replace('\n', '\\n').replace('\r', '\\n').replace('\t', '\\t')
            
            # Escape all double quotes that aren't already escaped.
            val = val.replace('"', '\\"')
            
            return f'{prefix}{val}"'

        for field in fields:
            # Match "field": ["'] (content) (lookahead for next field or object end)
            # We use a greedy match for the content until we hit the next known field header.
            # This handles values starting with either " or '
            pattern = rf'("{field}":\s*["\'])(.+?)(?=["\']?\s*(?:{next_field_pattern}))'
            text = re.sub(pattern, repair_field_value, text, flags=re.DOTALL)
        
        return text

    async def generate_technical_breakdown(
        self,
        story_narrative: str,
        scene_count: int = 12,
        style: str = "High-quality Pixar/Disney 3D Render"
    ) -> TechnicalBreakdownOutput:
        """
        Stage 2: Extract characters and create scene breakdown from narrative.
        Returns master character prompts and scene-by-scene breakdown.
        """
        prompt = f"""You are an expert storyboard artist and 3D animation director.
STORY:
{story_narrative}

STYLE: {style}
TARGET SCENES: {scene_count}

Analyze the story and create EXACTLY {scene_count} scenes and establish 2 main characters.

Create a structured breakdown with:
1. MASTER CHARACTER PROMPTS: Define 2 main characters with detailed Text-to-Image prompts.
2. SCENE BREAKDOWN: For each of the {scene_count} scenes, provide:
   - scene_title: Brief title.
   - voiceover_text: Narration/Script (2 sentences max).
   - character_pose_prompt: [Style], [Lighting]. ([Character Name]: Brief Appearance). ACTION: [Action & Camera]. MUST REPEAT STYLE every time. Keep character appearance brief (e.g. "Boy: red hoodie").
   - text_to_image_prompt: FULL detailed description for image generation.
   - image_to_video_prompt: Dynamic movement for Grok (1-2 sentences).
   - motion_description: Concise instruction (e.g. "Pan right").
   - duration_in_seconds: 5-10.
   - camera_angle: "wide", "medium", "close-up", etc.
   - dialogue: '[CHARACTER]: (emotion) "Speech"'. Use null if no dialogue.

Return ONLY valid JSON in this exact format:
{{
  "characters": [
    {{
      "name": "CHARACTER NAME",
      "prompt": "Full detailed 3D render prompt..."
    }}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "...",
      "voiceover_text": "...",
      "text_to_image_prompt": "...",
      "character_pose_prompt": "...",
      "background_description": "...",
      "image_to_video_prompt": "...",
      "motion_description": "...",
      "duration_in_seconds": 10,
      "camera_angle": "medium",
      "dialogue": null
    }}
  ]
}}
Return ONLY valid JSON.
- For character_pose_prompt, keep it extremely brief: [Style]. ([Name]: visual). ACTION: [Action].
- DO NOT use unescaped double quotes inside strings.
"""

        # text = await self._call_huggingface(
        #     prompt,
        #     max_tokens=16384,
        #     timeout=120.0,
        #     retries=5
        # )
        # text = await self._call_llm(prompt, json_mode=True)
        raise ValueError("AI generation is disabled. Please use 'Manual Script' mode.")
        
        print(f"DEBUG: Raw technical breakdown text length: {len(text)}")
        
        # Use new aggressive cleaning method
        clean_text = self._clean_json_text(text)
        
        try:
            breakdown_data = json.loads(clean_text)
            print("✅ JSON parsed successfully!")
            return TechnicalBreakdownOutput(**breakdown_data)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            
            # Enhanced error reporting
            if "column" in str(e):
                match = re.search(r'line (\d+) column (\d+)', str(e))
                if match:
                    line_num = int(match.group(1))
                    col_num = int(match.group(2))
                    
                    # Find the error location
                    lines = clean_text.split('\n')
                    if line_num <= len(lines):
                        error_line = lines[line_num - 1]
                        print(f"\n🔴 ERROR AT LINE {line_num}, COLUMN {col_num}:")
                        print(f"   {error_line}")
                        if col_num <= len(error_line):
                            print(f"   {' ' * (col_num - 1)}^")
                        
                        # Show context (3 lines before and after)
                        start = max(0, line_num - 4)
                        end = min(len(lines), line_num + 3)
                        print(f"\n📄 CONTEXT (lines {start+1}-{end}):")
                        for i in range(start, end):
                            marker = ">>> " if i == line_num - 1 else "    "
                            print(f"{marker}{i+1:4d}: {lines[i]}")
            
            # Try one more aggressive repair
            print("\n🔧 Attempting final repair...")
            
            # Last resort: try to fix common patterns
            repaired = clean_text
            
            # Fix unescaped quotes inside values (very aggressive)
            # This looks for "key": "value with "internal" quotes"
            def fix_internal_quotes(match):
                prefix = match.group(1)  # e.g., '"dialogue": "'
                value = match.group(2)   # the actual value content
                suffix = match.group(3)  # the closing '"'
                # Escape all non-escaped quotes in the value
                value_fixed = re.sub(r'(?<!\\)"', r'\\"', value)
                # Return: prefix (already has opening ") + fixed value + suffix (closing ")
                return f'{prefix}{value_fixed}{suffix}'
            
            for field in ["dialogue", "prompt", "text_to_image_prompt", "image_to_video_prompt", 
                         "scene_title", "name"]:
                repaired = re.sub(
                    rf'("{field}":\s*")(.+?)("(?=\s*[,}}\n]))',
                    fix_internal_quotes,
                    repaired,
                    flags=re.DOTALL
                )
            
            try:
                breakdown_data = json.loads(repaired)
                print("✅ JSON Repair successful!")
                return TechnicalBreakdownOutput(**breakdown_data)
            except Exception as e2:
                print(f"❌ Final repair failed: {e2}")
                print(f"\n📝 CLEANED TEXT (first 1000 chars):\n{clean_text[:1000]}\n")
                raise e

    def parse_json_script(self, json_content: str) -> TechnicalBreakdownOutput:
        """Parse a JSON string directly into the breakdown model."""
        data = None
        try:
            # 1. Try Direct Parse (Best for valid JSON)
            data = json.loads(json_content)
        except json.JSONDecodeError:
            try:
                # 2. Try Cleaning (For LLM output / markdown)
                clean_text = self._clean_json_text(json_content)
                data = json.loads(clean_text)
            except Exception as e:
                print(f"❌ JSON Parsing failed: {e}")
                raise ValueError(f"Invalid JSON script: {e}")
            
        try:
            # Ensure fields exist
            characters = []
            if "characters" in data:
                for c in data["characters"]:
                    try:
                        # Alias support
                        if "whisk_prompt" in c and "prompt" not in c:
                            c["prompt"] = c["whisk_prompt"]
                            
                        # Handle ID if name is missing (or map ID as name fallback)
                        if "id" in c and "name" not in c:
                            c["name"] = c["id"]

                        characters.append(MasterCharacter(**c))
                    except Exception as e:
                        print(f"⚠️ Skipping invalid character: {e}")
            
            scenes = []
            if "scenes" in data:
                for s in data["scenes"]:
                    # Ensure defaults for key fields if missing
                    if "static_image_prompt" in s and not s.get("text_to_image_prompt"):
                        s["text_to_image_prompt"] = s.pop("static_image_prompt")
                        
                    s.setdefault("duration_in_seconds", 5)
                    s.setdefault("scene_number", len(scenes) + 1)
                    try:
                        scenes.append(SceneBreakdown(**s))
                    except Exception as e:
                        print(f"⚠️ Skipping invalid scene: {e}")
            
            youtube_upload = None
            if "youtube_upload" in data:
                try:
                    youtube_upload = YouTubeUpload(**data["youtube_upload"])
                except Exception as e:
                    print(f"⚠️ Skipping invalid youtube_upload: {e}")
            
            final_assembly = None
            if "final_assembly" in data:
                try:
                    final_assembly = FinalAssembly(**data["final_assembly"])
                except Exception as e:
                    print(f"⚠️ Skipping invalid final_assembly: {e}")
                    
            return TechnicalBreakdownOutput(
                characters=characters,
                scenes=scenes,
                youtube_upload=youtube_upload,
                final_assembly=final_assembly
            )
        except Exception as e:
            print(f"❌ JSON Model Validation failed: {e}")
            raise ValueError(f"Invalid JSON structure: {e}")

    async def parse_manual_script_llm(self, raw_text: str) -> TechnicalBreakdownOutput:
        """
        Extract structured data from a manual script using LLM.
        The LLM is designed to be FULLY FORMAT-AGNOSTIC - it should understand
        ANY reasonable script format without requiring specific labels.
        """
        print("📝 Manual Extraction: Using Hugging Face LLM (Intelligent Parser)...")
        
        prompt = f"""You are an expert script analyst and AI video production assistant. Your job is to intelligently extract structured data from ANY movie/video script format, regardless of how it's formatted.

SCRIPT TO ANALYZE:
---
{raw_text}
---

## YOUR EXTRACTION TASKS:

### TASK 1: EXTRACT ALL CHARACTERS
Find EVERY character defined in the script. Characters can appear in many formats:
- "CHARACTER NAME: description..." 
- "CHARACTER NAME (Role): description..."
- "[CHARACTER NAME] - description..."
- "Character 1: NAME - description..."
- "1. NAME - description..."
- Names in ALL CAPS followed by description
- Any section labeled "Characters", "Cast", "Character Prompts", etc.

For EACH character extract:
- **name**: The character's name (clean, no roles like "The Cat")
- **prompt**: Their FULL visual description (appearance, clothing, style, rendering details)

IMPORTANT: Extract ALL characters, not just the first 2. Look for 3, 4, or more characters.

### TASK 2: EXTRACT ALL SCENES
Find EVERY scene in the script. Scenes can be labeled as:
- "Scene 1", "SCENE 1:", "Scene 1:", etc.
- "Shot 1", "Panel 1", "Frame 1"
- Or just numbered sections

For EACH scene, you MUST extract these fields SEPARATELY:

| Field | What to Look For | Examples |
|-------|------------------|----------|
| **text_to_image_prompt** | Visual/image description | "Text to Image Prompt:", "Visual:", "Image:", "Setting:", "Description:" |
| **image_to_video_prompt** | Motion/animation description | "Text to Video Prompt:", "Motion:", "Animation:", "Action:", "Movement:" |
| **dialogue** | Speech, audio, sound effects | "Dialog:", "Dialogue:", "Audio:", "Voiceover:", "VO:", "SFX:", "(spoken)" |
| **camera_angle** | Shot type/camera info | "Shot Type:", "Short Type:", "Shot:", "Camera:", "Angle:", or embedded like "Medium shot of..." |

CRITICAL RULES FOR SCENE EXTRACTION:
1. **SEPARATE the fields** - Do NOT combine text_to_image_prompt with image_to_video_prompt
2. If you see "Text to Image Prompt:" - extract ONLY that content for text_to_image_prompt
3. If you see "Text to Video Prompt:" - extract ONLY that content for image_to_video_prompt  
4. Look for shot type at START of visual descriptions (e.g., "Wide shot of...", "Close-up of...")
5. Extract EVERY scene, even if there are 10, 12, or more scenes
6. Copy text EXACTLY as written (preserve the original wording)

### OUTPUT FORMAT (STRICT JSON):
Return ONLY this JSON structure, nothing else:

{{
  "characters": [
    {{
      "name": "CHARACTER_NAME",
      "prompt": "Full visual description..."
    }}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "Scene title if any",
      "text_to_image_prompt": "ONLY the visual/image description",
      "image_to_video_prompt": "ONLY the motion/animation description", 
      "dialogue": "Speech, voiceover, or audio cues",
      "camera_angle": "Wide Shot, Medium Shot, Close-up, etc.",
      "voiceover_text": "Same as dialogue",
      "motion_description": "Same as image_to_video_prompt",
      "character_pose_prompt": "Same as text_to_image_prompt",
      "duration_in_seconds": 5
    }}
  ]
}}

### FINAL REMINDERS:
- Return PURE JSON only (no markdown, no code blocks, no explanations)
- Extract ALL characters (look for 3+)
- Extract ALL scenes (look for 10+)
- Keep fields SEPARATE (don't mix image and video prompts)
- If a field is not found, use empty string ""
- Preserve original text exactly as written
"""
        try:
            text = await self._call_huggingface(prompt, max_tokens=16384)
            print(f"DEBUG: LLM Response (First 4000 chars):\n{text[:4000]}...")
            
            # Robust JSON extraction and cleaning
            import re
            
            # Step 1: Extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(1)
            else:
                # Look for first { and last } to extract JSON object
                first_brace = text.find('{')
                last_brace = text.rfind('}')
                if first_brace != -1 and last_brace > first_brace:
                    clean_text = text[first_brace:last_brace + 1]
                else:
                    clean_text = text
            
            # Step 2: Try direct parsing first
            try:
                data = json.loads(clean_text)
            except json.JSONDecodeError:
                # Step 3: Fix common issues using robust token strategy
                repaired = clean_text
                
                try:
                    # Strategy: Identify structural quotes, replace them with tokens, 
                    # escape remaining (internal) quotes, then restore tokens.
                    
                    # 1. Protect Key Ends: "key": -> __KEY_END__:
                    repaired = re.sub(r'"\s*:', '__KEY_END__:', repaired)
                    
                    # 2. Protect Key Starts: {"key" or ,"key" -> {__KEY_START__key
                    repaired = re.sub(r'(?<=[{,])\s*"', '__KEY_START__', repaired)
                    
                    # 3. Protect Value Starts: : "value" -> : __VAL_START__value
                    repaired = re.sub(r':\s*"', ':__VAL_START__', repaired)
                    
                    # 4. Protect Value Ends: "value", or "value"} or "value"] -> "value__VAL_END__,
                    # We capture the following delimiter to ensure we don't eat it
                    repaired = re.sub(r'"\s*([,}\]])', r'__VAL_END__\1', repaired)
                    
                    # 5. Now ALL remaining double quotes are internal/content quotes. Escape them!
                    repaired = repaired.replace('"', '\\"')
                    
                    # 6. Restore Tokens
                    repaired = repaired.replace('__KEY_END__', '"')
                    repaired = repaired.replace('__KEY_START__', '"')
                    repaired = repaired.replace('__VAL_START__', '"')
                    repaired = repaired.replace('__VAL_END__', '"')
                    
                    # 7. Additional cleanup: remove trailing commas
                    repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
                    
                    data = json.loads(repaired)
                    print("✅ JSON Repair successful with token strategy!")
                    
                except json.JSONDecodeError as e2:
                    print(f"DEBUG: JSON repair failed: {e2}")
                    print(f"DEBUG: Cleaned text: {repaired[:500]}...")
                    # Fallback: Try the simple regex method as a Hail Mary
                    try:
                        simple_repair = clean_text
                        for field in ["dialogue", "prompt", "text_to_image_prompt", "image_to_video_prompt", "scene_title", "name"]:
                            simple_repair = re.sub(
                                rf'("{field}":\s*")(.+?)("(?=\s*[,}}\n]))',
                                lambda m: '{}{}{}'.format(m.group(1), m.group(2).replace('"', '\\"'), m.group(3)),
                                simple_repair,
                                flags=re.DOTALL
                            )
                        data = json.loads(simple_repair)
                        print("✅ JSON Repair successful with simple fallback!")
                    except:
                        raise e2
            
            char_count = len(data.get('characters', []))
            scene_count = len(data.get('scenes', []))
            print(f"✅ LLM Extraction Successful! Found {char_count} characters and {scene_count} scenes.")
            
            if char_count == 0:
                print("⚠️ Warning: LLM found 0 characters. The script may need clearer character definitions.")
            if scene_count == 0:
                print("⚠️ Warning: LLM found 0 scenes. The script may need clearer scene markers.")
            
            # Clean up scene data - fix empty strings and set defaults
            for scene in data.get('scenes', []):
                # Fix duration_in_seconds: convert empty string or invalid to default 5
                duration = scene.get('duration_in_seconds', '')
                if isinstance(duration, str):
                    try:
                        scene['duration_in_seconds'] = int(duration) if duration else 5
                    except ValueError:
                        scene['duration_in_seconds'] = 5
                elif not isinstance(duration, int):
                    scene['duration_in_seconds'] = 5
                
                # Fix scene_number: ensure it's an int
                scene_num = scene.get('scene_number', 1)
                if isinstance(scene_num, str):
                    try:
                        scene['scene_number'] = int(scene_num) if scene_num else 1
                    except ValueError:
                        scene['scene_number'] = 1
                
                # Set any missing string fields to empty string
                for field in ['scene_title', 'text_to_image_prompt', 'image_to_video_prompt', 
                              'dialogue', 'camera_angle', 'voiceover_text', 'motion_description',
                              'background_description', 'character_pose_prompt']:
                    if field not in scene or scene[field] is None:
                        scene[field] = ''
                
            return TechnicalBreakdownOutput(**data)
        except Exception as e:
            print(f"❌ LLM Extraction Failed: {e}")
            # Return empty structure instead of brittle regex fallback
            raise ValueError(f"Failed to parse script with LLM: {e}. Please check your script format.")

    async def parse_manual_script_gemini(self, raw_text: str) -> TechnicalBreakdownOutput:
        """
        Extract structured data from a manual script using Gemini 2.0 Flash.
        Serves as a robust fallback to Hugging Face.
        """
        print("📝 Manual Extraction: Using Google Gemini 2.0 Flash...")
        
        prompt = f"""You are an expert script analyst. Extract structured data from this script into JSON.

SCRIPT:
---
{raw_text}
---

INSTRUCTIONS:
1. Extract ALL characters (Name + Visual Description).
2. Extract ALL scenes (Scene Number + Visuals + Audio).
3. Be precise with "Text-to-Image" vs "Text-to-Video" vs "Dialogue".
4. If a field is missing, use empty string "".

OUTPUT JSON FORMAT:
{{
  "characters": [
    {{ "name": "NAME", "prompt": "Visual description" }}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "text_to_image_prompt": "...",
      "image_to_video_prompt": "...",
      "dialogue": "...",
      "voiceover_text": "...",
      "camera_angle": "Medium Shot",
      "duration_in_seconds": 5
    }}
  ]
}}
"""
        try:
            text = await self._call_gemini(prompt)
            print(f"DEBUG: Gemini Response (First 200 chars): {text[:200]}...")
            
            clean_text = self._clean_json_text(text)
            data = json.loads(clean_text)
            
            # Post-processing (ensure ints, etc)
            for scene in data.get('scenes', []):
                 sec = scene.get('duration_in_seconds', 5)
                 scene['duration_in_seconds'] = int(sec) if isinstance(sec, (int, float)) else 5
                 
                 # Ensure all fields exist
                 for field in ['text_to_image_prompt', 'image_to_video_prompt', 'dialogue', 'character_pose_prompt']:
                     if field not in scene: scene[field] = ""

            return TechnicalBreakdownOutput(**data)

        except Exception as e:
            print(f"❌ Gemini Extraction Failed: {e}")
            raise ValueError(f"Gemini extraction failed: {e}")

    def parse_manual_script(self, raw_text: str) -> TechnicalBreakdownOutput:
        """
        Parse a manual script following the user's specific storyboard format.
        Supports 'PART 1', 'PART 2', 'PART 3' structure.
        """
        import re
        characters = []
        scenes = []
        
        print("📝 Parsing manual storyboard (Sequence Flow v6.0 - Robust)...")
        
        # 1. Normalize
        text = raw_text.replace('\r\n', '\n').strip()
        
        # --- 2. Extract Style Wrapper ---
        style_wrapper = ""
        # Look for PART 2 header or just "STYLE WRAPPER"
        # We capture everything until the next PART or SCENE start
        style_section_match = re.search(r'(?:PART 2:?\s*)?THE GLOBAL STYLE WRAPPER.*?(?=(?:PART 3|SCENE 1|MATCH END))', text + "MATCH END", re.DOTALL | re.IGNORECASE)
        
        if style_section_match:
            style_block = style_section_match.group(0)
            # functionality: Aggregating known style keys into one string
            style_components = []
            keys_to_extract = ["Artistic Influence", "Medium/Texture", "Color Palette", "Lighting/Environment", "Technical Keywords", "Base Style"]
            
            for line in style_block.split('\n'):
                for key in keys_to_extract:
                    if re.search(rf'{key}:', line, re.IGNORECASE):
                        # Extract value: "Key: Value" -> "Value"
                        val = line.split(':', 1)[1].strip()
                        if val:
                             style_components.append(val)
            
            # If we found specific components, join them. Otherwise try to grab the whole block content if simple.
            if style_components:
                style_wrapper = ", ".join(style_components)
            else:
                # Fallback: exact simplistic match
                m = re.search(r'Style Wrapper:\s*(.+)', style_block)
                if m: style_wrapper = m.group(1).strip()
            
            print(f"   🎨 Extracted Style Wrapper ({len(style_wrapper)} chars)")

        # --- 3. Extract Characters ---
        # Strategy: Try multiple known headers
        # 1. "THE CHARACTER BIOS" (Format 1)
        # 2. "CHARACTER MASTER PROMPTS" (Format 2)
        
        # Make regex extremely permissive for the header
        # Added: "Master Character Prompts" (without "Step 1" assumption, using loose match)
        char_section_match = re.search(r'(?:PART 1:?|Step \d+:?)?\s*(?:THE CHARACTER BIOS|CHARACTER MASTER PROMPTS?|MASTER CHARACTERS?|CHARACTER PROMPTS?).*?(?=(?:PART 2|Step \d+|THE GLOBAL STYLE WRAPPER|MATCH END|🎞️|SCENE))', text + "MATCH END", re.DOTALL | re.IGNORECASE)
        
        bio_text = ""
        if char_section_match:
            bio_text = char_section_match.group(0)
            print(f"DEBUG: Found Character Section via Header ({len(bio_text)} chars)")
        else:
             # Fallback: Everything before the first SCENE is potential character data
             print("DEBUG: Header regex failed. Using Fallback (Pre-Scene text).")
             # Find index of first scene
             scene_match = re.search(r'(?:🎞️)?\s*SCENE\s+\d+', text, re.IGNORECASE)
             if scene_match:
                 bio_text = text[:scene_match.start()]
                 print(f"DEBUG: Fallback Bio Text ({len(bio_text)} chars)")
             else:
                 # No scenes found? Use whole text
                 bio_text = text
        
        if bio_text:
             # Remove lines that might be headers to avoid false positives in names? 
             
            print(f"DEBUG: Processing Bio Text:\n{bio_text[:200]}...")
            
            # Format 3 (User Specific): [THE BOY] — Master Text-to-Image Prompt
            # Regex: explicit square brackets at start of line
            if "[" in bio_text and "]" in bio_text:
                print("DEBUG: Detecting Format 3 ([NAME])")
                # Pattern: [NAME] optional dash/text ... content ... until next [
                bracket_iter = re.finditer(r'(?:^|\n)\s*\[([A-Z0-9\s_\-]+)\](?:[^\n]*)(.*?)(?=(?:\n\s*\[|MATCH END|SCENE|$))', bio_text, re.DOTALL)
                
                found_any = False
                for m in bracket_iter:
                    name_raw = m.group(1).strip()
                    content = m.group(2).strip()
                    print(f"DEBUG: Found Bracket Char: {name_raw}")
                    
                    if name_raw and content:
                        characters.append(MasterCharacter(name=name_raw, prompt=content))
                        found_any = True
                
                if found_any:
                    # If we found characters this way, we might want to skip other formats to avoid duplicates?
                    # But sticking to append mode is safer for mixed formats unless it causes dupes.
                    # Given the input, this is likely the only format.
                    pass

            # Format 1: "Character 1: Name"
            if "Character 1:" in bio_text or "Character 1 :" in bio_text:
                print("DEBUG: Detecting Format 1 (Character X:)")
                char_iter = re.finditer(r'Character\s+\d+\s*:\s*([^\n]+)(.*?)(?=(?:Character\s+\d+:|$))', bio_text, re.DOTALL | re.IGNORECASE)
                for m in char_iter:
                    name_raw = m.group(1).strip()
                    content = m.group(2).strip()
                    simple_name = re.sub(r'\s*\(.*?\)', '', name_raw).strip()
                    
                    prompt_val = ""
                    bp_match = re.search(r'Base Prompt:\s*(.+)', content, re.IGNORECASE)
                    if bp_match:
                        prompt_val = bp_match.group(1).strip()
                    else:
                        phys = re.search(r'Physical Description:\s*(.+)', content, re.IGNORECASE)
                        ward = re.search(r'Wardrobe:\s*(.+)', content, re.IGNORECASE)
                        parts = []
                        if phys: parts.append(phys.group(1).strip())
                        if ward: parts.append(ward.group(1).strip())
                        prompt_val = ", ".join(parts)
                    
                    if simple_name and prompt_val:
                        characters.append(MasterCharacter(name=simple_name, prompt=prompt_val))

            # Format 2: "1. Name" with "Text-to-Image Prompt:"
            # Only try this if we haven't found much yet, or just try in parallel? 
            # "1." can false positive on "Step 1".
            if len(characters) == 0:
                print("DEBUG: Detecting Format 2 (Numbered List 1. Name)")
                # Regex: Number dot Name matches
                # Look for "1. Name" followed by content until next number or end
                fmt2_iter = re.finditer(r'(?:^|\n)\s*(\d+)\.\s+([^\n]+)(.*?)(?=(?:\n\s*\d+\.\s+|MATCH END|$))', bio_text, re.DOTALL)
                for m in fmt2_iter:
                    name = m.group(2).strip()
                    content = m.group(3).strip()
                    print(f"DEBUG: Potential Char Match: {name}")
                    
                    # Extract Prompt
                    t2i_match = re.search(r'(?:Text-to-Image Prompt|Text to Image Prompt|Prompt):\s*(.*?)(?=\n(?:Style|Style:|2\.|3\.|$))', content, re.DOTALL | re.IGNORECASE)
                    style_match = re.search(r'Style:\s*(.*?)(?=\n|$)', content, re.IGNORECASE)
                    
                    prompt_val = ""
                    if t2i_match:
                        prompt_val = t2i_match.group(1).strip()
                        # Append style if present
                        if style_match:
                            prompt_val += f", {style_match.group(1).strip()}"
                    else:
                        print(f"DEBUG: No Text-to-Image Prompt found for {name}")
                        # Fallback: take whole content if simple
                        if len(content) < 500 and "PROMPT" not in content.upper():
                             prompt_val = content.strip()
                    
                    if name and prompt_val:
                        characters.append(MasterCharacter(name=name, prompt=prompt_val))
                        print(f"   👤 Found Character (fmt2): {name}")
            
            # Format 4 (User Specific): "Name — Master Text-to-Image Prompt"
            if len(characters) == 0:
                print("DEBUG: Detecting Format 4 (Name — Master Text-to-Image Prompt)")
                # Pattern: Name followed by dash and "Master Text-to-Image Prompt"
                # Regex looks for line start, name, dash, specific phrase
                fmt4_iter = re.finditer(r'(?:^|\n)\s*(.+?)\s+[—–-]\s*Master Text-to-Image Prompt\s*\n(.*?)(?=(?:\n\s*.+?\s+[—–-]\s*Master Text-to-Image Prompt|MATCH END|SCENE|Step \d+|$))', bio_text, re.DOTALL | re.IGNORECASE)
                for m in fmt4_iter:
                    name = m.group(1).strip()
                    content = m.group(2).strip()
                    
                    # Clean up name if it contains "Step 1:" prefix
                    if ":" in name and "Step" in name:
                        name = name.split(":")[-1].strip()
                        
                    print(f"DEBUG: Found Character (fmt4): {name}")
                    if name and content:
                        characters.append(MasterCharacter(name=name, prompt=content))

            # Format 5 (User Specific): "NAME (Role) — Master Text-to-Image Prompt: Description"
            # This matches: OLIVER (The Cat) — Master Text-to-Image Prompt: Oliver is a sturdy...
            if len(characters) == 0:
                print("DEBUG: Detecting Format 5 (NAME (Role) — Master Text-to-Image Prompt:)")
                # Pattern matches: NAME (optional role) — Master Text-to-Image Prompt: content until next similar line or Scene
                fmt5_iter = re.finditer(
                    r'(?:^|\n)\s*([A-Z][A-Z0-9\s]+?)(?:\s*\([^)]+\))?\s*[—–-]\s*Master Text-to-Image Prompt:\s*(.*?)(?=(?:\n\s*[A-Z][A-Z0-9\s]+\s*(?:\([^)]+\))?\s*[—–-]\s*Master|Step\s+\d+|Scene\s+\d+|$))',
                    bio_text + "\n",
                    re.DOTALL | re.IGNORECASE
                )
                for m in fmt5_iter:
                    name = m.group(1).strip()
                    content = m.group(2).strip()
                    # Clean multi-line content into single para
                    content = re.sub(r'\n+', ' ', content).strip()
                    
                    print(f"DEBUG: Found Character (fmt5): {name}")
                    if name and content:
                        characters.append(MasterCharacter(name=name, prompt=content))
            
            # Format 7 (User's Simplified): "NAME (Role): Description"
            # Example: OLIVER (The Cat): A "Semi-Cobby" British Shorthair...
            if len(characters) == 0:
                print("DEBUG: Detecting Format 7 (NAME (Role): Description)")
                # Pattern matches: NAME (anything in parens): rest of content until next NAME ( or newline pattern
                fmt7_iter = re.finditer(
                    r'(?:^|\n)\s*([A-Z][A-Z\s]+?)\s*\(([^)]+)\)\s*:\s*(.*?)(?=\n\s*[A-Z][A-Z\s]+\s*\([^)]+\)\s*:|Step\s+\d+|Scene\s+\d+|\Z)',
                    bio_text + "\n",
                    re.DOTALL
                )
                for m in fmt7_iter:
                    name = m.group(1).strip()
                    role = m.group(2).strip()
                    content = m.group(3).strip()
                    # Clean multi-line content into single para
                    content = re.sub(r'\n+', ' ', content).strip()
                    
                    print(f"DEBUG: Found Character (fmt7): {name} ({role})")
                    if name and content:
                        characters.append(MasterCharacter(name=name, prompt=content))
                
                if characters:
                    print(f"✅ Format 7 found {len(characters)} characters")
            
            # Format 7b: "UPPERCASE NAME:" without parentheses (e.g., "THE WHISPERING GHOST:")
            # Only try if Format 7 didn't find all characters
            if len(characters) < 3:  # User typically has 2-3 characters
                print("DEBUG: Detecting Format 7b (UPPERCASE NAME: without role)")
                # Pattern: UPPERCASE NAME followed by colon, content until next uppercase name or section
                fmt7b_iter = re.finditer(
                    r'(?:^|\n)\s*([A-Z][A-Z\s]+?)\s*:\s*(?!\s*$)\n+(.*?)(?=\n\s*[A-Z][A-Z\s]+\s*[:(]|Step\s+\d+|Scene\s+\d+|\Z)',
                    bio_text + "\n",
                    re.DOTALL
                )
                existing_names = {c.name.upper() for c in characters}
                for m in fmt7b_iter:
                    name = m.group(1).strip()
                    content = m.group(2).strip()
                    # Skip if already found or if it's a section header (like "Step 1")
                    if name.upper() in existing_names:
                        continue
                    if re.match(r'^(STEP|SCENE|PART)\s*\d*$', name, re.IGNORECASE):
                        continue
                    # Clean multi-line content into single para
                    content = re.sub(r'\n+', ' ', content).strip()
                    
                    print(f"DEBUG: Found Character (fmt7b): {name}")
                    if name and content and len(content) > 20:  # Must have substantial content
                        characters.append(MasterCharacter(name=name, prompt=content))
                
                if len(characters) > 2:
                    print(f"✅ Format 7b added more characters, total: {len(characters)}")

            # Format 8 (Same-line simplified): "UPPERCASE NAME: Description on same line"
            # Example: MOCHI CAT: A small, perfectly round, ultra-white cat...
            if len(characters) == 0:
                print("DEBUG: Detecting Format 8 (UPPERCASE NAME: Same line description)")
                # Pattern: Starts with uppercase name + colon, takes everything until next uppercase name+colon or section
                fmt8_iter = re.finditer(
                    r'(?:^|\n)\s*([A-Z][A-Z\s]+?)\s*:\s*([^\n]+)(.*?)(?=\n\s*[A-Z][A-Z\s]+\s*:|Step\s+\d+|Scene\s+\d+|\Z)',
                    bio_text + "\n",
                    re.DOTALL
                )
                for m in fmt8_iter:
                    name = m.group(1).strip()
                    first_line = m.group(2).strip()
                    rest = m.group(3).strip()
                    content = (first_line + " " + rest).strip()
                    # Clean multi-line content into single para
                    content = re.sub(r'\n+', ' ', content).strip()
                    
                    # Skip noise
                    if name.upper() in ["SCENE", "STEP", "PART", "NOTE"]: continue
                    
                    print(f"DEBUG: Found Character (fmt8): {name}")
                    if name and content and len(content) > 15:
                        characters.append(MasterCharacter(name=name, prompt=content))
                
                if characters:
                    print(f"✅ Format 8 found {len(characters)} characters")
            
            # Format 6: Simpler detection - look for lines containing "Master Text-to-Image Prompt:" anywhere
            if len(characters) == 0:
                print("DEBUG: Detecting Format 6 (Fallback - any 'Master' pattern)")
                lines = bio_text.split('\n')
                current_name = None
                current_content = []
                
                for line in lines:
                    # Check if line starts a new character definition
                    if '—' in line or '–' in line or '-' in line:
                        if 'Master' in line and 'Prompt' in line:
                            # Save previous if exists
                            if current_name and current_content:
                                characters.append(MasterCharacter(name=current_name, prompt=' '.join(current_content)))
                            
                            # Extract name (everything before the dash)
                            parts = re.split(r'[—–-]', line, 1)
                            if len(parts) >= 2:
                                name_part = parts[0].strip()
                                # Remove (Role) suffix
                                name_part = re.sub(r'\s*\([^)]+\)\s*$', '', name_part).strip()
                                current_name = name_part.upper() if name_part else None
                                
                                # Content after "Prompt:"
                                content_part = parts[1]
                                if ':' in content_part:
                                    content_part = content_part.split(':', 1)[1].strip()
                                current_content = [content_part] if content_part else []
                        continue
                    
                    # If we have a current name, append content lines
                    if current_name and line.strip() and not line.strip().startswith('Step') and not line.strip().startswith('Scene'):
                        current_content.append(line.strip())
                
                # Don't forget the last character
                if current_name and current_content:
                    characters.append(MasterCharacter(name=current_name, prompt=' '.join(current_content)))
                
                if characters:
                    print(f"DEBUG: Format 6 found {len(characters)} characters")

        else:
            print("DEBUG: NO CHARACTER SECTION MATCHED")

        # --- 4. Extract Scenes ---
        # Split by "SCENE X" or "🎞️ SCENE X"
        # We replace the emoji to standard "SCENE" first for easier splitting
        clean_text_for_scenes = re.sub(r'🎞️\s*', '', text)
        
        # Split by "SCENE X" with optional indentation
        scene_blocks = re.split(r'(?i)\n+\s*SCENE\s+(\d+)', clean_text_for_scenes)
        
        found_scenes = 0
        
        if len(scene_blocks) > 1:
            for i in range(1, len(scene_blocks), 2):
                try:
                    s_num = int(scene_blocks[i])
                    block = scene_blocks[i+1]
                    
                    # Scene title is the first line (could be empty or just whitespace after Scene X)
                    lines = block.strip().split('\n')
                    raw_title = lines[0].strip() if lines else ""
                    scene_title = f"Scene {s_num}"  # Default title
                    if raw_title and not raw_title.lower().startswith("text to"):
                        scene_title = re.sub(r'^[:\–\-\.]\s*', '', raw_title).strip() or scene_title
                    
                    # --- FIELD EXTRACTION ---
                    # We use robust regex to find fields regardless of order or exact formatting
                    
                    # 1. Image Prompt
                    # Matches: "(Text-to-Image): ...", "Text-to-Image Prompt: ...", "Image Prompt: ..."
                    img_match = re.search(
                        r'(?:(?:\(|\[)?(?:Text-to-Image|Text to Image|Image Prompt)(?:\)|\])?(?:\s*Prompt)?\s*:)\s*(.*?)(?=(?:\n\s*(?:\(|\[)?(?:Image-to-Video|Text-to-Video|Sound|AI News|Dialog|Scene)|$))', 
                        block, re.DOTALL | re.IGNORECASE
                    )
                    img_prompt = img_match.group(1).strip() if img_match else ""

                    # 2. Video/Motion Prompt
                    # Matches: "(Image-to-Video): ...", "Text-to-Video Prompt: ...", "Video Prompt: ..."
                    vid_match = re.search(
                        r'(?:(?:\(|\[)?(?:Image-to-Video|Text-to-Video|Text to Video|Video Prompt)(?:\)|\])?(?:\s*Prompt)?\s*:)\s*(.*?)(?=(?:\n\s*(?:\(|\[)?(?:Text-to-Image|Sound|AI News|Dialog|Scene)|$))', 
                        block, re.DOTALL | re.IGNORECASE
                    )
                    vid_prompt = vid_match.group(1).strip() if vid_match else ""

                    # 3. Dialogue / AI News Line
                    # Matches: "AI News Line:", "Dialog:", "Dialogue:", "Voiceover:"
                    # Handles multi-line values until the next keyword or end of block
                    dial_match = re.search(
                        r'(?:(?:AI News Line|Dialog|Dialogue|Voiceover|Audio)(?:\s*Line)?\s*:)\s*(.*?)(?=(?:\n\s*(?:\(|\[)?(?:Text-to-Image|Image-to-Video|Sound|Scene)|$))', 
                        block, re.DOTALL | re.IGNORECASE
                    )
                    dialogue_raw = dial_match.group(1).strip() if dial_match else ""
                    
                    # 4. Sound Effect (Optional, append to cues if needed)
                    sfx_match = re.search(
                        r'(?:Sound Effect|SFX|Audio Cue)\s*:\s*(.*?)(?=(?:\n\s*(?:\(|\[)?(?:Text-to-Image|Image-to-Video|AI News|Dialog|Scene|Emotion)|$))',
                        block, re.DOTALL | re.IGNORECASE
                    )
                    sfx = sfx_match.group(1).strip() if sfx_match else ""

                    # 5. Emotion (Optional)
                    emo_match = re.search(
                        r'(?:Emotion|Mood|Feeling)\s*:\s*(.*?)(?=(?:\n\s*(?:\(|\[)?(?:Text-to-Image|Image-to-Video|AI News|Dialog|Scene|Sound)|$))',
                        block, re.DOTALL | re.IGNORECASE
                    )
                    emotion = emo_match.group(1).strip() if emo_match else "neutrally"

                    # Clean dialogue (remove quotes)
                    clean_audio = dialogue_raw.strip('"').strip("'").strip()
                    if sfx and not clean_audio:
                         # If no dialog but SFX exists, maybe use SFX as audio cue? 
                         # Usually we only want spoken audio in 'voiceover_text'
                         pass

                    # Shot Type Inference
                    shot_type = "Medium Shot"
                    if "close-up" in img_prompt.lower(): shot_type = "Close-up"
                    elif "wide" in img_prompt.lower(): shot_type = "Wide Shot"
                    elif "extreme close" in img_prompt.lower(): shot_type = "Extreme Close-up"
                    
                    print(f"   📦 Scene {s_num}: {scene_title[:30]}...")
                    print(f"      📷 Text-to-Image: {img_prompt[:60]}...")
                    print(f"      🎬 Text-to-Video: {vid_prompt[:60]}...")
                    print(f"      🎤 Dialog/News: {clean_audio[:40]}...")
                    print(f"      🔊 SFX: {sfx[:40]}...")
                    print(f"      😊 Emotion: {emotion[:40]}...")
                    
                    scenes.append(SceneBreakdown(
                        scene_number=s_num,
                        scene_title=scene_title,
                        voiceover_text=clean_audio if "(SFX" not in dialogue_raw else "",
                        character_pose_prompt=img_prompt[:1000], 
                        text_to_image_prompt=img_prompt,
                        image_to_video_prompt=vid_prompt,
                        motion_description=vid_prompt,
                        background_description=img_prompt,
                        camera_angle=shot_type,
                        dialogue=clean_audio if "(SFX" not in dialogue_raw else None,
                        sound_effect=sfx,
                        emotion=emotion,
                        duration_in_seconds=5
                    ))
                    found_scenes += 1
                except Exception as ex:
                    print(f"   ⚠️ Error parsing scene {i}: {ex}")

        if found_scenes == 0:
             print("❌ Failed to parse any scenes manually. Check format.")
        else:
             print(f"✅ Extracted {found_scenes} scenes.")

        return TechnicalBreakdownOutput(characters=characters, scenes=scenes)

    async def generate_viral_thumbnail_prompt(self, script_context: str) -> str:
        """
        Generate a high-converting, viral YouTube thumbnail prompt style-aligned with Pixar/Disney 3D.
        """
        print("🎨 Generating VIRAL thumbnail prompt...")
        
        prompt = f"""Act as a YouTube Thumbnails Expert and 3D Art Director.
        
        CONTEXT:
        {script_context[:2000]}...
        
        TASK:
        Create a SINGLE, detailed text-to-image prompt for a viral YouTube thumbnail.
        
        STYLE:
        High-quality Pixar/Disney 3D animation style. Vibrant colors, expressive faces, high contrast.
        
        REQUIREMENTS:
        1. Main Subject: The most interesting character or element from the story.
        2. Action: High energy, shock, or intense emotion (e.g. wide eyes, mouth open, running).
        3. Composition: Rule of thirds, depth of field, 8k resolution.
        4. Lighting: Cinematic lighting, rim lighting, volumetric fog.
        5. Background: Detailed but slightly blurred to make subject pop.
        
        OUTPUT FORMAT:
        Return ONLY the raw prompt string. No "Here is the prompt" or quotes.
        
        Example Output:
        A cute 3D animated cat with wide eyes looking terrified at a glowing magical sword, Pixar style, 8k resolution, vibrant orange and teal lighting, volumetric fog, cinematic composition.
        """
        
        try:
            # Use HF LLM to generate the prompt
            thumbnail_prompt = await self._call_huggingface(prompt, max_tokens=200)
            
            # clean up
            thumbnail_prompt = thumbnail_prompt.strip().replace('"', '')
            if ":" in thumbnail_prompt and len(thumbnail_prompt.split(":")[0]) < 20: 
                # Remove "Prompt:" prefix if present
                thumbnail_prompt = thumbnail_prompt.split(":", 1)[1].strip()
                
            print(f"   ✅ Thumbnail Prompt: {thumbnail_prompt[:50]}...")
            return thumbnail_prompt
            
        except Exception as e:
            print(f"   ❌ Failed to generate thumbnail prompt: {e}")
            return "A high quality 3D render of the main character, Pixar style, vibrant lighting, 8k resolution, cinematic composition."

    async def generate_viral_metadata(self, script_context: str) -> dict:
        """
        Generate viral Title, Description, and Tags using LLM.
        """
        print("📈 Generating viral metadata...")
        
        prompt = f"""Act as a Viral YouTube Strategist (MrBeast style).
        
        CONTEXT:
        {script_context[:3000]}...
        
        TASK:
        Generate the metadata to MAXIMIZE click-through rate (CTR).
        
        1. TITLE: Under 60 chars. Shocking, curiosity gap, or high stakes. NO CLICKBAIT that lies.
        2. DESCRIPTION: 3 lines. First line is the hook. Include keywords.
        3. TAGS: 15 high-volume keywords.
        
        OUTPUT FORMAT (Strict JSON):
        {{
            "title": "...",
            "description": "...",
            "tags": ["tag1", "tag2", ...]
        }}
        """
        
        try:
            json_text = await self._call_huggingface(prompt, max_tokens=500)
            cleaned_json = self._clean_json_text(json_text)
            metadata = json.loads(cleaned_json)
            
            print(f"   ✅ Title: {metadata.get('title')}")
            return metadata
            
        except Exception as e:
            print(f"   ❌ Failed to generate metadata: {e}")
            return {
                "title": "Amazing AI Generated Story",
                "description": "Watch this incredible story generated by AI Video Factory.",
                "tags": ["AI", "Animation", "Story"]
            }

    async def rewrite_moderated_prompt(self, original_prompt: str) -> str:
        """
        Rewrite a prompt that was flagged by Grok's moderation.
        Uses clinical, safe language to avoid content filters.
        """
        print(f"🔄 Rewriting moderated prompt...")
        
        system_prompt = """You are a content safety expert. Rewrite the user's video generation prompt to avoid content moderation filters.

RULES:
- Keep the SAME creative intent and scene description
- Replace any potentially flagged words with safe clinical alternatives
- Avoid words like: violent, blood, weapon, fight, kill, dead, horror, scary, sexy, nude, drug, gun, knife, war, attack, destroy, explode, crash, burn, scream, pain, suffer, abuse, hate
- Use words like: active, energetic, dynamic, determined, coordinated, focused, moving, traveling, resting, standing, walking, running, jumping, celebrating
- Keep it under 200 words
- Output ONLY the rewritten prompt, nothing else"""

        try:
            rewritten = await self._call_huggingface(
                f"{system_prompt}\n\nOriginal prompt:\n{original_prompt}",
                max_tokens=300,
                timeout=30.0
            )
            rewritten = rewritten.strip()
            if rewritten and len(rewritten) > 20:
                print(f"   ✅ Rewritten (via HF): {rewritten[:80]}...")
                return rewritten
        except Exception as hf_err:
            print(f"   ⚠️ HuggingFace rewrite failed ({hf_err}). Falling back to Gemini...")
            try:
                # FALLBACK TO GEMINI
                gemini_prompt = f"{system_prompt}\n\nOriginal prompt:\n{original_prompt}"
                rewritten = await self._call_gemini(gemini_prompt)
                rewritten = rewritten.strip()
                if rewritten and len(rewritten) > 10:
                    print(f"   ✅ Rewritten (via Gemini): {rewritten[:80]}...")
                    return rewritten
            except Exception as gem_err:
                print(f"   ❌ Gemini rewrite also failed: {gem_err}")
        
        return original_prompt  # Return original if all rewrites fail
