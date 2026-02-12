"""SketchyNews Satire-as-a-Service API."""

from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import Response

from .config import settings
from .auth import AuthInfo, require_auth
from .models import (
    ComicRequest, ComicJob, JobStatus, PanelInfo,
    BalanceResponse, WebhookTestRequest, WebhookPayload,
)
from .queue_service import QueueBackend, create_queue
from .storage import StorageBackend, create_storage
from .worker import send_webhook

logger = logging.getLogger("sketchy.api")

# --- Globals (initialized at startup) ---
queue: QueueBackend
storage: StorageBackend


@asynccontextmanager
async def lifespan(app: FastAPI):
    global queue, storage
    queue = create_queue()
    storage = create_storage()
    settings.resolved_output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("SketchyNews API ready")
    yield


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)


# --- Helpers ---

def _job_to_response(job) -> ComicJob:
    result = job.result or {}
    panels = [PanelInfo(**p) for p in result.get("panels", [])]
    return ComicJob(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress=job.progress,
        panels_completed=job.panels_completed,
        panels_total=job.request.get("panels", 18),
        combined_image_url=result.get("combined_image_url"),
        panels=panels,
        title=result.get("title") or job.request.get("title"),
        error=job.error,
    )


def _check_rate_limit(auth: AuthInfo):
    limit = settings.rate_limit_for_tier(auth.tier)
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    used = queue.count_requests(auth.api_key, since)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({used}/{limit} per hour for {auth.tier} tier)",
        )
    return used, limit


# --- Endpoints ---

@app.post("/api/v1/comic", response_model=ComicJob, status_code=201)
async def create_comic(req: ComicRequest, auth: AuthInfo = Depends(require_auth)):
    """Submit a comic generation job."""
    _check_rate_limit(auth)
    job = queue.enqueue(auth.api_key, req)
    return _job_to_response(job)


@app.get("/api/v1/comic/{job_id}", response_model=ComicJob)
async def get_comic(job_id: str, auth: AuthInfo = Depends(require_auth)):
    """Get job status and result."""
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_response(job)


@app.get("/api/v1/comic/{job_id}/panels/{n}")
async def get_panel(job_id: str, n: int, auth: AuthInfo = Depends(require_auth)):
    """Download individual panel image."""
    key = f"{job_id}/panels/panel_{n:02d}.png"
    data = storage.get(key)
    if not data:
        raise HTTPException(404, "Panel not found")
    return Response(content=data, media_type="image/png")


@app.get("/api/v1/comic/{job_id}/combined")
async def get_combined(job_id: str, auth: AuthInfo = Depends(require_auth)):
    """Download combined comic image."""
    key = f"{job_id}/combined.png"
    data = storage.get(key)
    if not data:
        raise HTTPException(404, "Comic not found (still generating?)")
    return Response(content=data, media_type="image/png")


@app.get("/api/v1/balance", response_model=BalanceResponse)
async def get_balance(auth: AuthInfo = Depends(require_auth)):
    """Check usage and quota."""
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    limit = settings.rate_limit_for_tier(auth.tier)
    used = queue.count_requests(auth.api_key, since)
    return BalanceResponse(
        tier=auth.tier,
        requests_used=used,
        requests_limit=limit,
        requests_remaining=max(0, limit - used),
        reset_at=since + timedelta(hours=1),
    )


@app.post("/api/v1/webhook/test")
async def test_webhook(req: WebhookTestRequest, auth: AuthInfo = Depends(require_auth)):
    """Send a test webhook to verify your endpoint."""
    payload = WebhookPayload(
        event="test",
        job_id="test_000000000000",
        status=JobStatus.completed,
        combined_image_url=f"{settings.base_url}/example.png",
        panels_count=18,
        title="Test Webhook Delivery",
    )
    ok = await send_webhook(req.url, payload)
    if not ok:
        raise HTTPException(502, "Webhook delivery failed")
    return {"status": "ok", "message": "Test webhook delivered successfully"}


# --- Static file serving for local storage ---

@app.get("/files/{path:path}")
async def serve_file(path: str):
    """Serve stored files (local storage only)."""
    data = storage.get(path)
    if not data:
        raise HTTPException(404, "File not found")
    ct = "image/png" if path.endswith(".png") else "image/webp" if path.endswith(".webp") else "application/octet-stream"
    return Response(content=data, media_type=ct)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.api_version}
