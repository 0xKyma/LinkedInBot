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
from .base import BaseAgent, WEB_SEARCH_TOOL, MODEL_RESEARCH, MODEL_EXTRACTION

_EXTRACTION_SYSTEM = (
    "You are a precise data extractor. "
    "Given research output text, call the provided tool with the exact structured result. "
    "Do not add commentary."
)

MBSE_RESEARCH_RESULT_TOOL: dict = {
    "name": "submit_research_result",
    "description": "Submit the structured MBSE research result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "has_candidates": {
                "type": "boolean",
                "description": (
                    "True if at least one item met the scoring threshold "
                    "and was selected for drafting."
                ),
            },
            "selected_items": {
                "type": "array",
                "description": "Items selected for drafting. Empty array if has_candidates is false.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "total_score": {"type": "integer"},
                    },
                    "required": ["title", "url", "total_score"],
                },
            },
            "explanation": {
                "type": "string",
                "description": (
                    "One sentence on the selection decision, or why no candidates qualified."
                ),
            },
        },
        "required": ["has_candidates", "selected_items", "explanation"],
    },
}

WORLD_EVENTS_RESULT_TOOL: dict = {
    "name": "submit_world_events_result",
    "description": "Submit the structured world events research result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "has_candidates": {
                "type": "boolean",
                "description": (
                    "True if an event met the scoring threshold and was selected for drafting."
                ),
            },
            "selected_event": {
                "type": "object",
                "description": "The selected event. Omit entirely if has_candidates is false.",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "total_score": {"type": "integer"},
                    "se_angle": {
                        "type": "string",
                        "description": "The systems engineering or systems thinking angle identified.",
                    },
                },
                "required": ["title", "url", "total_score", "se_angle"],
            },
            "explanation": {
                "type": "string",
                "description": (
                    "One sentence on the selection decision, or why no event qualified."
                ),
            },
        },
        "required": ["has_candidates", "explanation"],
    },
}


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
        super().__init__(client, SEARCH_SYSTEM_PROMPT, tools=[WEB_SEARCH_TOOL], model=MODEL_RESEARCH)

    async def run(self, today: dt.date, skip_urls: set[str] | None = None) -> ResearchResult:
        cutoff = (today - dt.timedelta(days=10)).isoformat()
        user_prompt = SEARCH_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(),
            cutoff=cutoff,
            exclude_sources=_format_exclude(skip_urls),
        )
        raw = await self._call(user_prompt)
        structured = await self._call_with_forced_tool(
            f"Extract the selection result from this MBSE research output:\n\n{raw}",
            MBSE_RESEARCH_RESULT_TOOL,
            system=_EXTRACTION_SYSTEM,
            model=MODEL_EXTRACTION,
        )
        return ResearchResult(
            track="mbse",
            raw_text=raw,
            has_candidates=structured["has_candidates"],
        )


class WorldEventsResearchAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, WORLD_EVENTS_SEARCH_SYSTEM_PROMPT, tools=[WEB_SEARCH_TOOL], model=MODEL_RESEARCH)

    async def run(self, today: dt.date, skip_urls: set[str] | None = None) -> ResearchResult:
        cutoff_14d = (today - dt.timedelta(days=14)).isoformat()
        user_prompt = WORLD_EVENTS_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(),
            cutoff_14d=cutoff_14d,
            exclude_sources=_format_exclude(skip_urls),
        )
        raw = await self._call(user_prompt)
        structured = await self._call_with_forced_tool(
            f"Extract the selection result from this world events research output:\n\n{raw}",
            WORLD_EVENTS_RESULT_TOOL,
            system=_EXTRACTION_SYSTEM,
            model=MODEL_EXTRACTION,
        )
        return ResearchResult(
            track="world_events",
            raw_text=raw,
            has_candidates=structured["has_candidates"],
        )
