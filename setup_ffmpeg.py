
import os
import shutil
import imageio_ffmpeg
import sys

# Get the source executable
src_exe = imageio_ffmpeg.get_ffmpeg_exe()
print(f"Found imageio-ffmpeg at: {src_exe}")

# Create a 'bin' directory in .venv
venv_base = os.path.dirname(os.path.dirname(sys.executable)) # .venv usually
bin_dir = os.path.join(venv_base, "bin")

if not os.path.exists(bin_dir):
    os.makedirs(bin_dir)
    print(f"Created bin dir: {bin_dir}")

# Destination paths
dest_ffmpeg = os.path.join(bin_dir, "ffmpeg.exe")

# Copy
try:
    shutil.copy2(src_exe, dest_ffmpeg)
    print(f"✅ Copied to: {dest_ffmpeg}")
except Exception as e:
    print(f"Failed to copy: {e}")

# Verify
if os.path.exists(dest_ffmpeg):
    print("Verification successful.")
    
    # Also verify PATH injection for current process
    os.environ["PATH"] += os.pathsep + bin_dir
    import subprocess
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        print("Test Run Output (First line):")
        print(res.stdout.split('\n')[0])
    except Exception as e:
        print(f"Test run failed: {e}")
else:
    print("Verification failed.")
