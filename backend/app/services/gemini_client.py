"""
Thin wrapper around the Gemini SDK: one place that owns the API key, model
names, and the text/structured/image call shapes every agent needs. Agents
never import google.genai directly -- keeps the vendor swappable and keeps
resilience.run_with_fallback wrapping a single well-defined async surface.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, TypeVar

from google import genai
from pydantic import BaseModel

from app.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)

TEXT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "gemini-2.5-flash-image"

T = TypeVar("T", bound=BaseModel)


async def generate_text(system_prompt: str, user_message: str) -> str:
    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=TEXT_MODEL,
        contents=user_message,
        config={"system_instruction": system_prompt},
    )
    return response.text or ""


async def stream_text(system_prompt: str, user_message: str) -> AsyncIterator[str]:
    """Used by the Elicitation Agent so /chat/completions can stream SSE
    chunks back to Agora as they arrive, instead of waiting on the full
    reply."""
    stream = await asyncio.to_thread(
        _client.models.generate_content_stream,
        model=TEXT_MODEL,
        contents=user_message,
        config={"system_instruction": system_prompt},
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


async def generate_structured(system_prompt: str, user_message: str, schema: type[T]) -> T:
    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=TEXT_MODEL,
        contents=user_message,
        config={
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "response_schema": schema,
        },
    )
    return schema.model_validate_json(response.text)


async def generate_image(prompt: str, reference_image_bytes: bytes | None = None) -> bytes:
    """Composite generation / iterative edit. When reference_image_bytes is
    given, Gemini 2.5 Flash Image edits it in place (multi-turn consistency);
    otherwise it generates fresh. See agents/composite_generation.py for the
    "always pass the full current parameter set, not just the delta" policy
    that keeps this controllable turn over turn."""
    contents: list = [prompt]
    if reference_image_bytes is not None:
        contents.append({"inline_data": {"mime_type": "image/png", "data": reference_image_bytes}})

    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=IMAGE_MODEL,
        contents=contents,
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None:
            return part.inline_data.data
    raise RuntimeError("Gemini image response contained no image part")
