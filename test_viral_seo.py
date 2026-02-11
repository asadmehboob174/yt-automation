import sys
import os
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages"))

from services.youtube_seo import YouTubeSEO

def test_seo_generation():
    seo = YouTubeSEO()
    
    topics = [
        "The Secret History of the Roman Empire",
        "How a Stray Cat Started a War",
        "Future Mars Colony Life"
    ]
    
    niches = ["history", "pets", "scifi"]
    
    for topic, niche in zip(topics, niches):
        print(f"\n--- Testing Topic: {topic} ({niche}) ---")
        result = seo.optimize(
            topic=topic,
            niche=niche,
            script_summary=f"In this episode, we uncover the hidden details about {topic} that most people ignore."
        )
        
        print(f"TITLE: {result.title}")
        print("-" * 20)
        print(f"DESCRIPTION PREVIEW:\n{result.description[:300]}...")
        print("-" * 20)
        print(f"TAGS: {', '.join(result.tags[:10])}")

if __name__ == "__main__":
    test_seo_generation()
