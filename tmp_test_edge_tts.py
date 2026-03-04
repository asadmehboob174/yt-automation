import sys
import asyncio
from pathlib import Path
import edge_tts

# Add project root to path
sys.path.insert(0, str(Path(r'd:\GitHub\yt-automation')))

async def list_voices():
    voices = await edge_tts.list_voices()
    for v in voices:
        if v['Locale'].startswith('ur'):
            print(f"Urdu Voice: {v['ShortName']}, Gender: {v['Gender']}")

async def test_urdu():
    text = "رنگوں اور روشنیوں سے سجی ہوئی پریوں کی دلکش دنیا"
    voice = "ur-PK-UzmaNeural" # Let's assume this exists based on standard Azure voices
    
    print(f"Testing {voice} with text: {text}")
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save("test_urdu.mp3")
        print("Success! Created test_urdu.mp3")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(list_voices())
    asyncio.run(test_urdu())
