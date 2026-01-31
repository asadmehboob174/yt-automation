import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    with httpx.Client() as client:
        response = client.get(url)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            models = response.json().get('models', [])
            for model in models:
                print(f"- {model['name']}")
        else:
            print(response.text)
except Exception as e:
    print(f"Error: {e}")
