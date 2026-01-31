
character_images = [
    {"name": "Lion", "imageUrl": "http://lion.png"},
    {"name": "Cat", "imageUrl": "http://cat.png"}
]

prompts = [
    "A majestic Lion stands on a rock.",
    "The cute Cat sleeps on a pillow.",
    "A random elephant walks by.",
    "The lion and the cat play together."
]

def check(prompt):
    matches = []
    for char in character_images:
        if char.get("name", "").lower() in prompt.lower():
            matches.append(char)
    
    if len(matches) > 0:
        print(f"Prompt: '{prompt}' -> Matched: {matches[0]['name']}")
    else:
        print(f"Prompt: '{prompt}' -> No match")

for p in prompts:
    check(p)
