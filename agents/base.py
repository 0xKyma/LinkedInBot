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

    def _log_usage(self, msg, label: str = "") -> None:
        u = msg.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        log.info(
            "usage | in=%d cache_read=%d cache_write=%d out=%d | agent=%s%s",
            u.input_tokens, cache_read, cache_write, u.output_tokens,
            type(self).__name__,
            f":{label}" if label else "",
        )

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
        self._log_usage(msg)
        return self._extract_text(msg)

    async def _call_with_forced_tool(
        self,
        user_prompt: str,
        tool: dict,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> dict:
        """Force the model to return results via a specific tool call.

        Uses system if provided, otherwise self.system. No extra tools are passed
        so this is safe to call regardless of what tools the agent normally uses.
        Returns the tool's input dict.
        """
        effective_system = system if system is not None else self.system
        msg = await self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": effective_system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        self._log_usage(msg, label="extract")
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return block.input
        raise ValueError(f"Model did not call expected tool '{tool['name']}'")
