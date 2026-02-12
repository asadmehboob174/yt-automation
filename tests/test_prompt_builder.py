
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

# Mock imports likely needed by grok_agent
sys.modules["playwright.async_api"] = MagicMock()

from services.grok_agent import PromptBuilder

class TestPromptBuilder(unittest.TestCase):

    def test_full_prompt_override(self):
        """Verify full_prompt takes precedence and avoids duplication."""
        
        # User's exact example
        full_prompt_text = "[00:00–00:02] — Leo moves quickly... AUDIO: [LEO]: 'Go, go, go!' SFX: Rapid footsteps, heavy breathing."
        
        grok_video_prompt = {
            "full_prompt": full_prompt_text
        }
        
        dialogue = "LEO: Go, go, go!"
        
        # Call build
        result = PromptBuilder.build(
            character_pose="Standard pose",
            camera_angle="Wide",
            style_suffix="Pixar",
            motion_description="Running",
            dialogue=dialogue,
            grok_video_prompt=grok_video_prompt
        )
        
        print("\n--- TEST RESULT ---")
        print(f"Input Full Prompt: {full_prompt_text}")
        print(f"Resulting Prompt:  {result}")
        
        # Check that it starts with the duration prefix if missing in user prompt (user has [00-02], not 6s:)
        self.assertTrue(result.startswith("6s: [00:00–00:02]"))
        
        # Check that AUDIO is NOT duplicated
        audio_count = result.count("AUDIO:")
        self.assertEqual(audio_count, 1, f"AUDIO should appear exactly once, found {audio_count}")
        
        # Check that SFX is NOT duplicated
        sfx_count = result.count("SFX:")
        self.assertEqual(sfx_count, 1, f"SFX should appear exactly once, found {sfx_count}")
        
        # content check
        self.assertIn("Leo moves quickly", result)

    def test_merge_dialogue_into_full_prompt(self):
        """Verify dialogue is merged if full_prompt lacks audio."""
        
        # User provides full_prompt WITHOUT audio
        full_prompt_no_audio = "[00:00–00:02] — A cat sits on a fence."
        grok_video_prompt = {"full_prompt": full_prompt_no_audio}
        dialogue = "I am a cat."
        
        result = PromptBuilder.build(
            character_pose="Visuals...",
            camera_angle="Wide",
            style_suffix="Pixar",
            motion_description="Sitting",
            dialogue=dialogue,
            grok_video_prompt=grok_video_prompt,
            character_name="Mochi"
        )
        
        print(f"\nMerge Test Result: {result}")
        
        # Should contain the visual prompt
        self.assertIn(full_prompt_no_audio, result)
        # AND the dialogue (since it wasn't in full_prompt)
        self.assertIn('AUDIO: [MOCHI] (Natural): "I am a cat."', result)

    def test_standard_construction(self):
        """Verify normal prompt construction works as expected."""
        result = PromptBuilder.build(
            character_pose="A cat sitting",
            camera_angle="Close up",
            style_suffix="Cinematic",
            motion_description="The cat meows",
            dialogue="Meow!",
            character_name="Mochi",
            emotion="Happy"
        )
        
        # Should build standard prompt
        self.assertIn("The cat meows", result)
        self.assertIn("Shot: Close up", result)
        self.assertIn("AUDIO: [MOCHI] (Happy): \"Meow!\"", result)

if __name__ == "__main__":
    unittest.main()
