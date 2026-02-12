"""Pydantic models for request/response."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# --- Enums ---

class Tone(str, Enum):
    gentle = "gentle"
    sharp = "sharp"
    savage = "savage"
    absurd = "absurd"


class JobStatus(str, Enum):
    pending = "pending"
    writing_script = "writing_script"
    generating_images = "generating_images"
    assembling = "assembling"
    completed = "completed"
    failed = "failed"


class Language(str, Enum):
    en = "en"
    fr = "fr"


# --- Requests ---

class ComicRequest(BaseModel):
    """Submit a new comic generation job."""
    article_url: Optional[str] = Field(None, description="URL of the article to satirize")
    article_text: Optional[str] = Field(None, description="Raw article text (alternative to URL)")
    title: Optional[str] = Field(None, description="Optional title override")
    panels: int = Field(18, description="Number of panels", ge=4, le=18)
    tone: Tone = Field(Tone.sharp, description="Satirical tone")
    style: str = Field(
        "editorial cartoon style, vibrant colors, Mort Drucker MAD Magazine style, bold ink outlines",
        description="Art style prompt suffix",
    )
    language: Language = Field(Language.en)
    category: Optional[str] = Field(None, description="Category override")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion callback")

    def model_post_init(self, __context):
        if not self.article_url and not self.article_text:
            raise ValueError("Provide either article_url or article_text")


class WebhookTestRequest(BaseModel):
    url: str = Field(..., description="Webhook URL to test")


# --- Responses ---

class PanelInfo(BaseModel):
    index: int
    character: str = ""
    dialogue: str = ""
    image_url: Optional[str] = None


class ComicJob(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: Optional[str] = None
    panels_completed: int = 0
    panels_total: int = 0
    # Populated on completion
    combined_image_url: Optional[str] = None
    panels: list[PanelInfo] = []
    title: Optional[str] = None
    error: Optional[str] = None


class BalanceResponse(BaseModel):
    tier: str
    requests_used: int
    requests_limit: int
    requests_remaining: int
    reset_at: datetime


class WebhookPayload(BaseModel):
    event: str = "comic.completed"
    job_id: str
    status: JobStatus
    combined_image_url: Optional[str] = None
    panels_count: int = 0
    title: Optional[str] = None
    error: Optional[str] = None
