"""
Subtitle Engine - SRT Generation.

Generates SRT subtitle files from video scripts
with proper timing synchronization.
"""
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import pysrt

logger = logging.getLogger(__name__)


@dataclass
class SubtitleEntry:
    """A single subtitle entry with timing."""
    text: str
    start_seconds: float
    end_seconds: float


class SubtitleEngine:
    """Generate SRT subtitle files from scripts."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_srt(
        self,
        entries: list[SubtitleEntry],
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate SRT file from subtitle entries."""
        output_path = output_path or self.output_dir / "subtitles.srt"
        
        subs = pysrt.SubRipFile()
        
        for i, entry in enumerate(entries, 1):
            sub = pysrt.SubRipItem(
                index=i,
                start=pysrt.SubRipTime(seconds=entry.start_seconds),
                end=pysrt.SubRipTime(seconds=entry.end_seconds),
                text=entry.text
            )
            subs.append(sub)
        
        subs.save(str(output_path), encoding="utf-8")
        logger.info(f"✅ Generated SRT with {len(entries)} entries -> {output_path.name}")
        return output_path
    
    def generate_from_script(
        self,
        scenes: list[dict],  # List of scene dicts with voiceover_text and duration
        words_per_second: float = 2.5,
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate SRT from video script scenes."""
        entries = []
        current_time = 0.0
        
        for scene in scenes:
            text = scene.get("voiceover_text", "")
            duration = scene.get("duration_in_seconds", 10)
            
            # Split long text into chunks
            words = text.split()
            chunk_size = int(words_per_second * 3)  # ~3 seconds per subtitle
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk_text = " ".join(chunk_words)
                
                # Calculate timing
                chunk_duration = len(chunk_words) / words_per_second
                start = current_time
                end = current_time + chunk_duration
                
                entries.append(SubtitleEntry(
                    text=chunk_text,
                    start_seconds=start,
                    end_seconds=end
                ))
                
                current_time = end
            
            # Ensure we don't exceed scene duration
            if current_time > sum(s.get("duration_in_seconds", 10) for s in scenes[:scenes.index(scene) + 1]):
                current_time = sum(s.get("duration_in_seconds", 10) for s in scenes[:scenes.index(scene) + 1])
        
        return self.generate_srt(entries, output_path)
    
    def offset_subtitles(
        self,
        srt_path: Path,
        offset_seconds: float,
        output_path: Optional[Path] = None
    ) -> Path:
        """Shift all subtitles by a given offset."""
        output_path = output_path or self.output_dir / "offset_subtitles.srt"
        
        subs = pysrt.open(str(srt_path))
        subs.shift(seconds=offset_seconds)
        subs.save(str(output_path), encoding="utf-8")
        
        logger.info(f"✅ Offset subtitles by {offset_seconds}s -> {output_path.name}")
        return output_path
