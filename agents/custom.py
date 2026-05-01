from __future__ import annotations

from dataclasses import dataclass

from anthropic import AsyncAnthropic

from prompts.custom import CUSTOM_RESEARCH_SYSTEM_PROMPT, CUSTOM_DRAFT_SYSTEM_PROMPT
from .base import BaseAgent, WEB_SEARCH_TOOL
from .drafting import DraftResult

ANGLE_LABELS = [
    "Practitioner",
    "Industry/trend",
    "Contrarian",
    "SE lens",
    "Systems thinking",
]


class CustomTopicAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        # Initialise with research prompt; draft call uses a separate system prompt
        super().__init__(client, CUSTOM_RESEARCH_SYSTEM_PROMPT, tools=[WEB_SEARCH_TOOL])

    async def run(self, topic: str, n_angles: int = 3) -> DraftResult:
        # Step 1: research the topic
        research_prompt = (
            f"Find and summarise the following article or topic:\n\n{topic}\n\n"
            "Search for the full source and any relevant context."
        )
        research = await self._call(research_prompt)

        # Step 2: draft posts from the research brief
        angle_list = "\n".join(
            f"  - {ANGLE_LABELS[i]}" for i in range(min(n_angles, len(ANGLE_LABELS)))
        )
        draft_prompt = (
            f"Here is the research brief:\n\n{research}\n\n"
            f"Draft exactly {n_angles} LinkedIn post angle(s) using these angles in order:\n"
            f"{angle_list}"
        )

        # Override system prompt for the draft call
        original_system = self.system
        self.system = CUSTOM_DRAFT_SYSTEM_PROMPT
        self.tools = []
        raw = await self._call(draft_prompt)
        self.system = original_system
        self.tools = [WEB_SEARCH_TOOL]

        return DraftResult(track="custom", raw_text=raw, has_drafts=bool(raw))
