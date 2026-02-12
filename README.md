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

## Deployment (Local — thething + snaf.foo)

### Services (systemd on thething)

| Service | Description | Port |
|---------|-------------|------|
| `sketchyapi.service` | FastAPI API server | 8900 |
| `sketchyapi-worker.service` | Background comic generator | — |
| `sketchyapi-tunnel.service` | SSH reverse tunnel to snaf.foo | — |

Service files: `deploy/`

### Architecture

```
User → sketchyapi.snaf.foo (Caddy HTTPS)
       → SSH tunnel → thething:8900 (FastAPI)
       → SQLite queue → Worker → ComfyUI (192.168.1.59:8123, RTX 3090)
       → Panels saved to data/output/
```

### Enable/Disable

```bash
# Enable (thething):
sudo systemctl enable --now sketchyapi sketchyapi-worker sketchyapi-tunnel

# Disable (thething):
sudo systemctl stop sketchyapi sketchyapi-worker sketchyapi-tunnel
sudo systemctl disable sketchyapi sketchyapi-worker sketchyapi-tunnel

# Caddy on snaf.foo — block at lines 50-65 in /etc/caddy/Caddyfile
# Comment out to disable, uncomment to enable, then: sudo systemctl reload caddy
```

### Performance

- ~16 seconds per panel (Flux fp8, 512x512, 20 steps, RTX 3090)
- 6-panel comic ≈ 2 minutes total (including script + assembly)

## Status

**PAUSED** as of 2026-02-12. All services disabled. First successful job completed.

## License

MIT
