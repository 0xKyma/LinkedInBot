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

# Phrases that only appear in the agent's explicit "nothing qualified" statement,
# not inside candidate descriptions. Checked only against the selection-summary
# section to avoid false negatives from matching quotes within candidate text.
_NO_CANDIDATES_SIGNALS = (
    "cannot find",
    "no strong candidates",
    "no candidates met",
    "no qualifying candidates",
    "did not meet the bar",
    "did not meet the threshold",
    "no items met",
)

_NO_WORLD_EVENT_SIGNALS = (
    "no item met",
    "no item scored",
    "no strong candidates",
    "no qualifying event",
    "no event scored",
    "no event met",
)

# Section headers that introduce the agent's final selection summary.
# Checking only this section avoids false negatives from signal phrases
# appearing inside candidate descriptions earlier in the response.
_MBSE_SELECTION_HEADER = "## selected for drafting"
_WORLD_SELECTION_HEADER = "## selected world event for drafting"


def _selection_section(raw: str, header: str) -> str:
    """Return the text from the final selection header onwards, or full text if not found."""
    idx = raw.lower().rfind(header)
    return raw[idx:] if idx != -1 else raw


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
        check = _selection_section(raw, _MBSE_SELECTION_HEADER).lower()
        has_candidates = not any(sig in check for sig in _NO_CANDIDATES_SIGNALS)
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
        check = _selection_section(raw, _WORLD_SELECTION_HEADER).lower()
        has_candidates = not any(sig in check for sig in _NO_WORLD_EVENT_SIGNALS)
        return ResearchResult(track="world_events", raw_text=raw, has_candidates=has_candidates)
