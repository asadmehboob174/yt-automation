
import os
import logging
from pathlib import Path
from gradio_client import Client, handle_file
import shutil

logger = logging.getLogger(__name__)

class AudioSeparator:
    """
    Client for interacting with a Demucs Audio Separator hosted on Hugging Face Spaces.
    """
    
    def __init__(self):
        self.hf_space_url = os.getenv("HF_DEMUCS_SPACE_URL") # e.g. "username/demucs-space"
        self.hf_token = os.getenv("HF_TOKEN")
        
        if not self.hf_space_url:
            logger.warning("⚠️ HF_DEMUCS_SPACE_URL is not set. Audio separation will be skipped.")
            self.client = None
        else:
            try:
                self.client = Client(self.hf_space_url, hf_token=self.hf_token)
                logger.info(f"✅ Connected to Demucs Space: {self.hf_space_url}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Demucs Space: {e}")
                self.client = None

    def separate_audio(self, input_path: Path) -> tuple[Path, Path]:
        """
        Separate audio into (background, vocals).
        Returns paths to local files.
        """
        if not self.client:
            logger.warning("⚠️ separate_audio called but client is not configured.")
            return None, None
            
        if not input_path.exists():
            logger.error(f"❌ Input file not found: {input_path}")
            return None, None
            
        logger.info(f"✂️ Separating audio (sending to HF Space)... {input_path.name}")
        
        try:
            # Predict expects: [audio_file]
            # Returns: [background_path, vocals_path] (as temp files)
            result = self.client.predict(
                audio_file=handle_file(str(input_path)),
                api_name="/predict"
            )
            
            # Result is a tuple/list of file paths (temp files from gradio_client)
            bg_temp, vocals_temp = result
            
            # Move to local directory to persist/rename? 
            # Or just return path (gradio_client handles download)
            
            # Let's ensure they are Path objects
            return Path(bg_temp), Path(vocals_temp)
            
        except Exception as e:
            logger.error(f"❌ Audio separation failed: {e}")
            return None, None

