
import os
import httpx
import logging
import asyncio
import time
from typing import Optional

logger = logging.getLogger(__name__)

class KaggleController:
    """
    Manages the lifecycle of a remote Kaggle GPU notebook (Kernel).
    Ensures the Ngrok tunnel is alive and restarts the session if needed.
    """

    def __init__(self):
        self.username = os.getenv("KAGGLE_USERNAME")
        self.key = os.getenv("KAGGLE_KEY")
        self.ngrok_domain = os.getenv("KAGGLE_NGROK_DOMAIN")
        self.kernel_slug = os.getenv("KAGGLE_KERNEL_SLUG") # e.g. asad174mehboob/comfyui-server
        
        # Ngrok URL for health check
        if self.ngrok_domain and not self.ngrok_domain.startswith("http"):
            self.health_url = f"https://{self.ngrok_domain}/health"
        else:
            self.health_url = f"{self.ngrok_domain}/health" if self.ngrok_domain else None

    async def is_alive(self) -> bool:
        """Pings the Ngrok static domain to check if the ComfyUI server is reachable."""
        if not self.health_url:
            return False
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_url)
                # Successful /health check returned from our custom Flask wrapper
                return response.status_code == 200
        except Exception:
            return False

    async def ensure_running(self, wait_seconds: int = 300) -> bool:
        """
        Checks if the server is alive. If not, restarts it and waits for boot.
        Called automatically by KaggleImageGenerator before every generation.
        """
        if await self.is_alive():
            return True
            
        logger.warning("🏔️ Kaggle backend is offline. Attempting to wake it up...")
        
        # Try to restart the session
        try:
            success = await self.restart_session()
            if not success:
                logger.error("❌ Failed to push restart command to Kaggle API.")
                return False
                
            # Wait loop: poll for life every 15 seconds up to wait_seconds
            logger.info(f"⏳ Waiting up to {wait_seconds}s for Kaggle + ComfyUI to boot...")
            start_time = time.time()
            while time.time() - start_time < wait_seconds:
                if await self.is_alive():
                    logger.info("✅ Kaggle server is LIVE! Resuming operations.")
                    return True
                await asyncio.sleep(15)
                
            logger.error("❌ Kaggle server failed to boot within time limit.")
            return False
            
        except Exception as e:
            logger.error(f"❌ Critical error in Kaggle Controller: {e}")
            return False

    async def restart_session(self) -> bool:
        """
        Uses the Kaggle API to push/start the kernel.
        Requires 'kaggle' package and KAGGLE_USERNAME / KAGGLE_KEY env set.
        """
        if not self.username or not self.key or not self.kernel_slug:
            logger.error("❌ Missing Kaggle credentials or slug for restart.")
            return False

        # Set environment variables for the Kaggle library
        os.environ["KAGGLE_USERNAME"] = self.username
        os.environ["KAGGLE_KEY"] = self.key
        
        try:
            # We use subprocess to call the 'kaggle' CLI since it's easier 
            # to handle 'kernels pull/push' this way.
            # 1. We create a temporary metadata file and push it
            # Or simpler: just use 'kaggle kernels push' if we have a local copy of the script.
            # For our factory, we'll keep a master copy of the server script.
            
            logger.info(f"🚀 Pushing kernel restart for {self.kernel_slug}...")
            
            # The Kaggle CLI requires a folder with kernel-metadata.json
            # Let's create a temporary structure for pushing
            import tempfile
            import json
            from pathlib import Path
            
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                
                # Create metadata
                metadata = {
                    "id": self.kernel_slug,
                    "title": "ComfyUI Server",
                    "code_file": "server.py",
                    "language": "python",
                    "kernel_type": "script",
                    "is_private": "true",
                    "enable_gpu": "true",
                    "enable_tpu": "false",
                    "enable_internet": "true",
                    "dataset_sources": [],
                    "competition_sources": [],
                    "kernel_sources": [],
                    "model_sources": []
                }
                
                (tmp_path / "kernel-metadata.json").write_text(json.dumps(metadata))
                
                # Copy the server script and workflow JSON from our project
                server_source = Path("scripts/kaggle_comfyui_server.py")
                workflow_source = Path("scripts/comfyui_workflow.json")
                
                if not server_source.exists() or not workflow_source.exists():
                    logger.error(f"❌ Missing server source: {server_source} or {workflow_source}")
                    return False
                
                (tmp_path / "server.py").write_text(server_source.read_text())
                (tmp_path / "comfyui_workflow.json").write_text(workflow_source.read_text())
                
                # Execute push
                import subprocess
                result = subprocess.run(
                    ["kaggle", "kernels", "push", "-p", str(tmp_path)],
                    capture_output=True, text=True, check=True
                )
                
                logger.debug(f"Kaggle API Output: {result.stdout}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Kaggle API restart failed: {e}")
            return False

# Singleton instance
kaggle_controller = KaggleController()
