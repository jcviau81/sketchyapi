"""Run: python -m sketchyapi"""
import uvicorn
from .config import settings

uvicorn.run("sketchyapi.main:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)
