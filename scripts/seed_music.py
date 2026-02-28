import asyncio
import os
from prisma import Prisma

async def seed_music():
    db = Prisma()
    await db.connect()

    # Kevin MacLeod (incompetech.com) - Licensed under Creative Commons: By Attribution 4.0 License
    music_data = [
        # --- Cartoon / Playful ---
        {"category": "Cartoon", "name": "Hidden Agenda", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hidden%20Agenda.mp3"},
        {"category": "Cartoon", "name": "Sneaky Snitch", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sneaky%20Snitch.mp3"},
        {"category": "Cartoon", "name": "Fluffing a Duck", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Fluffing%20a%20Duck.mp3"},
        {"category": "Cartoon", "name": "If I Had a Chicken", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/If%20I%20Had%20a%20Chicken.mp3"},
        {"category": "Cartoon", "name": "Merry Go Slower", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Merry%20Go%20Slower.mp3"},
        {"category": "Cartoon", "name": "Pixelland", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Pixelland.mp3"},
        {"category": "Cartoon", "name": "Gaslamp Funworks", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gaslamp%20Funworks.mp3"},
        {"category": "Cartoon", "name": "Run Amok", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Run%20Amok.mp3"},
        {"category": "Cartoon", "name": "Investigations", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Investigations.mp3"},
        {"category": "Cartoon", "name": "Hamster March", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hamster%20March.mp3"},

        # --- Ghibli Cozy / Calm piano ---
        {"category": "Ghibli Cozy", "name": "Living Voyage", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Living%20Voyage.mp3"},
        {"category": "Ghibli Cozy", "name": "Windswept", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Windswept.mp3"},
        {"category": "Ghibli Cozy", "name": "Fairytale Waltz", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Fairytale%20Waltz.mp3"},
        {"category": "Ghibli Cozy", "name": "Midsummer Sky", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Midsummer%20Sky.mp3"},
        {"category": "Ghibli Cozy", "name": "Almost in F - Tranquility", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Almost%20in%20F%20-%20Tranquility.mp3"},
        {"category": "Ghibli Cozy", "name": "Heart of Nowhere", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heart%20of%20Nowhere.mp3"},
        {"category": "Ghibli Cozy", "name": "Pastoral", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Pastoral.mp3"},
        {"category": "Ghibli Cozy", "name": "Ethereal Relaxing", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ethereal%20Relaxing.mp3"},
        {"category": "Ghibli Cozy", "name": "Ever Mindful", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ever%20Mindful.mp3"},
        {"category": "Ghibli Cozy", "name": "Peace of Mind", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Peace%20of%20Mind.mp3"},

        # --- Epic / Action ---
        {"category": "Epic", "name": "Curse of the Scarab", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Curse%20of%20the%20Scarab.mp3"},
        {"category": "Epic", "name": "Volatile Reaction", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3"},
        {"category": "Epic", "name": "Movement Proposition", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Movement%20Proposition.mp3"},
        {"category": "Epic", "name": "Thunderbird", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Thunderbird.mp3"},
        {"category": "Action", "name": "Hitman", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hitman.mp3"},
        {"category": "Action", "name": "Future Gladiator", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Future%20Gladiator.mp3"},
        {"category": "Action", "name": "Decisions", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Decisions.mp3"},
        {"category": "Action", "name": "Heroic Age", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heroic%20Age.mp3"},
        {"category": "Action", "name": "The Descent", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Descent.mp3"},
        {"category": "Epic", "name": "Agnus Dei X", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Agnus%20Dei%20X.mp3"},

        # --- Cinematic / Dramatic ---
        {"category": "Cinematic", "name": "Heartbreaking", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3"},
        {"category": "Cinematic", "name": "Touching Moments Two", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Touching%20Moments%20Two%20-%20Higher.mp3"},
        {"category": "Cinematic", "name": "Somewhere Sunny", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Somewhere%20Sunny.mp3"},
        {"category": "Dramatic", "name": "Evening Fall Harp", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Evening%20Fall%20Harp.mp3"},
        {"category": "Dramatic", "name": "Hidden Past", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hidden%20Past.mp3"},
        {"category": "Dramatic", "name": "Oppressive Gloom", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Oppressive%20Gloom.mp3"},
        {"category": "Cinematic", "name": "Morning Cruise", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Morning%20Cruise.mp3"},
        {"category": "Cinematic", "name": "On the Shore", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/On%20the%20Shore.mp3"},
        {"category": "Dramatic", "name": "Symmetry", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Symmetry.mp3"},
        {"category": "Cinematic", "name": "Dream Culture", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dream%20Culture.mp3"},

        # --- Happy / Upbeat ---
        {"category": "Happy", "name": "Wallpaper", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3"},
        {"category": "Happy", "name": "Life of Riley", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Life%20of%20Riley.mp3"},
        {"category": "Happy", "name": "Easy Lemon", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Easy%20Lemon.mp3"},
        {"category": "Happy", "name": "Scheming Weasel", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Scheming%20Weasel%20(faster).mp3"},
        {"category": "Upbeat", "name": "Monkeys Spinning Monkeys", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Monkeys%20Spinning%20Monkeys.mp3"},
        {"category": "Upbeat", "name": "Carefree", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3"},
        {"category": "Upbeat", "name": "Bright Wish", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Bright%20Wish.mp3"},
        {"category": "Happy", "name": "Hyperfun", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hyperfun.mp3"},
        {"category": "Happy", "name": "Daily Beetle", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Daily%20Beetle.mp3"},
        {"category": "Happy", "name": "Malt Shop Bop", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Malt%20Shop%20Bop.mp3"},

        # --- Horror / Scary ---
        {"category": "Horror", "name": "The Hive", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Hive.mp3"},
        {"category": "Horror", "name": "Gathering Darkness", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gathering%20Darkness.mp3"},
        {"category": "Scary", "name": "Giant Wyrm", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Giant%20Wyrm.mp3"},
        {"category": "Scary", "name": "Unseen Horrors", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Unseen%20Horrors.mp3"},
        {"category": "Horror", "name": "Phantasm", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Phantasm.mp3"},
        {"category": "Horror", "name": "Echoes of Time", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Echoes%20of%20Time.mp3"},
        {"category": "Scary", "name": "Malicious", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Malicious.mp3"},
        {"category": "Scary", "name": "Aftermath", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Aftermath.mp3"},
        {"category": "Horror", "name": "Ghost Story", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ghost%20Story.mp3"},
        {"category": "Horror", "name": "Anxiety", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Anxiety.mp3"},

        # --- Calm / Relaxing ---
        {"category": "Calm", "name": "Clear Waters", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clear%20Waters.mp3"},
        {"category": "Calm", "name": "Porch Swing Days", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Porch%20Swing%20Days%20-%20slower.mp3"},
        {"category": "Relaxing", "name": "Gymnopedie No 1", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gymnopedie%20No%201.mp3"},
        {"category": "Relaxing", "name": "Clean Soul", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clean%20Soul.mp3"},
        {"category": "Calm", "name": "Windy Shores", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Windy%20Shores.mp3"},
        {"category": "Calm", "name": "Silver Flame", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Silver%20Flame.mp3"},
        {"category": "Relaxing", "name": "Luminous Rain", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Luminous%20Rain.mp3"},
        {"category": "Relaxing", "name": "Relaxing Piano Music", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Relaxing%20Piano%20Music.mp3"},
        {"category": "Calm", "name": "Inner Light", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Inner%20Light.mp3"},
        {"category": "Calm", "name": "Meditation", "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%201.mp3"},

    ]

    print(f"🌱 Seeding {len(music_data)} background music tracks...")
    
    # Clear existing to avoid duplicates if re-running
    #await db.backgroundmusic.delete_many()
    
    for track in music_data:
        # Check if exists
        exists = await db.backgroundmusic.find_first(where={"name": track["name"]})
        if not exists:
            await db.backgroundmusic.create(data=track)
            print(f"   ✅ Added: {track['name']} ({track['category']})")
        else:
            print(f"   ⏩ Skipping: {track['name']} (already exists)")

    await db.disconnect()
    print("✨ Seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_music())
