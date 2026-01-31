---
description: How to run the full development environment for AI Video Factory
---

# Development Environment Setup

This workflow guides you through setting up and running the complete AI Video Factory development environment.

## Prerequisites

Before starting, ensure you have:
- Docker Desktop installed and running
- Node.js 18+ installed
- Python 3.10+ installed
- Required API keys (see Environment Variables below)

## Environment Variables

Create a `.env` file in the project root with:

```env
# Database
DATABASE_URL="postgresql://..."

# AI Services
GEMINI_API_KEY="your-gemini-api-key"
HF_TOKEN="your-huggingface-pro-token"

# Cloud Storage
R2_ACCESS_KEY_ID="your-r2-access-key"
R2_SECRET_ACCESS_KEY="your-r2-secret"
R2_ENDPOINT="https://xxx.r2.cloudflarestorage.com"
R2_BUCKET="video-factory"

# Background Jobs
INNGEST_EVENT_KEY="local-dev-key"
INNGEST_SIGNING_KEY="local-dev-signing-key"

# YouTube (optional for development)
GOOGLE_CLIENT_SECRETS_PATH="./secrets/client_secrets.json"

# Grok (optional)
GROK_HEADLESS="false"
```

## Step 1: Start Docker Services

// turbo
```bash
docker-compose up --build
```

This starts:
- Inngest dev server on port 8288
- API server on port 8000

## Step 2: Start the Frontend

Open a new terminal and run:

// turbo
```bash
cd apps/web && npm run dev
```

The dashboard will be available at http://localhost:3000

## Step 3: Run Database Migrations

If this is the first run, push the schema:

// turbo
```bash
cd packages/database && npx prisma db push
```

## Step 4: Verify Services

Check that all services are healthy:

// turbo
```bash
curl http://localhost:8000/health/full
```

All checks should show `"healthy": true`

## Development URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Inngest | http://localhost:8288 |

## Common Commands

### Generate Prisma Client
```bash
cd packages/database && npx prisma generate
```

### Run Tests
```bash
pytest tests/test_integration.py -v
```

### Check R2 Storage Usage
```bash
curl http://localhost:8000/storage/stats
```

### View Job Status
```bash
curl http://localhost:8000/jobs
```

## Troubleshooting

### Database Connection Failed
- Ensure DATABASE_URL is correct
- Check that Postgres is running

### HuggingFace Rate Limited
- Check quota at https://huggingface.co/settings/billing
- Wait for quota reset (usually midnight UTC)

### Grok Not Working
- Login to x.com manually first with `GROK_HEADLESS=false`
- Profile is saved at `~/.grok-profiles/default`
