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

Generate exactly {scene_count} scenes adhering to the structure above.
"""

    async def _call_llm(self, prompt: str, gemini_model: str = "gemini-flash-latest", json_mode: bool = False) -> str:
        """LLM CALLS DISABLED BY USER REQUEST"""
        print("\n LLM INTEGRATION IS CURRENTLY DISABLED (COMMENTED OUT)")
        raise ValueError("AI generation is disabled. Please use 'Manual Script' mode.")

    # [COMMENTED OUT] async def _call_gemini(self, prompt: str, ...
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

    async def parse_manual_script_llm(self, raw_text: str) -> TechnicalBreakdownOutput:
        """
        Extract structured data from a manual script using LLM.
        """
        print("📝 Manual Extraction: Using Hugging Face LLM (Qwen-2.5-7B)...")
        
        prompt = f"""You are a master template-agnostic data extraction expert.
        
TASK:
Analyze the provided unstructured MOVIE SCRIPT/STORYBOARD and extract structured data.
The input format is variable. It often contains a **"Master Character Prompts"** section with headers like `[NAME]`, but sometimes character details are embedded in scenes.

INPUT SCRIPT:
{raw_text}

REQUIREMENTS:
1. **CHARACTERS**: Extract TWO (2) Main Characters.
   - **Strong Priority**: Look for headers like `[THE BOY]`, `[NAME]`, `1. Name`, `Character 1:`, or `Name — Master Text-to-Image Prompt`.
   - Use the text following these headers as their `prompt`.
   - If NO such headers exist, INFER them from the scenes.

2. **MUSIC MOOD**: Select ONE mood for the entire video from this list:
   [dramatic, cinematic, calm, horror, adventurous, cute, travel, beauty, suspense, hiphop, rock, piano, sorrow, epic, jazz]
   - Base selection on the overall tone of the script.

3. **SCENES**: Extract ALL Scenes containing:
   - **text_to_image_prompt**: Combine "Visual", "Text-to-Image", "What is happening", "Setting", and "Style".
   - **image_to_video_prompt**: Combine "Animation", "Video Prompt", "Motion", or "Action".
   - **voiceover_text**: Extract from "Dialogue", "Voiceover" or "Audio". 
   - **dialogue**: SAME as voiceover_text.
   - **scene_title**: Extract from "Scene 1 — Title" or similar.

OUTPUT FORMAT (JSON ONLY):
{{
  "characters": [
    {{ "name": "Name", "prompt": "Visual Description" }}
  ],
  "music_mood": "epic",
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "Title",
      "voiceover_text": "Narration...",
      "character_pose_prompt": "Visual...", 
      "text_to_image_prompt": "Combined Visual Description...",
      "image_to_video_prompt": "Combined Motion Description...",
      "motion_description": "Motion...",
      "duration_in_seconds": 5,
      "camera_angle": "Medium Shot",
      "dialogue": "Speech..."
    }}
  ]
}}

IMPORTANT:
- Return ONLY valid JSON.
- If a field is missing, use empty string or null.
- **text_to_image_prompt** MUST be detailed.
"""
        try:
            text = await self._call_huggingface(prompt, max_tokens=16384)
            print(f"DEBUG: LLM Response (First 500 chars):\n{text[:500]}...") # Added debug
            clean_text = self._clean_json_text(text)
            data = json.loads(clean_text)
            print(f"✅ LLM Extraction Successful! Found {len(data.get('scenes', []))} scenes.")
            return TechnicalBreakdownOutput(**data)
        except Exception as e:
            print(f"❌ LLM Extraction Failed: {e}")
            print("⚠️ Falling back to Regex Parser...")
            return self.parse_manual_script(raw_text)

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
        char_section_match = re.search(r'(?:PART 1:?|Step \d+:?)?\s*(?:THE CHARACTER BIOS|CHARACTER MASTER PROMPTS?|MASTER CHARACTERS?).*?(?=(?:PART 2|Step \d+|THE GLOBAL STYLE WRAPPER|MATCH END|🎞️|SCENE))', text + "MATCH END", re.DOTALL | re.IGNORECASE)
        
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

        else:
            print("DEBUG: NO CHARACTER SECTION MATCHED")

        # --- 4. Extract Scenes ---
        # Split by "SCENE X" or "🎞️ SCENE X"
        # We replace the emoji to standard "SCENE" first for easier splitting
        clean_text_for_scenes = re.sub(r'🎞️\s*', '', text)
        
        # Split by "SCENE X"
        scene_blocks = re.split(r'(?i)\n+SCENE\s+(\d+)', clean_text_for_scenes)
        
        found_scenes = 0
        
        if len(scene_blocks) > 1:
            for i in range(1, len(scene_blocks), 2):
                try:
                    s_num = int(scene_blocks[i])
                    block = scene_blocks[i+1]
                    
                    lines = block.strip().split('\n')
                    raw_title = lines[0].strip()
                    scene_title = re.sub(r'^[:\–\-\.]\s*', '', raw_title)
                    
                    def extract(keys: list, text_block: str) -> str:
                        for k in keys:
                            # Robust Match: Key: Value ... (until next key or double newline)
                            pattern = rf'(?i){k}\s*[:]\s*(.*?)(?=\n+(?:Shot|Text-to-Image|Image-to-Video|Dialogue|Audio|Style)|$)'
                            m = re.search(pattern, text_block, re.DOTALL)
                            if m: return m.group(1).strip()
                        return ""

                    # Mapping
                    shot = extract(["Shot Type", "Shot"], block)
                    img_prompt = extract(["Text-to-Image Prompt", "Image Prompt", "Visual"], block)
                    vid_prompt = extract(["Image-to-Video Prompt", "Video Prompt", "Animation"], block)
                    
                    # Audio / Dialogue
                    audio_raw = extract(["Dialogue", "Dialogue \\(Narrator\\)", "Dialogue \\(.*\\)", "Audio \\(VO\\)", "Audio \\(SFX\\)", "Audio", "VO", "Voiceover"], block)
                    
                    # Per-Scene Style
                    style_local = extract(["Style"], block)
                    
                    # Merge Style into Prompt
                    if style_local:
                        img_prompt = f"{img_prompt}, {style_local}"
                    elif style_wrapper:
                         if "[Style Wrapper]" in img_prompt:
                            img_prompt = img_prompt.replace("[Style Wrapper]", style_wrapper)
                         else:
                            # If no local style and no placeholder, maybe append global?
                            # For now, let's just respect local style overrides.
                            pass

                    # Dialogue Cleanup
                    clean_audio = audio_raw.strip('"').strip('“').strip('”')
                    
                    # Construct Pose
                    final_pose = f"{shot}, {img_prompt}" 
                    
                    scenes.append(SceneBreakdown(
                        scene_number=s_num,
                        scene_title=scene_title,
                        voiceover_text=clean_audio if "(SFX" not in audio_raw else "",
                        character_pose_prompt=final_pose[:1000], 
                        text_to_image_prompt=img_prompt,
                        image_to_video_prompt=vid_prompt,
                        motion_description=vid_prompt,
                        background_description=img_prompt,
                        camera_angle=shot,
                        dialogue=clean_audio if "(SFX" not in audio_raw else None,
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
