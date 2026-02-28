import asyncio
from gradio_client import Client
import os
from dotenv import load_dotenv

load_dotenv(".env")
hf_token = os.getenv("HF_TOKEN")

space_id = "tggtg/AI_Video_Enhancer_4K"
try:
    print(f"Connecting to {space_id}...")
    client = Client(space_id, token=hf_token)
    endpoints = client.view_api(return_format="dict")
    print("\nAPI ENDPOINTS:")
    for ep in endpoints['named_endpoints']:
        print(f"Endpoint: {ep}")
        print("Parameters:", endpoints['named_endpoints'][ep]['parameters'])
except Exception as e:
    import traceback
    traceback.print_exc()
