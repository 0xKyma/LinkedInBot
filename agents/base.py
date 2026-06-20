"""
Agent harness.

``BaseAgent`` is the single execution path every agent shares: it owns the
model/token configuration, the system-prompt caching, structured usage logging,
and the two call shapes (free-text ``_call`` and forced-tool ``_call_with_forced_tool``).
Agents stay thin — they compose a system prompt (from Agent Skills, see
``skill_loader``) and call through this harness rather than touching the SDK
directly.

``create_client`` centralises client construction so every entry point gets the
same retry policy. The Anthropic SDK already retries 429/5xx/connection errors
with exponential backoff; we raise the ceiling so a transient web-search or
rate-limit blip during the daily run self-heals instead of aborting the job.
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

# Model routing (#5): match each step to the cheapest model that does it well.
# Re-tune any of these in one line; the harness wires each agent to its model.
MODEL_RESEARCH = "claude-sonnet-4-6"    # web search + 25-point rubric scoring: balanced judgment, token-heavy
MODEL_DRAFTING = "claude-opus-4-8"      # the posts themselves: strongest writing voice, worth the premium
MODEL_QUALITY = "claude-haiku-4-5"      # checklist enforcement: lexical pattern matching, runs every revision round
MODEL_EXTRACTION = "claude-haiku-4-5"   # pull structured fields out of already-generated text: trivial
DEFAULT_MODEL = MODEL_RESEARCH

MAX_TOKENS = 16384
# A full daily run is a handful of calls; a transient failure shouldn't lose it.
MAX_RETRIES = 4
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}

log = logging.getLogger(__name__)


def create_client() -> AsyncAnthropic:
    """Construct the shared async client with the pipeline's retry policy.

    Reads ANTHROPIC_API_KEY from the environment (SDK default). Use this from
    every entry point instead of ``AsyncAnthropic()`` so retry behaviour is
    consistent across the MBSE, world-events, and interactive paths.
    """
    return AsyncAnthropic(max_retries=MAX_RETRIES)


class BaseAgent:
    def __init__(
        self,
        client: AsyncAnthropic,
        system: str,
        tools: list | None = None,
        model: str = DEFAULT_MODEL,
    ):
        self.client = client
        self.system = system
        self.tools = tools or []
        self.model = model

    def _extract_text(self, message) -> str:
        parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts).strip()

    def _log_usage(self, msg, model: str, label: str = "") -> None:
        u = msg.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        log.info(
            "usage | in=%d cache_read=%d cache_write=%d out=%d | model=%s agent=%s%s",
            u.input_tokens, cache_read, cache_write, u.output_tokens,
            model, type(self).__name__,
            f":{label}" if label else "",
        )

    async def _call(self, user_prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        kwargs: dict = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
        if self.tools:
            kwargs["tools"] = self.tools
        msg = await self.client.messages.create(**kwargs)
        self._log_usage(msg, self.model)
        return self._extract_text(msg)

    async def _call_with_forced_tool(
        self,
        user_prompt: str,
        tool: dict,
        system: str | None = None,
        max_tokens: int = 1024,
        model: str | None = None,
    ) -> dict:
        """Force the model to return results via a specific tool call.

        Uses ``system`` if provided, otherwise ``self.system``; uses ``model`` if
        provided, otherwise ``self.model`` (so a Sonnet research agent can run its
        cheap extraction sub-call on Haiku). No extra tools are passed, so this is
        safe regardless of what tools the agent normally uses. Returns the tool's
        input dict.
        """
        effective_system = system if system is not None else self.system
        effective_model = model or self.model
        msg = await self.client.messages.create(
            model=effective_model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": effective_system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        self._log_usage(msg, effective_model, label="extract")
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return block.input
        raise ValueError(f"Model did not call expected tool '{tool['name']}'")
