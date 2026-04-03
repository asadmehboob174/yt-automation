
import asyncio
import os
import json
from pathlib import Path
from packages.services.cloudflare_ai import CloudflareImageGenerator

async def test_budget_safeguard():
    usage_file = Path("tmp") / "cf_usage.json"
    
    print("🛡️ Testing Cloudflare Budget Safeguard...")
    
    # Mock usage: 2000 images today (well past free tier, costing > $3)
    mock_usage = {
        "daily": {"2026-04-03": 2000},
        "paid_neurons": 400000 # 400k neurons = (~$4.40)
    }
    
    usage_file.parent.mkdir(parents=True, exist_ok=True)
    usage_file.write_text(json.dumps(mock_usage))
    print(f"✅ Mocked usage created in {usage_file}")

    try:
        gen = CloudflareImageGenerator()
        print("📸 Attempting generation with exceeded budget...")
        await gen.generate("test prompt")
        print("❌ Error: Generation should have been blocked!")
    except RuntimeError as e:
        print(f"🎯 SUCCESS: Blocked as expected. Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
    
    # Cleanup
    if usage_file.exists():
        usage_file.unlink()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_budget_safeguard())
