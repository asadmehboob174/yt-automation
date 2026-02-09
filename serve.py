import asyncio
import sys
import uvicorn
import os

if __name__ == "__main__":
    # CRITICAL: Set ProactorEventLoopPolicy on Windows to support Playwright subprocesses
    if sys.platform == 'win32':
        print("SETTING WindowsProactorEventLoopPolicy for Playwright support...")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Note: Reload MUST be False on Windows + Playwright because the reloader subprocess 
    # doesn't inherit the ProactorEventLoopPolicy correctly.
    uvicorn.run(
        "apps.api.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False,  # <--- CRITICAL: Must be False for Playwright
        log_level="info"
    )
