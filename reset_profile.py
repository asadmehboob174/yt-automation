import shutil
from pathlib import Path
import os
import time

def reset_profile():
    profile_path = Path.home() / ".whisk-profile"
    backup_path = Path.home() / f".whisk-profile.bak_{int(time.time())}"
    
    if profile_path.exists():
        try:
            print(f"🔄 Renaming {profile_path} to {backup_path}...")
            shutil.move(str(profile_path), str(backup_path))
            print("✅ Profile reset successful.")
        except Exception as e:
            print(f"❌ Failed to reset profile: {e}")
    else:
        print("ℹ️ No existing profile to reset.")

if __name__ == "__main__":
    reset_profile()
