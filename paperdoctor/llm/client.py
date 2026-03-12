"""Minimal OpenAI-compatible LLM client for PaperDoctor."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_BASE_URL = "https://vip.yi-zhan.top/v1"
DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_MAX_TOKENS = 40000
DEFAULT_TIMEOUT = 600


@dataclass(slots=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str
    max_tokens: int
    timeout: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        load_dotenv()
        return cls(
            api_key=os.getenv("PAPERDOCTOR_API_KEY"),
            base_url=os.getenv("PAPERDOCTOR_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("PAPERDOCTOR_MODEL", DEFAULT_MODEL),
            max_tokens=int(os.getenv("PAPERDOCTOR_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
            timeout=int(os.getenv("PAPERDOCTOR_TIMEOUT", DEFAULT_TIMEOUT)),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


class LLMClient:
    """Small wrapper around an OpenAI-compatible chat completion API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = (
            OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
            if config.is_configured
            else None
        )

    @property
    def is_configured(self) -> bool:
        return self.config.is_configured

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self._client:
            raise RuntimeError("LLM client is not configured. Set PAPERDOCTOR_API_KEY in .env or environment variables.")
        response = self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        content = self.chat_text(system_prompt, user_prompt)
        return json.loads(content)


def load_llm_client() -> LLMClient:
    return LLMClient(LLMConfig.from_env())

