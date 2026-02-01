import logging
import httpx
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import ffmpeg

logger = logging.getLogger(__name__)

class MusicLibrary:
    """
    Manages a library of high-quality royalty-free background music.
    Downloads tracks on demand and processes them (loop/fade) for videos.
    """
    
    # Kevin MacLeod (incompetech.com) - Licensed under Creative Commons: By Attribution 4.0 License
    # Kevin MacLeod (incompetech.com) - Licensed under Creative Commons: By Attribution 4.0 License
    TRACKS = {
        "dramatic": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3",
            "filename": "volatile_reaction.mp3"
        },
        "cinematic": {
            # Impact Moderato (Suspense/Action)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Impact%20Moderato.mp3",
            "filename": "impact_moderato.mp3"
        },
        "calm": {
            # Clear Waters (Relaxing/Documentary)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clear%20Waters.mp3",
            "filename": "clear_waters.mp3"
        },
        "horror": {
            # The Hive (Horror/Dark)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Hive.mp3",
            "filename": "the_hive.mp3"
        },
        "adventurous": {
            # Adventure Meme (Light Adventure)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Adventure%20Meme.mp3",
            "filename": "adventure_meme.mp3"
        },
        "cute": {
            # Kawaii Kitsune (Cute/Happy)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Kawaii%20Kitsune.mp3",
            "filename": "kawaii_kitsune.mp3"
        },
        "travel": {
            # Life of Riley (Upbeat/Travel/Vlog)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Life%20of%20Riley.mp3",
            "filename": "life_of_riley.mp3"
        },
        "beauty": {
            # Life of Riley is also great for beauty/lifestyle
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Life%20of%20Riley.mp3",
            "filename": "life_of_riley.mp3"
        },
        "suspense": {
             # Impact Moderato works well here
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Impact%20Moderato.mp3",
            "filename": "impact_moderato.mp3"
        },
        "hiphop": {
            # Protofunk (Funk/HipHop)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Protofunk.mp3",
            "filename": "protofunk.mp3"
        },
        "edm": {
            # Loopster (Electronic/Fitness)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Loopster.mp3",
            "filename": "loopster.mp3"
        },
        "rock": {
            # Malt Shop Bop (Upbeat Rock)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Malt%20Shop%20Bop.mp3",
            "filename": "malt_shop_bop.mp3"
        },
        "piano": {
            # Touching Moments (Touching/Piano)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Touching%20Moments.mp3",
            "filename": "touching_moments.mp3"
        },
        "sorrow": {
            # Heartbreaking (Sad/Sorrow)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3",
            "filename": "heartbreaking.mp3"
        },
        "classical": {
            # Canon in D Major
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Canon%20in%20D%20Major.mp3",
            "filename": "canon_in_d.mp3"
        },
        "epic": {
            # Curse of the Scarab (Epic/History)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Curse%20of%20the%20Scarab.mp3",
            "filename": "curse_of_scarab.mp3"
        },
        "jazz": {
            # Faster Does It (Jazz/Comedy)
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Faster%20Does%20It.mp3",
            "filename": "faster_does_it.mp3"
        }
    }
    
    def __init__(self, cache_dir: str = "packages/services/assets/music"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _download_track(self, mood: str) -> Path:
        """Download track for mood if not cached."""
        track_info = self.TRACKS.get(mood, self.TRACKS["calm"])
        local_path = self.cache_dir / track_info["filename"]
        
        if local_path.exists():
            return local_path
            
        logger.info(f"📥 Downloading '{mood}' track from {track_info['url']}...")
        try:
            with httpx.Client() as client:
                resp = client.get(track_info["url"], follow_redirects=True, timeout=120.0)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
            logger.info(f"✅ Cached track: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ Failed to download music: {e}")
            # Fallback to existing calm track if possible, or error
            if mood != "calm":
                return self._download_track("calm")
            raise e

    def get_music_for_video(self, duration: float, mood: str = "calm") -> Path:
        """
        Get a music track looped/trimmed to the exact video duration.
        """
        # Map generic moods to our specific tracks
        # Note: MoodAnalyzer outputs keys that match our TRACKS keys mostly
        mood_map = {
            "scary": "horror",
            "thriller": "suspense",
            "action": "dramatic", # Adventure Meme is light, maybe use Dramatic for intense action
            "intense": "dramatic",
            "dreamy": "cute", # Kawaii can be dreamy/cute
            "relaxation": "calm",
            "meditation": "calm",
            "educational": "calm",
            "peace": "calm",
            "story": "cinematic",
            "vlog": "travel",
            "lifestyle": "beauty",
            "romance": "piano",
            "romantic": "piano",
            "love": "piano",
            "piano": "piano",
            "sad": "sorrow",
            "depressing": "sorrow",
            "emotional": "sorrow",
            "epic": "epic",
            "heroic": "epic",
            "jazz": "jazz",
            "comedy": "jazz",
            "hiphop": "hiphop",
            "rap": "hiphop",
            "urban": "hiphop",
            "edm": "edm",
            "fitness": "edm",
            "workout": "edm",
            "gym": "edm",
            "rock": "rock",
            "upbeat": "rock",
            "phonk": "dramatic", # Aggressive phonk
            "aggressive": "dramatic",
            "reggaeton": "travel", # Map to upbeat travel for now
            "afrobeats": "travel",
            "classical": "classical",
            "history": "epic"
        }
        
        # Normalize mood
        mood = mood.lower()
        selected_mood = mood_map.get(mood, mood)
        
        # Special case: map Action to Dramatic if Adventure Meme is too light
        if mood == "action":
            selected_mood = "dramatic"
            
        if selected_mood not in self.TRACKS:
            # Check if it was a valid key directly
            if mood in self.TRACKS:
                selected_mood = mood
            else:
                selected_mood = "calm" # Final fallback
            
        base_track = self._download_track(selected_mood)
        
        # Process track to match duration (Loop + Fade Out)
        output_filename = f"bgm_{selected_mood}_{int(duration)}s.mp3"
        output_path = self.cache_dir / "generated" / output_filename
        output_path.parent.mkdir(exist_ok=True)
        
        if output_path.exists():
            return output_path
            
        logger.info(f"🎵 Processing music: {selected_mood} for {duration}s...")
        
        # FFmpeg: loop input, trim to duration, add 3s fade out
        # stream_loop -1 loops infinitely
        # t sets duration
        # afade applies fade out
        
        try:
            cmd = [
                'ffmpeg', '-y',
                '-stream_loop', '-1',
                '-i', str(base_track),
                '-t', str(duration),
                '-af', f'afade=t=out:st={duration-3}:d=3',
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ Generated BGM: {output_path.name}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg music processing failed: {e.stderr.decode()}")
            return base_track # Fallback to raw track

# Function for compatibility with existing imports
def generate_background_music(duration: float, mood: str = "calm") -> Path:
    lib = MusicLibrary()
    return lib.get_music_for_video(duration, mood)
