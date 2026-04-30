from __future__ import annotations

import datetime as dt
from pathlib import Path

from agents.drafting import DraftResult
from agents.quality import ReviewResult

REPO_ROOT = Path(__file__).resolve().parent
POSTS_DIR = REPO_ROOT / "posts"
POSTS_DIR.mkdir(exist_ok=True)


def write_post_file(
    date: dt.date,
    mbse_evaluation: str,
    mbse_drafts: DraftResult,
    world_evaluation: str,
    world_drafts: DraftResult,
    review: ReviewResult | None = None,
) -> tuple[Path, Path]:
    date_str = date.isoformat()
    posts_path = POSTS_DIR / f"{date_str}.md"
    research_path = POSTS_DIR / f"{date_str}-research.md"

    # Drafts file
    posts_content = f"# LinkedIn Drafts — {date_str}\n\n"

    if mbse_drafts.has_drafts:
        posts_content += f"## Track 1: MBSE / SysML / Systems Engineering\n\n{mbse_drafts.raw_text}\n"
    else:
        posts_content += "## Track 1: MBSE / SysML / Systems Engineering\n\n_No qualifying candidates found today._\n"

    if world_drafts.has_drafts:
        posts_content += f"\n---\n\n## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n{world_drafts.raw_text}\n"
    elif world_evaluation:
        posts_content += "\n---\n\n## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n_No qualifying event found today._\n"

    # Research file
    research_content = f"# Research & Scoring — {date_str}\n\n"
    research_content += f"## Track 1: MBSE / SysML / Systems Engineering\n\n{mbse_evaluation}\n"

    if world_evaluation:
        research_content += f"\n---\n\n## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n{world_evaluation}\n"

    if review:
        research_content += f"\n---\n\n## Quality Review\n\n{review.raw_text}\n"

    posts_path.write_text(posts_content, encoding="utf-8")
    research_path.write_text(research_content, encoding="utf-8")
    return posts_path, research_path
