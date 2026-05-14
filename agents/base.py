from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}

log = logging.getLogger(__name__)


class BaseAgent:
    def __init__(self, client: AsyncAnthropic, system: str, tools: list | None = None):
        self.client = client
        self.system = system
        self.tools = tools or []

    def _extract_text(self, message) -> str:
        parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts).strip()

    async def _call(self, user_prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        kwargs: dict = dict(
            model=MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
        if self.tools:
            kwargs["tools"] = self.tools
        msg = await self.client.messages.create(**kwargs)
        u = msg.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        log.info(
            "usage | in=%d cache_read=%d cache_write=%d out=%d | agent=%s",
            u.input_tokens, cache_read, cache_write, u.output_tokens,
            type(self).__name__,
        )
        return self._extract_text(msg)
