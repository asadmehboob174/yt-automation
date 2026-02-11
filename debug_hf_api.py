import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_endpoint(name, url, token):
    print(f"\n[{name}]")
    print(f"URL: {url}")
    headers = {"Authorization": f"Bearer {token}"}
    if "/v1/chat/completions" in url:
        headers["Content-Type"] = "application/json"
        payload = {"model": "Qwen/Qwen2.5-7B-Instruct", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}
    else:
        payload = {"inputs": "A beautiful sunset"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Exception: {e}")

async def main():
    token = os.getenv("HF_TOKEN")
    
    # 1. Chat Completion (The one causing the error for the user)
    await test_endpoint("Chat current", "https://router.huggingface.co/v1/chat/completions", token)
    await test_endpoint("Chat alt 1", "https://api-inference.huggingface.co/v1/chat/completions", token)
    await test_endpoint("Chat alt 2", "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct/v1/chat/completions", token)

    # 2. Image (PuLID)
    pulid = "InstantX/PuLID-FLUX-v1"
    await test_endpoint("PuLID current", f"https://router.huggingface.co/hf-inference/models/{pulid}", token)
    await test_endpoint("PuLID alt 1", f"https://api-inference.huggingface.co/models/{pulid}", token)
    
    # 3. Image (SDXL)
    sdxl = "stabilityai/stable-diffusion-xl-base-1.0"
    await test_endpoint("SDXL current", f"https://router.huggingface.co/hf-inference/models/{sdxl}", token)
    await test_endpoint("SDXL alt 1", f"https://api-inference.huggingface.co/models/{sdxl}", token)

if __name__ == "__main__":
    asyncio.run(main())
