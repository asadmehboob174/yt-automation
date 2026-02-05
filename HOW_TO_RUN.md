# 🚀 AI Video Factory - Local Setup Guide

Follow these steps to set up the project on a new Windows machine.

## 🛠️ Prerequisites (Install First)
1.  **Python 3.10+**: [Download Here](https://www.python.org/downloads/) (Check "Add Python to PATH" during install).
2.  **Node.js (LTS)**: [Download Here](https://nodejs.org/).
3.  **Git**: [Download Here](https://git-scm.com/downloads).
4.  **FFmpeg**: 
    *   Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (essentials build).
    *   Extract the folder.
    *   Add the `bin` folder path (e.g., `C:\ffmpeg\bin`) to your System Environment Variables -> Path.
    *   Verify by running `ffmpeg -version` in a new terminal.

## 📥 1. Clone & Setup
Open your terminal (PowerShell or Git Bash) where you want the project:

```powershell
# Clone the repository
git clone https://github.com/asadmehboob174/yt-automation.git
cd yt-automation

# Copy environment variables
cp .env.example .env
# NOTE: You MUST edit .env and fill in your keys (HUGGINGFACE_TOKEN, R2_KEYS, DATABASE_URL etc)
```

## 🐍 2. Backend Setup (Python)

```powershell
# Create a virtual environment
python -m venv .venv

# Activate it (Windows)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (Required for Grok/Whisk)
playwright install
```

## ⚛️ 3. Frontend Setup (Node.js/Next.js)

```powershell
# Install Node dependencies
npm install

# Generate Prisma Client (if using DB)
npx prisma generate
```

## 🚀 4. Running the App

### Option A: Run Everything (Recommended)
Open one terminal and run:
```powershell
npm run dev
```
*(This uses TurboRepo to start both API and Web)*

### Option B: Run Separately (If Turbo issues)
**Terminal 1 (Backend):**
```powershell
.\.venv\Scripts\Activate.ps1
python serve.py
```

**Terminal 2 (Frontend):**
```powershell
npm run dev --filter=web
```

---

## 🔑 5. Login Scripts (First Time Only)
You need to authenticate the AI agents.

**Terminal 1 (Backend Active):**
```powershell
# Login to Grok
python auth_grok.py

# Login to Google Whisk
python auth_whisk_v2.py
```
