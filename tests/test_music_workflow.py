
import unittest
import asyncio
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

# Need to mock imports before importing the module under test
# because it might try to connect to services on import
sys.modules["services.inngest_client"] = MagicMock()
sys.modules["inngest"] = MagicMock()

from services.video_workflow import _generate_dynamic_soundtrack

class TestMusicWorkflow(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch("services.music_generator.MusicLibrary")
    @patch("services.music_generator.generate_background_music")
    @patch("services.music_generator.generate_music_with_ai")
    def test_routing_logic(self, mock_ai, mock_stock, mock_lib):
        # Setup mocks
        mock_lib.TRACKS = {"horror": [], "happy": []} # Mock known moods
        mock_ai.return_value = Path("/tmp/ai_music.mp3")
        mock_stock.return_value = Path("/tmp/stock_music.mp3")
        
        # Test 1: Stock Music (Mood)
        config_stock = {"background_music": "Horror theme"}
        result = self.loop.run_until_complete(
            _generate_dynamic_soundtrack(config_stock, {}, 30.0)
        )
        # Should call stock because "Horror" is in TRACKS
        mock_stock.assert_called_with(30.0, "horror")
        mock_ai.assert_not_called()
        self.assertEqual(result, Path("/tmp/stock_music.mp3"))
        
        # Reset mocks
        mock_stock.reset_mock()
        mock_ai.reset_mock()
        
        # Test 2: AI Music (Prompt)
        config_ai = {"background_music": "Cyberpunk city rain ambient"}
        # "Cyberpunk" is not in our mocked TRACKS
        result = self.loop.run_until_complete(
            _generate_dynamic_soundtrack(config_ai, {}, 30.0)
        )
        
        # Should call AI because "Cyberpunk" is not a known mood
        mock_ai.assert_called_with("Cyberpunk city rain ambient", duration=30)
        mock_stock.assert_not_called()
        self.assertEqual(result, Path("/tmp/ai_music.mp3"))

if __name__ == "__main__":
    unittest.main()
