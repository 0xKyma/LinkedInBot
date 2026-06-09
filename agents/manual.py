from __future__ import annotations

from anthropic import AsyncAnthropic

from prompts.custom import CUSTOM_RESEARCH_SYSTEM_PROMPT
from prompts.manual import MANUAL_INFO_DRAFT_SYSTEM_PROMPT, MANUAL_SOURCE_DRAFT_SYSTEM_PROMPT
from .base import BaseAgent, WEB_SEARCH_TOOL, MODEL_RESEARCH, MODEL_DRAFTING
from .drafting import DraftResult


class ManualDraftAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, CUSTOM_RESEARCH_SYSTEM_PROMPT, tools=[WEB_SEARCH_TOOL], model=MODEL_RESEARCH)

    def _reset_to_research(self) -> None:
        self.system = CUSTOM_RESEARCH_SYSTEM_PROMPT
        self.tools = [WEB_SEARCH_TOOL]
        self.model = MODEL_RESEARCH

    async def run_from_source(self, topic: str, angle: str) -> DraftResult:
        """Research a URL or topic via web search (Sonnet), then draft one post (Opus)."""
        research = await self._call(
            f"Find and summarise the following article or topic:\n\n{topic}\n\n"
            "Search for the full source and any relevant context."
        )

        self.system = MANUAL_SOURCE_DRAFT_SYSTEM_PROMPT
        self.tools = []
        self.model = MODEL_DRAFTING
        raw = await self._call(
            f"Research brief:\n\n{research}\n\n"
            f"Angle to use: {angle}\n\n"
            "Draft one LinkedIn post using this angle."
        )
        self._reset_to_research()

        return DraftResult(track="manual", raw_text=raw, has_drafts=bool(raw))

    async def run_from_info(self, user_text: str, angle: str) -> DraftResult:
        """Draft directly from user-provided info (Opus) — no web search."""
        self.system = MANUAL_INFO_DRAFT_SYSTEM_PROMPT
        self.tools = []
        self.model = MODEL_DRAFTING
        raw = await self._call(
            f"Angle to use: {angle}\n\n"
            f"User input:\n{user_text}"
        )
        self._reset_to_research()

        return DraftResult(track="manual", raw_text=raw, has_drafts=bool(raw))
