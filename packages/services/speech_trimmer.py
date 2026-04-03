import os
import torch
import ffmpeg
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

class SpeechTrimmer:
    def __init__(self):
        self.SAMPLING_RATE = 16000
        self.model = None
        self.utils = None

    def _load_model(self):
        if self.model is None:
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                trust_repo=True
            )
        return self.model, self.utils

    def get_speech_segments(self, video_path: str) -> List[dict]:
        """Detects all speech segments in a video file."""
        import uuid
        temp_wav = f"/tmp/temp_audio_{uuid.uuid4().hex}.wav"
        
        try:
            ffmpeg.input(video_path).output(temp_wav, ac=1, ar=self.SAMPLING_RATE).run(quiet=True, overwrite_output=True)
            
            model, utils = self._load_model()
            get_speech_timestamps, _, _, _, _ = utils
            
            import wave
            import numpy as np
            with wave.open(temp_wav, 'rb') as wf:
                audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                wav = torch.from_numpy(audio)

            segments = get_speech_timestamps(wav, model, sampling_rate=self.SAMPLING_RATE, return_seconds=True)
        finally:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
                
        return segments

    def trim_to_speech_end(self, video_path: str, padding: float = 0.15) -> str:
        """Cuts video at the end of the last detected speech segment."""
        segments = self.get_speech_segments(video_path)
        if not segments:
            logger.info("No speech detected, returning original video.")
            return video_path
        
        last_speech_end = segments[-1]['end'] + padding
        
        import uuid
        output_path = f"/tmp/trimmed_{uuid.uuid4().hex}.mp4"
        
        ffmpeg.input(video_path, t=last_speech_end).output(output_path, c="copy").run(quiet=True, overwrite_output=True)
        return output_path
