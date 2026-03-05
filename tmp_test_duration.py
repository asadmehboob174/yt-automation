import json
import asyncio
from packages.services.script_generator import ScriptGenerator

async def main():
    generator = ScriptGenerator()
    
    # Text inside prompt
    urdu_text = "رنگوں اور روشنیوں سے سجی ہوئی پریوں کی دلکش دنیا میں ایک عجیب و دل فریب رسم صدیوں سے چلی آ رہی تھی۔"
    words = urdu_text.split()
    print(f"Target word count: {len(words)}")
    
    scenes = [
        {
            "scene_number": 1,
            "voiceover_text": None, # Emptied
            "dialogue": None,       # Emptied
            "image_to_video_prompt": f'Cinematic drone shot. Dialogue: "{urdu_text}"'
        }
    ]
    
    result = await generator.compute_scene_durations(scenes)
    print("\n--- RESULTS ---")
    print(f"Analyzed Word Count: {result[0]['duration_config'].get('word_count', 'N/A')}")
    print(json.dumps(result[0]['duration_config'], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
