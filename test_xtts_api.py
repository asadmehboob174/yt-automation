
from gradio_client import Client
import sys

def test_space():
    name = "capleaf/VIZ-XTTS-2"
    print(f"Testing connectivity to {name}...")
    try:
        client = Client(name)
        print("✅ Successfully connected!")
        print("\nAPI Outline:")
        # This will list available endpoints and their signatures
        client.view_api()
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    test_space()
