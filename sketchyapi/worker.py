"""Background worker that processes comic generation jobs."""

from __future__ import annotations
import asyncio
import json
import logging
import re
import traceback

import httpx

from .config import settings
from .models import JobStatus, Tone, Language, WebhookPayload
from .queue_service import QueueBackend, Job, create_queue
from .storage import StorageBackend, create_storage
from .script_writer import ScriptWriter, create_script_writer
from .engine.comfyui import generate_image
from .engine.assembler import assemble_comic

logger = logging.getLogger("sketchy.worker")


async def send_webhook(url: str, payload: WebhookPayload) -> bool:
    """Send webhook notification."""
    try:
        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            resp = await client.post(url, json=payload.model_dump(mode="json"))
            logger.info(f"Webhook {url} → {resp.status_code}")
            return 200 <= resp.status_code < 300
    except Exception as e:
        logger.warning(f"Webhook failed: {e}")
        return False


async def process_job(job: Job, queue: QueueBackend, storage: StorageBackend, writer: ScriptWriter):
    """Process a single job end-to-end."""
    job_id = job.job_id
    request = job.request
    num_panels = request.get("panels", 18)

    try:
        # 1. Write script
        queue.update_status(job_id, JobStatus.writing_script, progress="Writing satirical script...")
        logger.info(f"[{job_id}] Writing script...")

        article_text = request.get("article_text", "")
        article_url = request.get("article_url")

        if not article_text and article_url:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(article_url, follow_redirects=True)
                    html = resp.text
                    for tag in ["script", "style", "nav", "footer", "aside"]:
                        html = re.sub(f"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)
                    article_text = re.sub(r"<[^>]+>", " ", html)
                    article_text = re.sub(r"\s+", " ", article_text).strip()[:4000]
            except Exception as e:
                logger.warning(f"[{job_id}] Failed to fetch article: {e}")
                if not article_text:
                    raise ValueError(f"Cannot fetch article from {article_url}: {e}")

        script = await writer.write_script(
            article_text=article_text,
            article_url=article_url,
            title=request.get("title"),
            num_panels=num_panels,
            tone=Tone(request.get("tone", "sharp")),
            style=request.get("style", ""),
            language=Language(request.get("language", "en")),
            category=request.get("category"),
        )

        if script.get("_prompt_only"):
            queue.update_status(job_id, JobStatus.completed, result=script)
            return

        title = script.get("title", "Untitled")
        storage.save(f"{job_id}/script.json", json.dumps(script, indent=2, ensure_ascii=False).encode())

        # 2. Generate images
        queue.update_status(job_id, JobStatus.generating_images, progress=f"Generating panel 1/{num_panels}...")
        logger.info(f"[{job_id}] Generating {num_panels} panels...")

        panels_data: list[tuple[bytes, str]] = []
        panel_urls = []

        for i, panel in enumerate(script.get("panels", [])[:num_panels]):
            queue.update_status(
                job_id, JobStatus.generating_images,
                progress=f"Generating panel {i + 1}/{num_panels}...",
                panels_completed=i,
            )

            img_bytes = await asyncio.to_thread(
                generate_image,
                panel["scene_prompt"],
                settings.comfyui_url,
                settings.comfyui_checkpoint,
                settings.comfyui_steps,
            )

            key = f"{job_id}/panels/panel_{i + 1:02d}.png"
            url = storage.save(key, img_bytes, "image/png")
            panel_urls.append(url)
            panels_data.append((img_bytes, panel.get("dialogue", "")))
            logger.info(f"[{job_id}] Panel {i + 1}/{num_panels} ✓")

        # 3. Assemble
        queue.update_status(job_id, JobStatus.assembling, progress="Assembling comic...", panels_completed=num_panels)
        logger.info(f"[{job_id}] Assembling...")

        combined_bytes = await asyncio.to_thread(assemble_comic, panels_data, title, num_panels)
        combined_key = f"{job_id}/combined.png"
        combined_url = storage.save(combined_key, combined_bytes, "image/png")

        # 4. Done
        result = {
            "title": title,
            "combined_image_url": combined_url,
            "panels": [
                {
                    "index": i + 1,
                    "character": p.get("character", ""),
                    "dialogue": p.get("dialogue", ""),
                    "image_url": panel_urls[i],
                }
                for i, p in enumerate(script.get("panels", [])[:num_panels])
            ],
        }
        queue.update_status(job_id, JobStatus.completed, result=result, panels_completed=num_panels)
        logger.info(f"[{job_id}] ✅ Completed!")

        webhook_url = request.get("webhook_url")
        if webhook_url:
            payload = WebhookPayload(
                event="comic.completed", job_id=job_id, status=JobStatus.completed,
                combined_image_url=combined_url, panels_count=num_panels, title=title,
            )
            await send_webhook(webhook_url, payload)

    except Exception as e:
        logger.error(f"[{job_id}] ❌ Failed: {e}\n{traceback.format_exc()}")
        queue.update_status(job_id, JobStatus.failed, error=str(e))

        webhook_url = request.get("webhook_url")
        if webhook_url:
            payload = WebhookPayload(
                event="comic.failed", job_id=job_id, status=JobStatus.failed, error=str(e),
            )
            await send_webhook(webhook_url, payload)


async def worker_loop():
    """Main worker loop."""
    queue = create_queue()
    storage = create_storage()
    writer = create_script_writer()

    logger.info(f"Worker started (poll={settings.worker_poll_interval}s, backend={settings.queue_backend})")

    while True:
        try:
            job = queue.next_pending()
            if job:
                logger.info(f"Claimed job {job.job_id}")
                await process_job(job, queue, storage, writer)
            else:
                await asyncio.sleep(settings.worker_poll_interval)
        except KeyboardInterrupt:
            logger.info("Worker shutting down.")
            break
        except Exception as e:
            logger.error(f"Worker error: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(settings.worker_poll_interval)


def run_worker():
    """Entry point for standalone worker process."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    asyncio.run(worker_loop())


if __name__ == "__main__":
    run_worker()
