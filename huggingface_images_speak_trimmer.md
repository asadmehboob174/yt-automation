# Technical Implementation Guide: Image Generation & Audio Trimming

This guide provides the complete implementation details for the Hugging Face image generation pipeline and the intelligent speech trimming tool.

---

## 1. Hugging Face Image Generation (Python)

This service uses the `black-forest-labs/FLUX.1-schnell` model via the Hugging Face Router API.

### Core Implementation (`huggingface_image_generator.py`)

```python
import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class HuggingFaceImageGenerator:
    HF_ROUTER_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"

    def __init__(self):
        # Requires HF_TOKEN in environment
        self.hf_token = os.getenv("HF_TOKEN")
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}

    async def generate_image(self, prompt: str, is_shorts: bool = False, seed: int = 42) -> bytes:
        \"\"\"
        Generates an image bytes based on the prompt and aspect ratio.
        \"\"\"
        # Prepare Prompt with quality enhancers
        full_prompt = f"{prompt}, highly detailed, masterpiece, 8k resolution, cinematic lighting"
        
        # Dimensions based on format
        width, height = (720, 1280) if is_shorts else (1280, 720)

        payload = {
            "inputs": full_prompt,
            "parameters": {
                "seed": seed,
                "width": width,
                "height": height,
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.HF_ROUTER_URL, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                raise RuntimeError(f"HF Error {response.status_code}: {response.text}")
                
            return response.content
```

---

## 2. Intelligent Speech Trimming (Python)

Uses **Silero VAD** for voice detection and **FFmpeg** for video processing.

### Dependencies
```bash
pip install torch ffmpeg-python numpy
```

### Core Implementation (`speech_trimmer.py`)

```python
import os
import torch
import ffmpeg
from pathlib import Path
from typing import List, Optional

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
        \"\"\"Detects all speech segments in a video file.\"\"\"
        # 1. Extract audio to temp WAV (16kHz mono)
        temp_wav = "temp_audio.wav"
        ffmpeg.input(video_path).output(temp_wav, ac=1, ar=self.SAMPLING_RATE).run(quiet=True, overwrite_output=True)
        
        model, utils = self._load_model()
        get_speech_timestamps, _, _, _, _ = utils
        
        # Load audio (simplified version)
        import wave
        import numpy as np
        with wave.open(temp_wav, 'rb') as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            wav = torch.from_numpy(audio)

        segments = get_speech_timestamps(wav, model, sampling_rate=self.SAMPLING_RATE, return_seconds=True)
        os.remove(temp_wav)
        return segments

    def trim_to_speech_end(self, video_path: str, padding: float = 0.15) -> str:
        \"\"\"Cuts video at the end of the last detected speech segment.\"\"\"
        segments = self.get_speech_segments(video_path)
        if not segments: return video_path
        
        last_speech_end = segments[-1]['end'] + padding
        output_path = f"trimmed_{os.path.basename(video_path)}"
        
        # Fast, lossless trim using stream copy
        ffmpeg.input(video_path, t=last_speech_end).output(output_path, c="copy").run(quiet=True, overwrite_output=True)
        return output_path
```

---

## 3. Backend API Endpoints (FastAPI)

```python
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
import shutil, os

app = FastAPI()

@app.post("/tools/trim-to-speech")
async def trim_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    padding: float = Form(0.3)
):
    # Save input
    tmp_input = f"tmp_{file.filename}"
    with open(tmp_input, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    trimmer = SpeechTrimmer()
    trimmed_path = trimmer.trim_to_speech_end(tmp_input, padding=padding)
    
    # Cleanup task
    def cleanup(paths):
        for p in paths:
            if os.path.exists(p): os.remove(p)
            
    background_tasks.add_task(cleanup, [tmp_input, trimmed_path])
    
    return FileResponse(trimmed_path, filename=f"trimmed_{file.filename}")
```

---

## 4. Premium Frontend Interface (React/Next.js)

Uses **Lucide-react** for icons and **Tailwind CSS** for styling.

```tsx
import { useState, useRef } from 'react';
import { Upload, Scissors, Download, AudioWaveform, Loader2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, Button } from '@/components/ui';

export default function ClipTrimmer() {
    const [file, setFile] = useState<File | null>(null);
    const [isTrimming, setIsTrimming] = useState(false);
    const [trimmedUrl, setTrimmedUrl] = useState<string | null>(null);

    const handleTrim = async () => {
        if (!file) return;
        setIsTrimming(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/tools/trim-to-speech', {
                method: 'POST',
                body: formData
            });
            
            const blob = await response.blob();
            setTrimmedUrl(URL.createObjectURL(blob));
        } finally {
            setIsTrimming(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto p-6 space-y-6">
            <Card className="border-primary/20 shadow-lg">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Scissors className="h-5 w-5 text-primary" />
                        Smart Clip Trimmer
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Upload Section */}
                    <div className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer hover:bg-primary/5">
                        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="hidden" id="upload" />
                        <label htmlFor="upload" className="cursor-pointer flex flex-col items-center">
                            <Upload className="h-10 w-10 text-muted-foreground mb-2" />
                            <span className="font-medium">{file ? file.name : "Choose Video"}</span>
                        </label>
                    </div>

                    <Button onClick={handleTrim} disabled={!file || isTrimming} className="w-full">
                        {isTrimming ? <Loader2 className="animate-spin mr-2" /> : <Scissors className="mr-2" />}
                        Process & Trim Clip
                    </Button>

                    {trimmedUrl && (
                        <div className="pt-4 border-t space-y-4">
                            <video src={trimmedUrl} controls className="w-full rounded-lg shadow-md" />
                            <Button asChild className="w-full bg-green-600">
                                <a href={trimmedUrl} download="trimmed_video.mp4">
                                    <Download className="mr-2" /> Download Result
                                </a>
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
```
