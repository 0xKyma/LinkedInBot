from __future__ import annotations

import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from prompts.quality import QUALITY_SYSTEM_PROMPT
from .base import BaseAgent, MODEL_QUALITY
from .drafting import DraftResult

log = logging.getLogger(__name__)

# A full day can produce ~14 drafts (3 MBSE items x 4 angles + 2 world events).
# Each structured review entry (post_id, status, word_count, quoted issues) is
# verbose, so the forced tool call needs generous output room — too small a cap
# truncates the JSON mid-array and the result comes back without "reviews".
QUALITY_REVIEW_MAX_TOKENS = 8192

QUALITY_REVIEW_TOOL: dict = {
    "name": "submit_quality_review",
    "description": "Submit the structured quality review for all draft posts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reviews": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "string",
                            "description": (
                                "The post section header, "
                                "e.g. 'C1 Option 1 — Practitioner' or "
                                "'World Event Option 1 — SE methodology frame'."
                            ),
                        },
                        "status": {"type": "string", "enum": ["PASS", "FAIL"]},
                        "word_count": {"type": "integer"},
                        "issues": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Specific rule violations, quoted where possible. "
                                "Empty list if status is PASS."
                            ),
                        },
                    },
                    "required": ["post_id", "status", "word_count", "issues"],
                },
            }
        },
        "required": ["reviews"],
    },
}


def _is_world_event(post_id: str) -> bool:
    return "world event" in post_id.lower()


def _format_review_text(reviews: list[dict]) -> str:
    lines = []
    for r in reviews:
        lines.append(f"POST: {r['post_id']}")
        lines.append(f"STATUS: {r['status']}")
        lines.append(f"WORD COUNT: {r['word_count']}")
        lines.append("ISSUES:")
        if r["issues"]:
            for issue in r["issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines).strip()


def _format_failed_notes(failed: list[dict]) -> str:
    parts = []
    for r in failed:
        issues_str = "\n".join(f"- {i}" for i in r["issues"])
        parts.append(f"{r['post_id']}\n{issues_str}")
    return "\n\n".join(parts)


@dataclass
class ReviewResult:
    raw_text: str
    has_failures: bool
    failed_notes: str = ""
    mbse_failed_notes: str = ""
    world_failed_notes: str = ""


class QualityAgent(BaseAgent):
    def __init__(self, client: AsyncAnthropic):
        super().__init__(client, QUALITY_SYSTEM_PROMPT, model=MODEL_QUALITY)

    async def run(self, mbse_drafts: DraftResult, world_drafts: DraftResult) -> ReviewResult:
        combined = ""
        if mbse_drafts.has_drafts:
            combined += "## Track 1 Drafts\n\n" + mbse_drafts.raw_text + "\n\n"
        if world_drafts.has_drafts:
            combined += "## Track 2 Drafts\n\n" + world_drafts.raw_text + "\n\n"

        if not combined.strip():
            return ReviewResult(raw_text="No drafts to review.", has_failures=False)

        user_prompt = (
            "Review every post in the following drafts against the checklist "
            "and call submit_quality_review with a result for each one:\n\n" + combined
        )
        structured = await self._call_with_forced_tool(
            user_prompt, QUALITY_REVIEW_TOOL, max_tokens=QUALITY_REVIEW_MAX_TOKENS
        )
        reviews = structured.get("reviews", [])
        if not reviews:
            # Truncated or malformed extraction. Don't lose the whole run over a
            # review-formatting issue — keep the drafts (they are reviewed by a
            # human before posting) and record that the check was inconclusive.
            log.warning("Quality review returned no parseable results; keeping drafts unreviewed.")
            return ReviewResult(
                raw_text="_Quality review was inconclusive; drafts kept as-is._",
                has_failures=False,
            )

        failed = [r for r in reviews if r["status"] == "FAIL"]
        mbse_failed = [r for r in failed if not _is_world_event(r["post_id"])]
        world_failed = [r for r in failed if _is_world_event(r["post_id"])]

        return ReviewResult(
            raw_text=_format_review_text(reviews),
            has_failures=bool(failed),
            failed_notes=_format_failed_notes(failed),
            mbse_failed_notes=_format_failed_notes(mbse_failed),
            world_failed_notes=_format_failed_notes(world_failed),
        )
