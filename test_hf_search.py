import requests

url = "https://huggingface.co/api/spaces?search=video%20upscale&sort=likes&direction=-1&limit=5"
response = requests.get(url)
print("\n--- Video Upscale Spaces ---")
for s in response.json(): print(f"{s['id']} (Likes: {s.get('likes')})")

url = "https://huggingface.co/api/spaces?search=video%20enhancer&sort=likes&direction=-1&limit=5"
response = requests.get(url)
print("\n--- Video Enhancer Spaces ---")
for s in response.json(): print(f"{s['id']} (Likes: {s.get('likes')})")
