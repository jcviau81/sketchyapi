"""Script writer abstraction — prepares LLM prompts for satirical comic scripts.

MVP: returns a stub/template. Interface ready for OpenAI/Anthropic/custom backends.
"""

from __future__ import annotations
import abc
import json
from typing import Optional

from .models import Tone, Language


SYSTEM_PROMPT = """\
You are a satirical cartoonist for SketchyNews. You write comic scripts that transform news articles into biting political satire in the style of MAD Magazine.

Rules:
- Every scene_prompt MUST end with: {style}
- Use HUMAN CARICATURES of real people, NO anthropomorphic animals
- Each panel must be a VISUAL GAG, not just someone talking
- Dialogue must be sharp, witty, and at least 5 words per panel
- Build a narrative arc: setup → escalation → punchline
- Include sourceUrl, context, and originalArticle fields
"""


def build_user_prompt(
    article_text: str,
    article_url: Optional[str],
    title: Optional[str],
    num_panels: int,
    tone: Tone,
    style: str,
    language: Language,
    category: Optional[str],
) -> str:
    """Build the user prompt for the LLM."""
    lang_instruction = ""
    if language == Language.fr:
        lang_instruction = "Write ALL dialogue in French. Title in French."

    return f"""\
Write a {num_panels}-panel satirical comic script about this article.

Tone: {tone.value}
Style suffix for every prompt: {style}
{lang_instruction}
Category: {category or "auto-detect"}

Article URL: {article_url or "N/A"}
Article text:
{article_text[:4000]}

Respond with ONLY valid JSON in this exact format:
{{
  "title": "...",
  "slug": "kebab-case-slug",
  "source": "Source Name",
  "sourceUrl": "{article_url or ''}",
  "context": "2-3 sentence summary for readers",
  "originalArticle": "<paste full article text here>",
  "category": "{category or 'auto'}",
  "panels": [
    {{
      "panel": 1,
      "character": "character_id",
      "scene_prompt": "detailed visual scene description, {style}",
      "dialogue": "Sharp witty dialogue (min 5 words)"
    }}
  ]
}}
"""


class ScriptWriter(abc.ABC):
    """Abstract script writer."""

    @abc.abstractmethod
    async def write_script(
        self,
        article_text: str,
        article_url: Optional[str] = None,
        title: Optional[str] = None,
        num_panels: int = 18,
        tone: Tone = Tone.sharp,
        style: str = "",
        language: Language = Language.en,
        category: Optional[str] = None,
    ) -> dict:
        """Generate a comic script JSON. Returns parsed dict."""
        ...


class StubScriptWriter(ScriptWriter):
    """Stub that returns a placeholder script for testing."""

    async def write_script(self, article_text, article_url=None, title=None,
                           num_panels=18, tone=Tone.sharp, style="", language=Language.en,
                           category=None) -> dict:
        panels = []
        for i in range(1, num_panels + 1):
            panels.append({
                "panel": i,
                "character": "anchor" if i == 1 else "politician",
                "scene_prompt": f"News anchor caricature at desk with BREAKING NEWS graphic, panel {i}, editorial cartoon style, vibrant colors, Mort Drucker MAD Magazine style, bold ink outlines",
                "dialogue": f"Panel {i}: This is a placeholder — connect a real LLM backend to generate actual satire!",
            })
        return {
            "title": title or "Stub Comic — Connect LLM",
            "slug": "stub-comic",
            "source": "StubWriter",
            "sourceUrl": article_url or "",
            "context": "This is a stub script. Set SKETCHY_SCRIPT_WRITER_BACKEND and SKETCHY_LLM_API_KEY to enable real generation.",
            "originalArticle": article_text[:3000],
            "category": category or "WTF News",
            "panels": panels,
        }


class PromptOnlyWriter(ScriptWriter):
    """Returns the prompt that should be sent to an LLM — useful for external orchestration."""

    async def write_script(self, article_text, article_url=None, title=None,
                           num_panels=18, tone=Tone.sharp, style="", language=Language.en,
                           category=None) -> dict:
        system = SYSTEM_PROMPT.format(style=style)
        user = build_user_prompt(article_text, article_url, title, num_panels, tone, style, language, category)
        # Return the prompts instead of calling an API
        return {
            "_prompt_only": True,
            "system_prompt": system,
            "user_prompt": user,
        }


def create_script_writer() -> ScriptWriter:
    """Factory."""
    from .config import settings

    if settings.script_writer_backend == "stub":
        return StubScriptWriter()
    if settings.script_writer_backend == "prompt_only":
        return PromptOnlyWriter()
    # Future: "openai", "anthropic" — import and instantiate here
    raise ValueError(f"Unknown script writer backend: {settings.script_writer_backend}")
