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
    # Curated High-Quality Royalty Free Music (Kevin MacLeod / Incompetech)
    # Mirroring the "YouTube Audio Library" vibe with trusted Creative Commons sources.
    TRACKS = {
        # --- Cinematic / Epic ---
        "epic": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Curse%20of%20the%20Scarab.mp3",
            "filename": "curse_of_the_scarab.mp3"
        },
        "dramatic": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3",
            "filename": "volatile_reaction.mp3"
        },
        "cinematic": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Thunderbird.mp3",
            "filename": "thunderbird.mp3"
        },
        
        # --- Horror / Dark ---
        "horror": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Hive.mp3",
            "filename": "the_hive.mp3"
        },
        "suspense": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Giant%20Wyrm.mp3",
            "filename": "giant_wyrm.mp3"
        },
        "scary": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gathering%20Darkness.mp3",
             "filename": "gathering_darkness.mp3"
        },

        # --- Happy / Upbeat / YT Vlogger ---
        "cute": {
             # Changed from Carefree (Too cartoonish) to Wallpaper (Happy/Clean)
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3", 
             "filename": "wallpaper.mp3"
        },
        "travel": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Life%20of%20Riley.mp3", 
            "filename": "life_of_riley.mp3"
        },
        "happy": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3", 
            "filename": "wallpaper.mp3"
        },
        
        # --- Calm / Documentary ---
        "calm": {
            # Meditating Beat Link was bad, reverting to Clear Waters which is a classic
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clear%20Waters.mp3",
            "filename": "clear_waters.mp3"
        },
        "peace": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Porch%20Swing%20Days%20-%20slower.mp3",
             "filename": "porch_swing_days.mp3"
        },
        "beauty": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Somewhere%20Sunny.mp3",
            "filename": "somewhere_sunny.mp3"
        },

        # --- Emotional / Sad ---
        "sorrow": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3",
            "filename": "heartbreaking.mp3"
        },
        "piano": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Touching%20Moments%20Two%20-%20Higher.mp3",
            "filename": "touching_moments_two.mp3"
        },

        # --- Action / Rock ---
        "rock": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Malt%20Shop%20Bop.mp3",
            "filename": "malt_shop_bop.mp3"
        },
        "action": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Movement%20Proposition.mp3",
            "filename": "movement_proposition.mp3"
        },
        
        # --- Urban / HipHop ---
        "hiphop": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Rollin%20at%205.mp3",
            "filename": "rollin_at_5.mp3"
        },
        "jazz": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Bass%20Walker.mp3",
             "filename": "bass_walker.mp3"
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
            "comedy": "happy", # Wallpaper is quirky/funny
            "funny": "happy",
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
            "classical": "classical",
            "history": "epic",
            "motivational": "epic",
            "inspiring": "cinematic"
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
