from __future__ import annotations

import datetime as dt
from pathlib import Path

from agents.drafting import DraftResult
from agents.quality import ReviewResult

REPO_ROOT = Path(__file__).resolve().parent

POSTS_DIR = REPO_ROOT / "posts"
RESEARCH_DIR = REPO_ROOT / "research"
CRITIQUE_DIR = REPO_ROOT / "critique"

for _d in (POSTS_DIR, RESEARCH_DIR, CRITIQUE_DIR):
    _d.mkdir(exist_ok=True)


def write_post_file(
    date: dt.date,
    mbse_evaluation: str,
    mbse_drafts: DraftResult,
    world_evaluation: str,
    world_drafts: DraftResult,
    review: ReviewResult | None = None,
    custom_drafts: list[tuple[str, DraftResult]] | None = None,
) -> tuple[Path, Path, Path]:
    date_str = date.isoformat()

    # posts/YYYY-MM-DD-post.md — draft posts only
    posts_content = f"# LinkedIn Drafts — {date_str}\n\n"
    if mbse_drafts.has_drafts:
        posts_content += f"## Track 1: MBSE / SysML / Systems Engineering\n\n{mbse_drafts.raw_text}\n"
    else:
        posts_content += "## Track 1: MBSE / SysML / Systems Engineering\n\n_No qualifying candidates found today._\n"
    if world_drafts.has_drafts:
        posts_content += f"\n---\n\n## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n{world_drafts.raw_text}\n"
    elif world_evaluation:
        posts_content += "\n---\n\n## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n_No qualifying event found today._\n"
    if custom_drafts:
        for i, (topic, draft) in enumerate(custom_drafts, 1):
            if draft.has_drafts:
                posts_content += f"\n---\n\n## Custom Topic {i}: {topic}\n\n{draft.raw_text}\n"

    # research/YYYY-MM-DD-research.md — candidate scoring and evaluation
    research_content = f"# Research & Scoring — {date_str}\n\n"
    research_content += f"## Track 1: MBSE / SysML / Systems Engineering\n\n{mbse_evaluation}\n"
    if world_evaluation:
        research_content += f"\n---\n\n## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n{world_evaluation}\n"

    # critique/YYYY-MM-DD-critique.md — final drafts alongside quality review notes
    critique_content = f"# Drafts & Quality Review — {date_str}\n\n"
    critique_content += "## Final Drafts\n\n"
    if mbse_drafts.has_drafts:
        critique_content += f"### Track 1: MBSE / SysML / Systems Engineering\n\n{mbse_drafts.raw_text}\n"
    if world_drafts.has_drafts:
        critique_content += f"\n### Track 2: World Events\n\n{world_drafts.raw_text}\n"
    if custom_drafts:
        for i, (topic, draft) in enumerate(custom_drafts, 1):
            if draft.has_drafts:
                critique_content += f"\n### Custom Topic {i}: {topic}\n\n{draft.raw_text}\n"
    if review and review.raw_text:
        critique_content += f"\n---\n\n## Quality Review\n\n{review.raw_text}\n"
    else:
        critique_content += "\n---\n\n## Quality Review\n\n_No drafts to review._\n"

    posts_path = POSTS_DIR / f"{date_str}-post.md"
    research_path = RESEARCH_DIR / f"{date_str}-research.md"
    critique_path = CRITIQUE_DIR / f"{date_str}-critique.md"

    posts_path.write_text(posts_content, encoding="utf-8")
    research_path.write_text(research_content, encoding="utf-8")
    critique_path.write_text(critique_content, encoding="utf-8")

    return posts_path, research_path, critique_path
