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
    mbse_failed_notes: str = ""
    world_failed_notes: str = ""


def _normalize(line: str) -> str:
    """Strip markdown bold markers so **POST:** and POST: both match."""
    return line.strip().replace("**", "")


def _detect_failures(review_text: str) -> tuple[bool, str, str, str]:
    """Parse review output to find FAIL entries and extract their notes.

    Returns (has_failures, all_failed_notes, mbse_failed_notes, world_failed_notes).
    Track membership is determined by "## Track 1" / "## Track 2" headers that
    the quality agent receives from the combined input.
    """
    lines = review_text.splitlines()
    mbse_sections: list[str] = []
    world_sections: list[str] = []
    current_post = ""
    current_track = "mbse"
    in_failed_post = False
    collecting_issues = False
    issue_lines: list[str] = []

    for line in lines:
        stripped = _normalize(line)
        lower = stripped.lower()
        if lower.startswith("## track 1") or lower.startswith("# track 1"):
            current_track = "mbse"
        elif lower.startswith("## track 2") or lower.startswith("# track 2"):
            current_track = "world"
        elif stripped.startswith("POST:"):
            if in_failed_post and issue_lines:
                entry = f"{current_post}\n" + "\n".join(issue_lines)
                (mbse_sections if current_track == "mbse" else world_sections).append(entry)
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
        entry = f"{current_post}\n" + "\n".join(issue_lines)
        (mbse_sections if current_track == "mbse" else world_sections).append(entry)

    all_sections = mbse_sections + world_sections
    has_failures = bool(all_sections)
    return (
        has_failures,
        "\n\n".join(all_sections),
        "\n\n".join(mbse_sections),
        "\n\n".join(world_sections),
    )


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
        raw = await self._call(user_prompt, max_tokens=2048)
        has_failures, failed_notes, mbse_notes, world_notes = _detect_failures(raw)
        return ReviewResult(
            raw_text=raw,
            has_failures=has_failures,
            failed_notes=failed_notes,
            mbse_failed_notes=mbse_notes,
            world_failed_notes=world_notes,
        )
