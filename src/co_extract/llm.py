"""LLM extraction via any OpenAI-compatible API (Groq by default; Ollama etc. via LLM_BASE_URL)."""

import json
import os

from openai import OpenAI
from pydantic import ValidationError

from .schema import FIELD_GUIDE, Extraction

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
MAX_CHARS = 30_000

SYSTEM = """You extract structured data from construction change-order documents.
Return ONLY a JSON object with exactly these keys:
{guide}

Rules:
- Copy names, numbers and text from the document. Do not guess or calculate missing values.
- If a value is not stated, use null (line_items: []).
- Dates as YYYY-MM-DD. Money as plain numbers (no symbols or commas).
- If the document bundles several change orders (e.g. subcontractor quotes as backup), extract the main, top-level one."""


def available() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY"))


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY"),
        max_retries=6,  # free tiers rate-limit; the SDK backs off on 429
    )


def extract(text: str, temperature: float = 0.0) -> Extraction | None:
    """One extraction pass. Retries once with the validation error; returns None if both attempts fail."""
    guide = "\n".join(f'- "{k}": {v}' for k, v in FIELD_GUIDE.items())
    messages = [
        {"role": "system", "content": SYSTEM.format(guide=guide)},
        {"role": "user", "content": f"Document:\n<<<\n{text[:MAX_CHARS]}\n>>>"},
    ]
    client = _client()
    for _ in range(2):
        resp = client.chat.completions.create(
            model=model_name(),
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        try:
            return Extraction.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as e:
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That output was invalid: {e}. Return the corrected JSON object only."},
            ]
    return None
