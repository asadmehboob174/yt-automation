
import os
import shutil
import time
import subprocess
import datetime

PROFILE_DIR = r"C:\Users\pc\.whisk-profile"

def kill_chrome():
    print("🔪 Killing all Chrome processes...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

def reset_profile():
    if not os.path.exists(PROFILE_DIR):
        print("ℹ️ No profile directory found to reset.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{PROFILE_DIR}_backup_{timestamp}"
    
    print(f"📦 Backing up corrupted profile to: {backup_name}")
    try:
        os.rename(PROFILE_DIR, backup_name)
        print("✅ Profile successfully reset!")
    except Exception as e:
        print(f"❌ Failed to rename profile: {e}")
        # Try copy-delete fallback if rename fails (e.g. cross-device)
        try:
            print("⏳ Attempting copy-delete fallback...")
            shutil.copytree(PROFILE_DIR, backup_name)
            shutil.rmtree(PROFILE_DIR)
            print("✅ Profile successfully reset (via copy-delete)!")
        except Exception as e2:
             print(f"❌ Critical Failure: {e2}")

if __name__ == "__main__":
    kill_chrome()
    reset_profile()
