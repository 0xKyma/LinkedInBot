from __future__ import annotations

from dataclasses import dataclass

from anthropic import AsyncAnthropic

from prompts.drafting import (
    DRAFT_SYSTEM_PROMPT,
    WORLD_EVENTS_DRAFT_SYSTEM_PROMPT,
    DRAFT_REVISION_SYSTEM_PROMPT,
)
from .base import BaseAgent
from .research import ResearchResult


@dataclass
class DraftResult:
    track: str
    raw_text: str
    has_drafts: bool


class MBSEDraftingAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, DRAFT_SYSTEM_PROMPT)

    async def run(self, research: ResearchResult) -> DraftResult:
        user_prompt = (
            "Here is the scored shortlist of content to write about:\n\n"
            + research.raw_text
            + "\n\nNow draft the three LinkedIn post options as instructed."
        )
        raw = await self._call(user_prompt)
        return DraftResult(track="mbse", raw_text=raw, has_drafts=bool(raw))

    async def revise(self, draft: DraftResult, review_notes: str) -> DraftResult:
        user_prompt = (
            "Here are the current draft posts:\n\n"
            + draft.raw_text
            + "\n\nThe reviewer identified these specific issues to fix:\n\n"
            + review_notes
            + "\n\nRevise the flagged posts to fix the listed issues. "
            "Return the full set of posts in the same format, with revisions applied."
        )
        raw = await self._call(user_prompt)
        return DraftResult(track="mbse", raw_text=raw, has_drafts=bool(raw))


class WorldEventsDraftingAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, WORLD_EVENTS_DRAFT_SYSTEM_PROMPT)

    async def run(self, research: ResearchResult) -> DraftResult:
        user_prompt = (
            "Here is the selected world event and systems thinking angle:\n\n"
            + research.raw_text
            + "\n\nNow draft the two LinkedIn post options as instructed."
        )
        raw = await self._call(user_prompt)
        return DraftResult(track="world_events", raw_text=raw, has_drafts=bool(raw))

    async def revise(self, draft: DraftResult, review_notes: str) -> DraftResult:
        user_prompt = (
            "Here are the current draft posts:\n\n"
            + draft.raw_text
            + "\n\nThe reviewer identified these specific issues to fix:\n\n"
            + review_notes
            + "\n\nRevise the flagged posts to fix the listed issues. "
            "Return the full set of posts in the same format, with revisions applied."
        )
        raw = await self._call(user_prompt)
        return DraftResult(track="world_events", raw_text=raw, has_drafts=bool(raw))
