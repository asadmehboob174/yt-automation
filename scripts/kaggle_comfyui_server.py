# --- KAGGLE SELF-CONTAINED COMFYUI SERVER (Final All-in-One) ---
import os
import subprocess
import threading
import time
import requests
import json
from flask import Flask, request, jsonify, send_file
import io

app = Flask(__name__)

# 1. Configuration - UPDATED WITH YOUR DOMAIN
NGROK_DOMAIN = "gaylord-swingable-belva.ngrok-free.dev"
NGROK_AUTH_TOKEN = "3BszoOagywOIKtyxh3yhYBoYAEn_4vgcNN57LRTjKvNBvwQYS"
COMFYUI_PORT = 8188

# --- EMBEDDED WORKFLOW JSON (SDXL Lightning + IP-Adapter) ---
# This eliminates the "FileNotFoundError" by keeping the logic inside the script.
COMFYUI_WORKFLOW = {
  "3": {
    "inputs": {
      "seed": 42, "steps": 4, "cfg": 1, "sampler_name": "euler", "scheduler": "sgm_uniform", "denoise": 1,
      "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]
    },
    "class_type": "KSampler"
  },
  "4": {
    "inputs": {"ckpt_name": "sdxl_lightning_4step_single_ckpt.safetensors"},
    "class_type": "CheckpointLoaderSimple"
  },
  "5": {
    "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
    "class_type": "EmptyLatentImage"
  },
  "6": {
    "inputs": {"text": "hyper-realistic cinematic shot", "clip": ["11", 0]},
    "class_type": "CLIPTextEncode"
  },
  "7": {
    "inputs": {"text": "text, watermark, low quality, blurry, deformed", "clip": ["4", 1]},
    "class_type": "CLIPTextEncode"
  },
  "8": {
    "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    "class_type": "VAEDecode"
  },
  "9": {
    "inputs": {"filename_prefix": "KaggleGen", "images": ["8", 0]},
    "class_type": "SaveImage"
  },
  "10": {
    "inputs": {"image": "reference.png", "upload": "image"},
    "class_type": "LoadImage"
  },
  "11": {
    "inputs": {
      "weight": 0.8, "weight_type": "linear", "combine_embeds": "concat", "start_at": 0, "end_at": 1,
      "embeds_scaling": "V only", "model": ["4", 0], "ipadapter": ["12", 0], "image": ["13", 0]
    },
    "class_type": "IPAdapterAdvanced"
  },
  "12": {
    "inputs": {"ipadapter_name": "ip-adapter-plus_sdxl_vit-h.safetensors"},
    "class_type": "IPAdapterLoader"
  },
  "13": {
    "inputs": {"clip_name": "model.safetensors"},
    "class_type": "CLIPVisionLoader"
  }
}

def run_command(cmd):
    print(f"🚀 Executing: {cmd}")
    return subprocess.run(cmd, shell=True)

def setup_comfyui():
    print("📦 Setting up ComfyUI and Dependencies...")
    if not os.path.exists("ComfyUI"):
        run_command("git clone https://github.com/comfyanonymous/ComfyUI")
        os.chdir("ComfyUI")
        run_command("pip install -r requirements.txt")
        run_command("pip install xformers pyngrok flask")
        
        # Install Nodes
        os.makedirs("custom_nodes", exist_ok=True)
        os.chdir("custom_nodes")
        run_command("git clone https://github.com/ltdrdata/ComfyUI-Manager")
        run_command("git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus")
        os.chdir("../..")
    else:
        print("✅ ComfyUI directory already exists.")

    print("📥 Downloading AI Models (this takes 3-5 mins)...")
    models = {
        "ComfyUI/models/checkpoints": ["https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step_single_ckpt.safetensors"],
        "ComfyUI/models/ipadapter": ["https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"],
        "ComfyUI/models/clip_vision": ["https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors"]
    }
    
    for folder, urls in models.items():
        os.makedirs(folder, exist_ok=True)
        for url in urls:
            path = os.path.join(folder, url.split("/")[-1])
            if not os.path.exists(path):
                run_command(f"wget -O {path} {url}")

def start_comfyui():
    print("🔥 Starting ComfyUI Backend...")
    comfy_dir = os.path.abspath("ComfyUI")
    with open("comfyui.log", "w") as log_file:
        subprocess.Popen(
            ["python", "main.py", "--listen", "0.0.0.0", "--port", str(COMFYUI_PORT)], 
            cwd=comfy_dir,
            stdout=log_file, 
            stderr=log_file
        )
    print("✅ ComfyUI process initiated. View logs in 'comfyui.log'.")

def start_ngrok():
    print(f"🌐 Opening Tunnel to {NGROK_DOMAIN}...")
    from pyngrok import ngrok
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    try:
        tunnel = ngrok.connect(5000, "http", domain=NGROK_DOMAIN)
        print(f"✅ Tunnel Live: {tunnel.public_url}")
    except Exception as e:
        print(f"❌ Ngrok Error: {e}")

# --- API WRAPPER ---

@app.route('/health')
def health():
    try:
        res = requests.get(f"http://127.0.0.1:{COMFYUI_PORT}/history", timeout=2)
        return "OK", 200 if res.status_code == 200 else 503
    except:
        return "ComfyUI Booting...", 503

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    print(f"✨ Generating: {data.get('prompt', '')[:50]}...")
    
    # Use the embedded workflow
    import copy
    workflow = copy.deepcopy(COMFYUI_WORKFLOW)
    
    # Update params
    try:
        workflow["6"]["inputs"]["text"] = data.get("prompt", "")
        workflow["3"]["inputs"]["seed"] = data.get("seed", 42)
        workflow["5"]["inputs"]["width"] = data.get("width", 1024)
        workflow["5"]["inputs"]["height"] = data.get("height", 1024)
        
        ref_image_url = data.get("reference_image_url")
        if ref_image_url:
            img_res = requests.get(ref_image_url)
            os.makedirs("ComfyUI/input", exist_ok=True)
            with open("ComfyUI/input/reference.png", "wb") as f:
                f.write(img_res.content)
            workflow["10"]["inputs"]["image"] = "reference.png"
    except Exception as e:
        return jsonify({"error": f"Workflow prep error: {str(e)}"}), 500
    
    # Push to ComfyUI
    try:
        res = requests.post(f"http://127.0.0.1:{COMFYUI_PORT}/prompt", json={"prompt": workflow})
        prompt_id = res.json().get("prompt_id")
        
        # Poll for completion
        while True:
            h_res = requests.get(f"http://127.0.0.1:{COMFYUI_PORT}/history/{prompt_id}").json()
            if prompt_id in h_res:
                filename = h_res[prompt_id]["outputs"]["9"]["images"][0]["filename"]
                break
            time.sleep(1)
            
        return send_file(f"ComfyUI/output/{filename}", mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    setup_comfyui()
    start_comfyui()
    start_ngrok()
    print("🚀 API WRAPPER READY ON PORT 5000")
    app.run(port=5000, host="0.0.0.0")
