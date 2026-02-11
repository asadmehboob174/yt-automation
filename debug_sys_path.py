
import sys
import os
print("Python Executable:", sys.executable)
print("Sys Path:")
for p in sys.path:
    print(f" - {p}")

try:
    import imageio_ffmpeg
    print("Succcess!")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
