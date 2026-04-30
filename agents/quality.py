from __future__ import annotations

from dataclasses import dataclass, field

from anthropic import AsyncAnthropic

from prompts.quality import QUALITY_SYSTEM_PROMPT
from .base import BaseAgent
from .drafting import DraftResult


@dataclass
class ReviewResult:
    raw_text: str
    has_failures: bool
    failed_notes: str = ""


def _detect_failures(review_text: str) -> tuple[bool, str]:
    """Parse review output to find FAIL entries and extract their notes."""
    lines = review_text.splitlines()
    failed_sections: list[str] = []
    current_post = ""
    in_failed_post = False
    collecting_issues = False
    issue_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("POST:"):
            if in_failed_post and issue_lines:
                failed_sections.append(
                    f"{current_post}\n" + "\n".join(issue_lines)
                )
            current_post = stripped[len("POST:"):].strip()
            in_failed_post = False
            collecting_issues = False
            issue_lines = []
        elif stripped.startswith("STATUS:"):
            status = stripped[len("STATUS:"):].strip().upper()
            in_failed_post = status == "FAIL"
        elif stripped.startswith("ISSUES:") and in_failed_post:
            collecting_issues = True
        elif collecting_issues and in_failed_post and stripped.startswith("-"):
            if stripped != "- None":
                issue_lines.append(stripped)

    if in_failed_post and issue_lines:
        failed_sections.append(f"{current_post}\n" + "\n".join(issue_lines))

    has_failures = bool(failed_sections)
    failed_notes = "\n\n".join(failed_sections)
    return has_failures, failed_notes


class QualityAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, QUALITY_SYSTEM_PROMPT)

    async def run(self, mbse_drafts: DraftResult, world_drafts: DraftResult) -> ReviewResult:
        combined = ""
        if mbse_drafts.has_drafts:
            combined += "## Track 1 Drafts\n\n" + mbse_drafts.raw_text + "\n\n"
        if world_drafts.has_drafts:
            combined += "## Track 2 Drafts\n\n" + world_drafts.raw_text + "\n\n"

        if not combined.strip():
            return ReviewResult(raw_text="No drafts to review.", has_failures=False)

        user_prompt = (
            "Review all of the following LinkedIn post drafts against the checklist:\n\n"
            + combined
        )
        raw = await self._call(user_prompt)
        has_failures, failed_notes = _detect_failures(raw)
        return ReviewResult(raw_text=raw, has_failures=has_failures, failed_notes=failed_notes)
