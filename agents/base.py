from __future__ import annotations

from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}


class BaseAgent:
    def __init__(self, client: AsyncAnthropic, system: str, tools: list | None = None):
        self.client = client
        self.system = system
        self.tools = tools or []

    def _extract_text(self, message) -> str:
        parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts).strip()

    async def _call(self, user_prompt: str) -> str:
        kwargs: dict = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=self.system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if self.tools:
            kwargs["tools"] = self.tools
        msg = await self.client.messages.create(**kwargs)
        return self._extract_text(msg)
