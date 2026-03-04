import os
import requests
from dotenv import load_dotenv

load_dotenv('d:/GitHub/yt-automation/.env')
api_key = os.getenv('ELEVENLABS_API_KEY')

headers = {'xi-api-key': api_key}
response = requests.get('https://api.elevenlabs.io/v1/voices', headers=headers)

if response.status_code == 200:
    voices = response.json().get('voices', [])
    print("✨ FREE TIER PREMADE FEMALE VOICES:")
    for v in voices:
        if v.get('category') == 'premade':
            labels = v.get('labels', {})
            if labels.get('gender') == 'female':
                print(f"- {v['name']} ({labels.get('accent', 'Unknown')} {labels.get('age', '')}): {v['voice_id']}")
else:
    print('Failed', response.text)
