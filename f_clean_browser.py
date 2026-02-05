
import os
import shutil
import time
import subprocess
import signal

PROFILE_DIR = r"C:\Users\pc\.whisk-profile"

def kill_chrome():
    print("🔪 Killing Chrome processes...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1) # Wait for death
    except Exception as e:
        print(f"Error killing chrome: {e}")

def clean_locks():
    print("🧹 Cleaning lock files...")
    locks = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock in locks:
        path = os.path.join(PROFILE_DIR, lock)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"✅ Removed {lock}")
            except Exception as e:
                print(f"❌ Failed to remove {lock}: {e}")
        else:
            print(f"ℹ️ {lock} not found")

def main():
    kill_chrome()
    clean_locks()
    print("✨ Browser profile cleanup complete.")

if __name__ == "__main__":
    main()
