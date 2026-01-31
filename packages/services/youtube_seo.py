"""
YouTube SEO & Thumbnail Engine.

Generates optimized thumbnails, titles, and descriptions
for maximum YouTube engagement and discoverability.
"""
import os
import re
import random
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)


# ============================================
# Data Classes
# ============================================
@dataclass
class ThumbnailConfig:
    """Configuration for thumbnail generation."""
    width: int = 1280
    height: int = 720
    text_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 4
    font_size: int = 72
    font_path: Optional[str] = None
    overlay_opacity: float = 0.3


@dataclass
class SEOResult:
    """Result of SEO optimization."""
    title: str
    description: str
    tags: list[str]
    thumbnail_path: Optional[Path] = None


# ============================================
# Thumbnail Generator
# ============================================
class ThumbnailGenerator:
    """
    Generate click-optimized thumbnails using PIL.
    
    Features:
    - Template-based composition
    - Face detection for optimal placement
    - High-contrast text overlays
    - Emoji and icon support
    """
    
    def __init__(self, config: ThumbnailConfig = None):
        self.config = config or ThumbnailConfig()
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts for text rendering."""
        # Try to find a bold font
        font_paths = [
            # Windows
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/impact.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            # Mac
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        
        if self.config.font_path:
            font_paths.insert(0, self.config.font_path)
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    self.font = ImageFont.truetype(path, self.config.font_size)
                    self.small_font = ImageFont.truetype(path, int(self.config.font_size * 0.6))
                    logger.info(f"📝 Loaded font: {path}")
                    return
                except Exception:
                    continue
        
        # Fallback to default
        self.font = ImageFont.load_default()
        self.small_font = ImageFont.load_default()
        logger.warning("⚠️ Using default font")
    
    def generate(
        self,
        background_image: Path,
        title_text: str,
        character_image: Optional[Path] = None,
        emoji: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Generate a thumbnail with all optimizations.
        
        Args:
            background_image: Scene image for background
            title_text: Main text (keep short!)
            character_image: Optional character face to overlay
            emoji: Optional emoji to add
            output_path: Save location
            
        Returns:
            Path to generated thumbnail
        """
        # Load and resize background
        bg = Image.open(background_image).convert("RGBA")
        bg = bg.resize((self.config.width, self.config.height), Image.LANCZOS)
        
        # Apply slight blur and darkening for better text contrast
        bg = bg.filter(ImageFilter.GaussianBlur(radius=2))
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.7)
        
        # Add dark overlay
        overlay = Image.new("RGBA", bg.size, (0, 0, 0, int(255 * self.config.overlay_opacity)))
        bg = Image.alpha_composite(bg, overlay)
        
        # Add character image if provided
        if character_image and Path(character_image).exists():
            bg = self._add_character(bg, character_image)
        
        # Add text
        bg = self._add_text(bg, title_text, emoji)
        
        # Convert to RGB for saving as JPEG
        bg = bg.convert("RGB")
        
        # Save
        if output_path is None:
            output_path = Path(f"/tmp/thumbnail_{hash(title_text)}.jpg")
        
        bg.save(str(output_path), "JPEG", quality=95)
        logger.info(f"🖼️ Generated thumbnail: {output_path}")
        
        return output_path
    
    def _add_character(self, bg: Image.Image, character_path: Path) -> Image.Image:
        """Add character image on the right side."""
        char_img = Image.open(character_path).convert("RGBA")
        
        # Resize character to fit right side (40% of width)
        char_width = int(self.config.width * 0.4)
        char_height = int(char_img.height * (char_width / char_img.width))
        
        # Cap height at thumbnail height
        if char_height > self.config.height:
            char_height = self.config.height
            char_width = int(char_img.width * (char_height / char_img.height))
        
        char_img = char_img.resize((char_width, char_height), Image.LANCZOS)
        
        # Position on right side, vertically centered
        x = self.config.width - char_width - 20
        y = (self.config.height - char_height) // 2
        
        bg.paste(char_img, (x, y), char_img)
        return bg
    
    def _add_text(self, bg: Image.Image, text: str, emoji: Optional[str] = None) -> Image.Image:
        """Add title text with stroke effect."""
        draw = ImageDraw.Draw(bg)
        
        # Add emoji prefix if provided
        if emoji:
            text = f"{emoji} {text}"
        
        # Wrap text if too long
        wrapped = self._wrap_text(text, max_chars=20)
        
        # Calculate text position (left side, vertically centered)
        text_x = 50
        
        # Calculate total text height
        lines = wrapped.split('\n')
        line_height = self.config.font_size + 10
        total_height = len(lines) * line_height
        text_y = (self.config.height - total_height) // 2
        
        # Draw each line with stroke
        for i, line in enumerate(lines):
            y = text_y + (i * line_height)
            
            # Draw stroke (outline)
            for dx in range(-self.config.stroke_width, self.config.stroke_width + 1):
                for dy in range(-self.config.stroke_width, self.config.stroke_width + 1):
                    draw.text(
                        (text_x + dx, y + dy),
                        line,
                        font=self.font,
                        fill=self.config.stroke_color
                    )
            
            # Draw main text
            draw.text(
                (text_x, y),
                line,
                font=self.font,
                fill=self.config.text_color
            )
        
        return bg
    
    def _wrap_text(self, text: str, max_chars: int = 20) -> str:
        """Wrap text to multiple lines."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= max_chars:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines[:3])  # Max 3 lines


# ============================================
# Title Generator
# ============================================
class TitleGenerator:
    """
    Generate click-worthy titles using pattern-based hooks.
    
    Patterns:
    - Curiosity gap: "Why X Did Y (And What Happened Next)"
    - Numbers: "Top 10 X That Will Y"
    - Controversy: "The Truth About X"
    """
    
    PATTERNS = [
        "{emoji} {subject} - You Won't Believe What Happened",
        "The {adjective} Truth About {subject}",
        "Why {subject} {verb} (And What Happened Next)",
        "{number} {subject} That Will {emotion} You",
        "I Tried {subject} for {time} - Here's What Happened",
        "{subject}: The Untold Story",
        "What They Don't Tell You About {subject}",
        "{emoji} {subject} Changed Everything",
    ]
    
    EMOJIS = {
        "history": ["⚔️", "🏛️", "👑", "📜", "🗡️"],
        "pets": ["🐕", "🐈", "🐾", "❤️", "😻"],
        "scifi": ["🚀", "🛸", "🌌", "👽", "🤖"],
        "default": ["🔥", "💥", "⚡", "✨", "🎯"]
    }
    
    ADJECTIVES = ["Shocking", "Incredible", "Hidden", "Real", "Dark", "Untold", "Strange"]
    
    def generate(
        self,
        topic: str,
        niche: str = "default",
        pattern_index: Optional[int] = None
    ) -> str:
        """
        Generate an optimized title.
        
        Args:
            topic: Main subject of the video
            niche: Channel niche for emoji selection
            pattern_index: Specific pattern to use (random if None)
        """
        pattern = self.PATTERNS[pattern_index] if pattern_index is not None else random.choice(self.PATTERNS)
        emoji = random.choice(self.EMOJIS.get(niche, self.EMOJIS["default"]))
        adjective = random.choice(self.ADJECTIVES)
        
        title = pattern.format(
            emoji=emoji,
            subject=topic,
            adjective=adjective,
            verb="Changed History",
            number=random.choice(["5", "7", "10", "15"]),
            emotion="SHOCK",
            time="30 Days"
        )
        
        # Ensure title isn't too long (YouTube limit ~100 chars, but 60-70 is optimal)
        if len(title) > 70:
            title = title[:67] + "..."
        
        return title


# ============================================
# Description Generator
# ============================================
class DescriptionGenerator:
    """Generate SEO-optimized video descriptions."""
    
    TEMPLATE = """
{hook}

{main_content}

🔔 Subscribe for more {niche} content!
👍 Like if you enjoyed this video
💬 Comment your thoughts below

##{tags_line}

---
📧 Business: contact@example.com
⏰ New videos every week!

{ai_disclosure}
"""

    AI_DISCLOSURE = "This video contains AI-generated content. Character imagery and animations were created using artificial intelligence."
    
    def generate(
        self,
        title: str,
        script_summary: str,
        niche: str,
        tags: list[str],
        include_ai_disclosure: bool = True
    ) -> str:
        """
        Generate an optimized description.
        
        Args:
            title: Video title
            script_summary: Brief summary from script
            niche: Channel niche
            tags: SEO tags
            include_ai_disclosure: Add AI content disclosure
        """
        hook = f"🎬 {title}\n\nIn this video, {script_summary}"
        
        # Create hashtag line from top 5 tags
        top_tags = tags[:5] if len(tags) > 5 else tags
        tags_line = " #".join(tag.replace(" ", "") for tag in top_tags)
        
        description = self.TEMPLATE.format(
            hook=hook,
            main_content=script_summary,
            niche=niche.replace("_", " ").title(),
            tags_line=tags_line,
            ai_disclosure=self.AI_DISCLOSURE if include_ai_disclosure else ""
        )
        
        return description.strip()


# ============================================
# SEO Tag Optimizer
# ============================================
class TagOptimizer:
    """Optimize tags for YouTube SEO."""
    
    NICHE_TAGS = {
        "history": ["history", "documentary", "ancient history", "facts", "education"],
        "pets": ["pets", "cats", "dogs", "funny animals", "cute pets", "pet videos"],
        "scifi": ["sci-fi", "science fiction", "space", "future", "aliens", "robots"],
    }
    
    def optimize(
        self,
        topic: str,
        niche: str,
        base_tags: list[str] = None
    ) -> list[str]:
        """
        Generate optimized tag list.
        
        Args:
            topic: Video topic
            niche: Channel niche
            base_tags: Initial tags from config
            
        Returns:
            List of optimized tags (max 500 chars total)
        """
        tags = []
        
        # Add base tags first
        if base_tags:
            tags.extend(base_tags)
        
        # Add niche-specific tags
        if niche in self.NICHE_TAGS:
            tags.extend(self.NICHE_TAGS[niche])
        
        # Extract keywords from topic
        topic_words = re.findall(r'\b\w+\b', topic.lower())
        tags.extend([w for w in topic_words if len(w) > 3])
        
        # Add variations
        if topic:
            tags.append(topic)
            tags.append(f"{topic} explained")
            tags.append(f"{topic} facts")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower not in seen:
                seen.add(tag_lower)
                unique_tags.append(tag)
        
        # Limit to 500 characters total (YouTube limit)
        result = []
        total_chars = 0
        for tag in unique_tags:
            if total_chars + len(tag) + 1 <= 500:
                result.append(tag)
                total_chars += len(tag) + 1
            else:
                break
        
        return result


# ============================================
# Main SEO Service
# ============================================
class YouTubeSEO:
    """
    Complete YouTube SEO optimization service.
    
    Usage:
        seo = YouTubeSEO()
        result = seo.optimize(
            topic="Roman Emperors",
            niche="history",
            background_image="/path/to/scene.png"
        )
        print(result.title)
        print(result.description)
    """
    
    def __init__(self):
        self.thumbnail_generator = ThumbnailGenerator()
        self.title_generator = TitleGenerator()
        self.description_generator = DescriptionGenerator()
        self.tag_optimizer = TagOptimizer()
    
    def optimize(
        self,
        topic: str,
        niche: str,
        script_summary: str = "",
        background_image: Optional[Path] = None,
        character_image: Optional[Path] = None,
        base_tags: list[str] = None,
        output_dir: Optional[Path] = None
    ) -> SEOResult:
        """
        Generate complete SEO package.
        
        Args:
            topic: Video topic
            niche: Channel niche
            script_summary: Brief content summary
            background_image: Image for thumbnail
            character_image: Character face for thumbnail
            base_tags: Additional tags from config
            output_dir: Directory for thumbnail output
        """
        # Generate title
        title = self.title_generator.generate(topic, niche)
        
        # Generate tags
        tags = self.tag_optimizer.optimize(topic, niche, base_tags)
        
        # Generate description
        description = self.description_generator.generate(
            title=title,
            script_summary=script_summary or f"we explore the fascinating world of {topic}",
            niche=niche,
            tags=tags,
            include_ai_disclosure=True
        )
        
        # Generate thumbnail if image provided
        thumbnail_path = None
        if background_image and Path(background_image).exists():
            output_path = None
            if output_dir:
                output_path = output_dir / f"thumbnail_{topic.replace(' ', '_')[:20]}.jpg"
            
            # Extract short hook from title for thumbnail
            thumbnail_text = topic.upper()[:25]
            
            thumbnail_path = self.thumbnail_generator.generate(
                background_image=background_image,
                title_text=thumbnail_text,
                character_image=character_image,
                emoji=random.choice(["🔥", "⚔️", "🎯", "💥"]) if niche == "history" else None,
                output_path=output_path
            )
        
        return SEOResult(
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=thumbnail_path
        )


# ============================================
# Hook Script Generator
# ============================================
class HookGenerator:
    """Generate engaging hook scripts for the first 15-20 seconds."""
    
    HOOK_PATTERNS = [
        "What if I told you that {topic} was completely different from what you thought?",
        "In the next {duration} seconds, I'm going to show you something that will change how you see {topic}.",
        "Most people have no idea that {topic}... but by the end of this video, you will.",
        "This is the story that history books don't want you to know about {topic}.",
        "{topic}. Three words that changed everything.",
    ]
    
    def generate(
        self,
        topic: str,
        niche: str = "default",
        video_duration: int = 60
    ) -> str:
        """
        Generate a hook script for the video intro.
        
        Args:
            topic: Main topic
            niche: Channel niche for tone
            video_duration: Total video length in seconds
        """
        pattern = random.choice(self.HOOK_PATTERNS)
        
        hook = pattern.format(
            topic=topic,
            duration=video_duration
        )
        
        # Add niche-specific flavor
        if niche == "history":
            hook = f"[Dramatic music] {hook}"
        elif niche == "pets":
            hook = f"[Cute intro] {hook}"
        elif niche == "scifi":
            hook = f"[Sci-fi ambience] {hook}"
        
        return hook
