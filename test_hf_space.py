import asyncio
from gradio_client import Client
import os
from dotenv import load_dotenv

load_dotenv(".env")
hf_token = os.getenv("HF_TOKEN")

spaces_to_test = [
    "r3gm/Video-Upscaler",
    "tggtg/AI-Video-Enhancer-4K",
    "raju014/Video-Upscaler-4K",
]

def test_space(space_id):
    try:
        print(f"Testing space: {space_id}...")
        client = Client(space_id, hf_token) # try positional or token=hf_token
        endpoints = client.view_api(return_format="dict")
        print(f"✅ Successfully connected to {space_id}")
        print(endpoints)
        return True
    except Exception as e:
        print(f"❌ Failed to connect to {space_id}: {e}")
        return False

for space in spaces_to_test:
    test_space(space)
