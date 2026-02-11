
import sys
try:
    print(f"EXE: {sys.executable}")
    import imageio_ffmpeg
    print(f"SUCCESS: {imageio_ffmpeg.__file__}")
except ImportError as e:
    print(f"FAIL: {e}")
except Exception as e:
    print(f"ERR: {e}")
