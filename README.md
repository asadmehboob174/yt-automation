# AI Video Factory - Startup Guide

Follow these steps to run the complete system locally.

## Prerequisites
- **Node.js** 18+
- **Python** 3.12+
- **Docker Desktop** (for Inngest)
- **Postgres Database** (Neon or local)

## 1. Environment Setup
Ensure you have a `.env` file in the root directory with all required keys (see `.env.example`).

## 2. Install Dependencies

### Frontend (Node.js)
```bash
npm install
```

### Backend (Python)
It's recommended to use a virtual environment.
```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies (including Prisma)
pip install -r packages/services/requirements.txt
# Note: Since we don't have a single requirements.txt yet, install the core ones:
pip install fastapi uvicorn prisma httpx boto3 playwright playwright-stealth ffmpeg-python edge-tts google-generativeai google-api-python-client google-auth-oauthlib inngest
```

## 3. Database Setup (Prisma)
Initialize the database and client:
```bash
# Generate Prisma Client (Node & Python)
npx prisma generate

# Run Migrations (if not done)
npx prisma migrate dev

# Seed Database (optional, if you haven't seeded channels yet)
npx tsx packages/database/seed.ts
```

## 4. Running the System (3 Terminals)

You need to run these in separate terminals:

### Terminal 1: Inngest (Background Jobs)
```bash
docker-compose up
```
*   Inngest Dashboard: `http://localhost:8288`

### Terminal 2: Backend API
```bash
# Set PYTHONPATH to root so it can find 'apps' and 'packages'
$env:PYTHONPATH="."
python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```
*   API Docs: `http://localhost:8000/docs`

### Terminal 3: Frontend Dashboard
```bash
cd apps/web
npm run dev
```
*   **Dashboard**: `http://localhost:3000`

## 5. Verification
1.  Open `http://localhost:3000`.
2.  Go to **Channels** tab. You should see "Pets", "History", "Sci-Fi".
3.  Go to **Script Editor**, enter a topic, and click "Generate".

## Troubleshooting
*   **Prisma Client Error**: Run `npx prisma generate` and `prisma generate` (python).
*   **Missing Modules**: Ensure your `PYTHONPATH` includes the root directory or run python with `PYTHONPATH=.`
    ```bash
    $env:PYTHONPATH="."
    python -m uvicorn apps.api.main:app --reload
    ```
