from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic

from prompts.research import (
    SEARCH_SYSTEM_PROMPT,
    SEARCH_USER_PROMPT_TEMPLATE,
    WORLD_EVENTS_SEARCH_SYSTEM_PROMPT,
    WORLD_EVENTS_USER_PROMPT_TEMPLATE,
)
from .base import BaseAgent, WEB_SEARCH_TOOL

_NO_CANDIDATES_SIGNALS = (
    "cannot find",
    "no strong candidates",
    "did not meet",
    "no qualifying",
)

_NO_WORLD_EVENT_SIGNALS = (
    "no item",
    "no strong candidates",
    "did not meet",
    "no event",
    "no qualifying",
)


@dataclass
class ResearchResult:
    track: str
    raw_text: str
    has_candidates: bool
    shortlist_summary: str = ""


def _format_exclude(skip_urls: set[str] | None) -> str:
    if not skip_urls:
        return "None"
    return "\n".join(f"- {u}" for u in sorted(skip_urls))


class MBSEResearchAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, SEARCH_SYSTEM_PROMPT, tools=[WEB_SEARCH_TOOL])

    async def run(self, today: dt.date, skip_urls: set[str] | None = None) -> ResearchResult:
        cutoff = (today - dt.timedelta(days=10)).isoformat()
        user_prompt = SEARCH_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(),
            cutoff=cutoff,
            exclude_sources=_format_exclude(skip_urls),
        )
        raw = await self._call(user_prompt)
        low = raw.lower()
        has_candidates = not any(sig in low for sig in _NO_CANDIDATES_SIGNALS)
        return ResearchResult(track="mbse", raw_text=raw, has_candidates=has_candidates)


class WorldEventsResearchAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, WORLD_EVENTS_SEARCH_SYSTEM_PROMPT, tools=[WEB_SEARCH_TOOL])

    async def run(self, today: dt.date, skip_urls: set[str] | None = None) -> ResearchResult:
        cutoff_14d = (today - dt.timedelta(days=14)).isoformat()
        user_prompt = WORLD_EVENTS_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(),
            cutoff_14d=cutoff_14d,
            exclude_sources=_format_exclude(skip_urls),
        )
        raw = await self._call(user_prompt)
        low = raw.lower()
        has_candidates = not any(sig in low for sig in _NO_WORLD_EVENT_SIGNALS)
        return ResearchResult(track="world_events", raw_text=raw, has_candidates=has_candidates)
