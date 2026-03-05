import os
import httpx
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

class MoodAnalyzer:
    """
    Analyzes text (title, niche, script) to determine the best 
    background music mood using an LLM.
    """
    
    MOODS = [
        "horror", "adventurous", "dreamy", "cute", 
        "travel", "beauty", "suspense", "dramatic", 
        "calm", "cinematic", "epic", "rock", 
        "hiphop", "jazz", "classical", "edm", 
        "piano", "sorrow",
        "funny", "happy", "upbeat", "inspiring", "motivational"
    ]
    
    def __init__(self):
        self.api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        self.model = "meta-llama/Llama-3.3-70B-Instruct"
        
    def analyze_mood(self, title: str, niche: str, description: str = "") -> str:
        """
        Determine the best mood for the video.
        Returns one of the keys in Moods.
        """
        if not self.api_key:
            logger.warning("No HUGGINGFACE_API_KEY or HF_TOKEN set, falling back to basic mapping")
            return self._basic_map(niche)
            
        from huggingface_hub import InferenceClient
        
        prompt = f"""
        Analyze the following video context and select the single best background music mood from this list:
        {self.MOODS}
        
        Video Title: {title}
        Niche: {niche}
        Description: {description}
        
        Return ONLY the mood word from the list. Nothing else.
        Mood:
        """
        
        try:
            client = InferenceClient(model=self.model, token=self.api_key)
            
            # Simple completion for speed
            resp = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            mood = resp.choices[0].message.content.strip().lower()
                
            # Clean up response (remove punctuation etc)
            mood = mood.replace(".", "").replace('"', '').replace("'", "").strip()
            
            # Validate
            for valid_mood in self.MOODS:
                if valid_mood in mood:
                    logger.info(f"🧠 LLM selected mood: '{valid_mood}' for '{title}'")
                    return valid_mood
                        
            logger.warning(f"LLM returned invalid mood '{mood}', falling back.")
            return self._basic_map(niche)
                
        except Exception as e:
            logger.error(f"Mood analysis failed: {e}")
            return self._basic_map(niche)
            
    def _basic_map(self, niche: str) -> str:
        """Fallback keyword mapping."""
        niche = niche.lower()
        if "horror" in niche or "scary" in niche: return "horror"
        if "pet" in niche or "animal" in niche: return "cute"
        if "travel" in niche or "outdoor" in niche: return "travel"
        if "beauty" in niche or "makeup" in niche: return "beauty"
        if "story" in niche: return "cinematic"
        return "calm"
