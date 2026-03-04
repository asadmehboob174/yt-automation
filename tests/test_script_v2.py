import pytest
import asyncio
from packages.services.script_generator import ScriptGenerator, SceneBreakdown
from unittest.mock import patch, MagicMock

@pytest.fixture
def script_gen():
    return ScriptGenerator()

def test_parse_manual_script_with_voiceover_and_dialogue(script_gen):
    script_content = """
🎞️ PART 3: SCENE-BY-SCENE STORYBOARD

SCENE 1 – The Park

Shot Type: Close-up

Text-to-Image Prompt: Max runs in the park.

Image-to-Video Prompt: Max barks loudly. Dialogue: "Woof woof!"

Voiceover: The park was full of surprises today.
"""
    breakdown = script_gen.parse_manual_script(script_content)
    
    assert len(breakdown.scenes) == 1
    scene = breakdown.scenes[0]
    
    # The image-to-video prompt should NOT contain the dialogue
    assert "Max barks loudly." in scene.image_to_video_prompt
    assert 'Dialogue: "Woof woof!"' not in scene.image_to_video_prompt
    
    # verify new fields
    assert scene.dialogue == "Woof woof!"
    assert scene.voiceover == "The park was full of surprises today."


@pytest.mark.asyncio
@patch.dict('os.environ', {'HF_TOKEN': 'fake_token'})
@patch('huggingface_hub.InferenceClient')
async def test_compute_scene_durations_hf(mock_hf_client_class, script_gen):
    # Setup mock
    mock_client = MagicMock()
    mock_hf_client_class.return_value = mock_client
    
    # Mock response for a long scene
    mock_chat = MagicMock()
    mock_chat.choices = [
        MagicMock(message=MagicMock(content='{"durations": [{"scene_number": 1, "clip_duration": "10s", "needs_extend": true, "extend_duration": "6s", "total_clip_time": 16}]}'))
    ]
    mock_client.chat_completion.return_value = mock_chat
    
    long_text = "This is a very long voiceover text that will definitely require more than the standard 6 seconds to read."
    scenes_payload = [{"scene_number": 1, "voiceover": long_text}]
    result = await script_gen.compute_scene_durations(scenes_payload)
    
    assert len(result) == 1
    scene_result = result[0]
    assert "duration_config" in scene_result
    
    config = scene_result["duration_config"]
    assert config["clip_duration"] == "10s"
    assert config["needs_extend"] is True
    assert config["extend_duration"] == "6s"


def test_parse_manual_script_no_voiceover_but_has_dialogue(script_gen):
    script_content = """
🎞️ PART 3: SCENE-BY-SCENE STORYBOARD

SCENE 1 – Close Up

Shot Type: Medium

Text-to-Image Prompt: Close up of a man.

Image-to-Video Prompt: He turns and says something. Dialogue: "Hello there!"
"""
    breakdown = script_gen.parse_manual_script(script_content)
    assert len(breakdown.scenes) == 1
    
    scene = breakdown.scenes[0]
    assert scene.dialogue == "Hello there!"
    assert scene.voiceover == ""
    assert scene.image_to_video_prompt.strip() == "He turns and says something."
    

def test_parse_manual_script_legacy_format(script_gen):
    script_content = """
🎞️ PART 3: SCENE-BY-SCENE STORYBOARD

SCENE 1 – Legacy

Shot Type: Wide

Text-to-Image Prompt: Standard old format target.

Image-to-Video Prompt: Just motion here.
"""
    breakdown = script_gen.parse_manual_script(script_content)
    assert len(breakdown.scenes) == 1
    scene = breakdown.scenes[0]
    assert scene.dialogue == ""
    assert scene.voiceover == ""
    assert scene.image_to_video_prompt.strip() == "Just motion here."
    
