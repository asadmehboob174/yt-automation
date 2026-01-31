FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install playwright && playwright install chromium --with-deps

WORKDIR /app

# Copy application code
COPY apps/api .

# Copy packages
COPY packages /packages

# Install dependencies (requires pyproject.toml and source code)
RUN pip install -e .

# Setup Prisma
COPY prisma/schema.prisma /app/prisma/schema.prisma
# Remove Windows-specific output path for Docker build
RUN sed -i '/output   = "\.\.\/\.venv/d' /app/prisma/schema.prisma
RUN prisma generate --schema=/app/prisma/schema.prisma

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
