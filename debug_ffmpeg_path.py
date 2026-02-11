
import os
import sys
import imageio_ffmpeg

exe_path = imageio_ffmpeg.get_ffmpeg_exe()
print(f"Exec Path: {exe_path}")
print(f"Dir: {os.path.dirname(exe_path)}")
print(f"Exists: {os.path.exists(exe_path)}")

# List dir contents
try:
    print("Directory contents:")
    for f in os.listdir(os.path.dirname(exe_path)):
        print(f" - {f}")
except Exception as e:
    print(f"Error listing dir: {e}")
