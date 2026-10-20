"""Thin LLM client: JSON-only Responses calls with a hard timeout. Any failure raises LLMError → fallback (I7)."""

from __future__ import annotations

import json
import time

from openai import AsyncOpenAI

from sentinel.config import settings

TIMEOUT_S = 25


class LLMError(RuntimeError):
    pass


_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=TIMEOUT_S, max_retries=1)
    return _client


async def complete_json(system: str, user: str, smart: bool = False) -> tuple[dict, int, int]:
    """Returns (parsed JSON, total tokens, latency ms)."""
    if not settings.openai_api_key:
        raise LLMError("no OPENAI_API_KEY")
    model = settings.openai_smart_model if smart else settings.openai_fast_model
    t = time.perf_counter()
    try:
        r = await client().responses.create(
            model=model,
            instructions=system + "\nRespond with a single JSON object only.",
            input="Return a JSON object.\n" + user,
            text={"format": {"type": "json_object"}},
        )
        data = json.loads(r.output_text)
    except Exception as e:  # 429, 5xx, timeout, invalid JSON
        raise LLMError(f"{type(e).__name__}: {e}") from e
    tokens = getattr(r.usage, "total_tokens", 0) if r.usage else 0
    return data, int(tokens), int((time.perf_counter() - t) * 1000)
