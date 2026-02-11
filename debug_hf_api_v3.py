import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_endpoint(name, url, token):
    print(f"--- {name} ---")
    headers = {"Authorization": f"Bearer {token}"}
    # Simple test for image models - just checking if we can reach the model
    # We won't send a full payload, just a HEAD or a minimal POST to check auth
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # POST with empty body might give 400 but auth should be 200 or 400 (not 403)
            resp = await client.post(url, headers=headers, json={"inputs": "test"})
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
        except Exception as e:
            print(f"Exception: {e}")

async def main():
    token = os.getenv("HF_TOKEN")
    
    # PULID
    m_pulid = "InstantX/PuLID-FLUX-v1"
    await test_endpoint("PuLID Router", f"https://router.huggingface.co/hf-inference/models/{m_pulid}", token)
    await test_endpoint("PuLID Direct", f"https://api-inference.huggingface.co/models/{m_pulid}", token)

if __name__ == "__main__":
    asyncio.run(main())
