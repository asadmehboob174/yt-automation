import logging
import httpx
import os
import asyncio
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
        },

        # --- Ghibli / Cozy (User Requested) ---
        "ghibli": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ishikari%20Lore.mp3",
            "filename": "ishikari_lore.mp3"
        },
        "cozy_piano": {
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gymnopedie%20No%201.mp3",
            "filename": "gymnopedie_no_1.mp3"
        },
        "playful": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Onion%20Capers.mp3",
             "filename": "onion_capers.mp3"
        },
        "magic_forest": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Enchanted%20Valley.mp3",
             "filename": "enchanted_valley.mp3"
        },
        "winter_waltz": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Frost%20Waltz%20(Alternate).mp3",
             "filename": "frost_waltz.mp3"
        },
        "cute_lemon": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Easy%20Lemon.mp3",
             "filename": "easy_lemon.mp3"
        },
        "kiki_jazz": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sweet%20Vermouth.mp3",
             "filename": "sweet_vermouth.mp3"
        },
        "nostalgia": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Touching%20Moments%20Two%20-%20Higher.mp3",
             "filename": "touching_moments.mp3"
        },
        "uplifting_strings": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Somewhere%20Sunny.mp3",
             "filename": "somewhere_sunny.mp3"
        },
        "gentle_rain": {
             "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clean%20Soul.mp3",
             "filename": "clean_soul.mp3"
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
            "inspiring": "cinematic",
            
            # --- New Ghibli / Cozy Mappings ---
            "whimsical": "playful",
            "magical": "magic_forest",
            "fantasy": "magic_forest",
            "forest": "magic_forest",
            "winter": "winter_waltz",
            "snow": "winter_waltz",
            "cozy": "cozy_piano",
            "relaxing": "gentle_rain",
            "lofi": "gentle_rain",
            "soul": "gentle_rain",
            "anime": "ghibli",
            "folk": "ghibli",
            "japan": "ghibli",
            "kiki": "kiki_jazz",
            "cafe": "kiki_jazz",
            "coffee": "kiki_jazz",
            "nostalgic": "nostalgia",
            "uplifting": "uplifting_strings",
            "cute": "cute_lemon", # Override old mapping
            "kawaii": "cute_lemon"
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

async def generate_music_with_ai(prompt: str, duration: int = 10) -> Optional[Path]:
    """Generate custom music using AI (MusicGen)."""
    try:
        api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        if not api_key:
            logger.warning("No HF API Key found. Skipping AI music generation.")
            return None
            
        logger.info(f"🎵 Generating AI Music: '{prompt}' ({duration}s)...")
        
        # Using facebook/musicgen-small via HF Inference API
        API_URL = "https://api-inference.huggingface.co/models/facebook/musicgen-small"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # MusicGen API expects specific payload structure
        payload = {"inputs": prompt}
        
        async with httpx.AsyncClient() as client:
            # Increased timeout for audio generation
            response = await client.post(API_URL, headers=headers, json=payload, timeout=120.0)
            
            if response.status_code != 200:
                logger.error(f"HF MusicGen Error {response.status_code}: {response.text}")
                return None
                
            # Response is binary audio
            audio_bytes = response.content
            
        # Save to cache
        # Use a safe filename based on prompt hash
        import hashlib
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        filename = f"ai_music_{prompt_hash}_{duration}s.flac"
        
        cache_dir = Path("packages/services/assets/music/generated")
        cache_dir.mkdir(parents=True, exist_ok=True)
        file_path = cache_dir / filename
        
        file_path.write_bytes(audio_bytes)
        logger.info(f"✅ AI Music Generated: {file_path}")
        
        return file_path
        
    except Exception as e:
        logger.error(f"❌ AI Music Generation Failed: {e}")
        return None
