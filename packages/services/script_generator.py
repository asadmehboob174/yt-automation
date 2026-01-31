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
    camera_angle: str = "medium shot"
    dialogue: Optional[str] = None
    imageUrl: Optional[str] = None
    videoUrl: Optional[str] = None


class TechnicalBreakdownOutput(BaseModel):
    """Output schema for technical breakdown (characters + scenes)."""
    characters: list[MasterCharacter]
    scenes: list[SceneBreakdown]


class ScriptGenerator:
    """Generate video scripts using HuggingFace Inference API (Mistral-7B)."""
    
    # Gemini API (commented out - rate limited)
    # GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
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
            raise ValueError("HF_TOKEN environment variable is required")
        
        # Rate limiter: HuggingFace free tier has 300 req/hour
        self._call_semaphore = asyncio.Semaphore(1)  # One call at a time
        self._last_call_time = 0
        self._min_interval = 2.0  # 2 seconds between calls (more generous than Gemini)
    
    def _build_prompt(self, topic: str, niche_style: str, scene_count: int = 10) -> str:
        """Build the prompt for Gemini."""
        return f"""You are a professional video scriptwriter. Generate a video script about: "{topic}"

Style: {niche_style}

Generate exactly {scene_count} scenes. For each scene, provide:
1. voiceover_text: The narration (2-3 sentences, engaging, hook-focused for first scene)
2. character_pose_prompt: Detailed character appearance and pose description
3. background_description: Setting and environment details
4. duration_in_seconds: 8-12 seconds per scene
5. camera_angle: "close up", "medium shot", "wide shot", or "extreme close up"
6. motion_description: What movement happens in the scene
7. dialogue: Optional spoken dialogue (if character speaks)
8. character_name: Name of speaking character
9. emotion: How they speak (e.g., "excitedly", "nervously", "calmly")

IMPORTANT: The first scene must be a strong hook (15-20 seconds) that grabs attention immediately.

Return ONLY valid JSON in this exact format:
{{
  "title": "Video Title",
  "description": "YouTube description (2-3 sentences)",
  "scenes": [
    {{
      "voiceover_text": "...",
      "character_pose_prompt": "...",
      "background_description": "...",
      "duration_in_seconds": 10,
      "camera_angle": "medium shot",
      "motion_description": "...",
      "dialogue": null,
      "character_name": "Character",
      "emotion": "neutrally"
    }}
  ]
}}"""

    async def _call_gemini(self, prompt: str, model: str = "gemini-flash-latest", retries: int = 8) -> str:
        """Call Gemini API via HTTP with retry logic for 429 errors."""
        # Log key debug (masked)
        masked_key = f"{self.gemini_key[:4]}...{self.gemini_key[-4:]}" if self.gemini_key else "None"
        print(f"🔑 Using Gemini API Key: {masked_key} | Model: {model}")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192
            }
        }
        
        import random
        
        async with httpx.AsyncClient() as client:
            for attempt in range(retries):
                try:
                    response = await client.post(url, json=payload, timeout=60.0)
                    
                    if response.status_code == 429:
                        # More aggressive backoff: 5, 10, 20, 40...
                        wait_time = (5 * (2 ** (attempt))) + random.uniform(1, 5)
                        print(f"⚠️ Gemini Rate Limit (429). Waiting {wait_time:.1f}s (Attempt {attempt+1}/{retries})...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    response.raise_for_status()
                    result = response.json()
                    
                    if "candidates" in result and result["candidates"]:
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            content = candidate["content"]["parts"][0]["text"]
                            print(f"DEBUG: Gemini raw content length: {len(content)}")
                            return content
                        else:
                            print(f"⚠️ Gemini candidate missing content: {candidate}")
                            # Check for safety ratings
                            if "finishReason" in candidate:
                                print(f"⚠️ Finish Reason: {candidate['finishReason']}")
                    else:
                        print(f"⚠️ Unexpected Gemini response: {result}")
                        raise ValueError(f"Unexpected Gemini response: {result}")
                        
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < retries - 1:
                        # Should be handled by the if block above, but double check
                        continue
                    print(f"❌ Gemini API Error: {e}")
                    raise
                except Exception as e:
                    if attempt < retries - 1:
                        print(f"⚠️ Gemini request failed: {e}. Retrying...")
                        await asyncio.sleep(2)
                        continue
                    print(f"❌ Gemini API Failed after {retries} attempts: {e}")
                    raise
        return ""

    async def _call_huggingface(self, prompt: str, max_tokens: int = 4096, timeout: float = 120.0, retries: int = 5) -> str:
        """Call HuggingFace Inference API (OpenAI-compatible) with retry logic."""
        import random
        import time
        
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json"
        }
        
        # Use OpenAI-compatible chat completion format
        payload = {
            "model": self.HF_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.95
        }
        
        print(f"🚀 Calling HF API with model: {self.HF_MODEL}...")
        
        async with self._call_semaphore:
            # Enforce minimum interval between calls
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self._min_interval:
                wait = self._min_interval - elapsed
                print(f"⏱️ Rate limiting: waiting {wait:.1f}s...")
                await asyncio.sleep(wait)
            
            last_exception = None
            for attempt in range(retries):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            self.HF_API, 
                            headers=headers,
                            json=payload, 
                            timeout=timeout
                        )
                        self._last_call_time = time.time()
                        
                        # Handle model loading (503)
                        if response.status_code == 503:
                            data = response.json()
                            wait_time = data.get("estimated_time", 20)
                            print(f"⏳ Model loading... waiting {wait_time:.0f}s")
                            await asyncio.sleep(wait_time)
                            continue
                        
                        if response.status_code == 429:
                            base_wait = 2 ** attempt
                            jitter = random.uniform(0, 2)
                            wait = base_wait + jitter
                            print(f"⚠️ Rate limit hit. Waiting {wait:.1f}s (attempt {attempt+1}/{retries})...")
                            await asyncio.sleep(wait)
                            continue
                        
                        # Log error details
                        if response.status_code >= 400:
                            print(f"⚠️ HuggingFace API Error {response.status_code}:")
                            print(f"   Response: {response.text[:300]}")
                            
                        response.raise_for_status()
                        result = response.json()
                        
                        # Parse OpenAI-compatible response format
                        if "choices" in result and len(result["choices"]) > 0:
                            return result["choices"][0]["message"]["content"]
                        # Fallback for other formats
                        elif isinstance(result, list) and len(result) > 0:
                            return result[0].get("generated_text", "")
                        elif isinstance(result, dict):
                            return result.get("generated_text", str(result))
                        return str(result)
                        
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in [429, 503]:
                        last_exception = e
                        continue
                    raise
                except Exception as e:
                    print(f"⚠️ Error (Attempt {attempt+1}/{retries}): {e}")
                    last_exception = e
                    if attempt < retries - 1:
                        await asyncio.sleep(2)
            
            raise last_exception or Exception("HuggingFace API failed after all retries")

    async def generate(
        self,
        topic: str,
        niche_style: str,
        scene_count: int = 10
    ) -> VideoScriptOutput:
        """Generate a video script for the given topic."""
        prompt = self._build_prompt(topic, niche_style, scene_count)
        
        text = await self._call_huggingface(prompt)
        
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
        prompt = f"""You are a professional storyteller and screenwriter. Create a detailed, engaging story based on this idea:

STORY IDEA: "{story_idea}"

TARGET LENGTH: This story will be adapted into a {scene_count}-scene animated short film with exactly 2 MAIN CHARACTERS.
STYLE: {style}
(FOR TESTING: Ensure exactly {scene_count} scenes and exactly 2 characters)

Write the story as flowing paragraphs (NOT a scene breakdown yet). Include:
- Character introductions with personality traits
- Setting descriptions
- Plot progression with conflict and resolution
- Emotional beats and character development
- A satisfying ending

The story should be engaging, family-friendly, and visually descriptive.
Write approximately {scene_count * 2} to {scene_count * 3} paragraphs.

Output ONLY the story narrative, no headers or metadata."""

        # text = await self._call_huggingface(
        #     prompt,
        #     max_tokens=8192,
        #     timeout=90.0,
        #     retries=5
        # )
        text = await self._call_gemini(prompt)
        return text.strip()

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
        if not text.endswith("}") and "}" in text:
            text = text[:text.rfind("}")+1]
        
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
        
        # Step 5: Fix literal newlines inside JSON strings
        def escape_newlines(match):
            content = match.group(2)
            fixed = content.replace('\n', '\\n').replace('\r', '\\n').replace('\t', '\\t')
            return f'{match.group(1)}{fixed}{match.group(3)}'
        
        for field in ["name", "prompt", "text_to_image_prompt", "image_to_video_prompt", 
                      "dialogue", "scene_title", "voiceover_text", "character_pose_prompt",
                      "background_description", "motion_description", "duration_in_seconds", "camera_angle"]:
            text = re.sub(
                rf'("{field}":\s*")(.+?)("(?=\s*[,}}\n]))',
                escape_newlines,
                text,
                flags=re.DOTALL
            )
        
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
        prompt = f"""You are an expert storyboard artist and 3D animation director. Analyze this story and create a complete production package:

STORY:
{story_narrative}

STYLE: {style}
TARGET SCENES: {scene_count}
(FOR TESTING: Generate exactly {scene_count} scenes and exactly 2 master characters)

Create a structured breakdown with:

1. MASTER CHARACTER PROMPTS: For EXACTLY 2 main characters, write a detailed Text-to-Image prompt that establishes their visual appearance. Include:
   - Physical features (age, hair, eyes, build)
   - Clothing and accessories
   - Expression and personality cues
   - Art style consistency notes

2. SCENE BREAKDOWN: For each of the {scene_count} scenes, provide:
   - scene_title: Brief title (e.g., "The Discovery")
   - voiceover_text: Narration/Script for this scene (2-3 sentences max).
   - text_to_image_prompt: FULL detailed description for image generation.
   - character_pose_prompt: Focussed description of character pose/action for consistency.
   - background_description: Setting details.
   - image_to_video_prompt: Dynamic movement description.
   - motion_description: Concise motion instruction (e.g. "Pan right", "Character waves").
   - duration_in_seconds: 5-10
   - camera_angle: "wide shot", "close up", etc.
   - dialogue: Character speech with emotion cues, format: '[CHARACTER_NAME]: (emotion) "Speech"'. Use null if no dialogue.

CRITICAL: 
- Use varied camera angles (Low angle, High angle, Close-up, Wide shot) for cinematic feel
- First scene must be a strong hook
- Reference characters by bracketed names like [THE BOY], [THE DRAGON]
- DO NOT use extra quotes in your output - each string value should have exactly ONE opening quote and ONE closing quote

Return ONLY valid JSON in this exact format:
{{
  "characters": [
    {{
      "name": "THE BOY",
      "prompt": "A high-quality Pixar-style 3D render of [THE BOY], a 10-year-old..."
    }}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "The Discovery",
      "voiceover_text": "In the heart of the ancient forest, a boy stumbled upon a secret...",
      "text_to_image_prompt": "A wide, low-angle landscape shot at twilight. [THE BOY] is crouched...",
      "character_pose_prompt": "[THE BOY] is crouched examining a glowing object...",
      "background_description": "Ancient forest with bioluminescent plants at twilight...",
      "image_to_video_prompt": "[THE BOY] hesitates, looking around nervously. He slowly reaches out...",
      "motion_description": "[THE BOY] reaches out slowly...",
      "duration_in_seconds": 10,
      "camera_angle": "wide shot",
      "dialogue": "[THE BOY]: (whispering) What is this?"
    }}
  ]
}}
IMPORTANT: 
- Use SINGLE QUOTES (') for dialogue or internal quotes. DO NOT use unescaped double quotes (") inside JSON string values.
- Ensure the JSON is valid and strictly follows the schema.
- The output must be ONLY the JSON object.
- Each JSON string value must have EXACTLY ONE opening " and EXACTLY ONE closing "
"""

        # text = await self._call_huggingface(
        #     prompt,
        #     max_tokens=16384,
        #     timeout=120.0,
        #     retries=5
        # )
        text = await self._call_gemini(prompt)
        
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