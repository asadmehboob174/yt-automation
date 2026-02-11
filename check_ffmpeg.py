
try:
    import imageio_ffmpeg
    print(f"FOUND: {imageio_ffmpeg.get_ffmpeg_exe()}")
except ImportError:
    print("NOT FOUND")
