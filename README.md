# SketchyAPI — Satire-as-a-Service

A FastAPI-powered API that transforms news articles into satirical comic strips, MAD Magazine style.

## Features

- **Article → Comic**: Submit a news article URL or text, get a multi-panel satirical comic
- **Async Processing**: Jobs are queued and processed by background workers
- **ComfyUI Integration**: AI image generation via Flux model
- **LLM Script Writing**: Pluggable backends (stub, OpenAI, Anthropic) for generating satirical scripts
- **Webhook Notifications**: Get notified when your comic is ready
- **API Key Auth**: Tiered rate limiting (free/pro/enterprise)

## Quick Start

```bash
cp .env.example .env
# Edit .env with your settings

# Docker Compose
docker compose up -d

# Or run locally
pip install -r requirements.txt
uvicorn sketchyapi.main:app --reload  # API
python -m sketchyapi.worker            # Worker (separate terminal)
```

## API Usage

```bash
# Create a comic
curl -X POST https://sketchyapi.snaf.foo/api/v1/comic \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"article_url": "https://example.com/article", "panels": 9, "tone": "savage"}'

# Check status
curl https://sketchyapi.snaf.foo/api/v1/comic/{job_id} \
  -H "X-API-Key: your-key"

# Get balance
curl https://sketchyapi.snaf.foo/api/v1/balance \
  -H "X-API-Key: your-key"
```

## Configuration

All settings via environment variables with `SKETCHY_` prefix. See `.env.example`.

## Architecture

```
sketchyapi/
├── main.py          # FastAPI app & endpoints
├── config.py        # Settings (env vars)
├── models.py        # Pydantic models
├── auth.py          # API key authentication
├── queue_service.py # Job queue (SQLite MVP)
├── storage.py       # File storage (local/S3)
├── script_writer.py # LLM script generation
├── worker.py        # Background job processor
└── engine/
    └── comfyui.py   # ComfyUI image generation
```

## License

MIT
