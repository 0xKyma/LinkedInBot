"""
World Events LinkedIn Post Script — standalone entry point.

Runs the world events track only:
  WorldEventsResearchAgent — web search + scoring for defence/energy/geopolitics
  WorldEventsDraftingAgent — draft 2 angles for selected world event
  QualityAgent             — review drafts for voice compliance
  (revision loop)          — rewrite flagged posts, max 2 rounds

Usage:
    python world_events.py            # full run
    python world_events.py --dry-run  # print prompts without calling Claude
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import os
import sys
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")

from agents.base import create_client
from agents.research import WorldEventsResearchAgent
from agents.drafting import WorldEventsDraftingAgent, DraftResult
from agents.quality import QualityAgent, ReviewResult
from output import write_post_file, get_used_sources
from prompts.research import WORLD_EVENTS_USER_PROMPT_TEMPLATE

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Adelaide")

_EMPTY_DRAFT = DraftResult(track="", raw_text="", has_drafts=False)
_EMPTY_REVIEW = ReviewResult(raw_text="", has_failures=False)

MAX_REVISION_ROUNDS = 2


async def run() -> int:
    today = dt.datetime.now(ZoneInfo(TIMEZONE)).date()

    client = create_client()

    world_researcher = WorldEventsResearchAgent(client)
    world_drafter = WorldEventsDraftingAgent(client)
    quality = QualityAgent(client)

    skip_urls = get_used_sources()
    if skip_urls:
        print(f"Excluding {len(skip_urls)} source(s) from covered sources list.")

    print("Step 1: Searching world events candidates...")
    world_research = await world_researcher.run(today, skip_urls=skip_urls)
    print(world_research.raw_text)

    print("\nStep 2: Drafting world events post...")
    if world_research.has_candidates:
        world_drafts = await world_drafter.run(world_research)
    else:
        print("No qualifying world event found today.")
        world_drafts = _EMPTY_DRAFT

    review: ReviewResult = _EMPTY_REVIEW
    if world_drafts.has_drafts:
        print("\nStep 3: Quality review...")
        review = await quality.run(_EMPTY_DRAFT, world_drafts)
        print(review.raw_text)

        for round_num in range(1, MAX_REVISION_ROUNDS + 1):
            if not review.has_failures:
                print(f"Quality check passed (round {round_num - 1} revisions).")
                break
            print(f"\nStep 3b: Revising flagged posts (round {round_num})...")
            if review.world_failed_notes:
                world_drafts = await world_drafter.revise(world_drafts, review.world_failed_notes)
            review = await quality.run(_EMPTY_DRAFT, world_drafts)
            print(review.raw_text)
        else:
            if review.has_failures:
                print(f"Some posts still have issues after {MAX_REVISION_ROUNDS} revision rounds.")

    posts_path, research_path, critique_path = write_post_file(
        today,
        "",
        _EMPTY_DRAFT,
        world_research.raw_text,
        world_drafts,
        review if review.raw_text else None,
    )
    print(f"\nWrote drafts:   {posts_path}")
    print(f"Wrote research: {research_path}")
    print(f"Wrote critique: {critique_path}\n")
    if world_drafts.has_drafts:
        print("--- WORLD EVENTS DRAFTS ---\n", world_drafts.raw_text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the search prompts without calling Claude.")
    args = p.parse_args(argv)

    if args.dry_run:
        today = dt.datetime.now(ZoneInfo(TIMEZONE)).date()
        cutoff_14d = (today - dt.timedelta(days=14)).isoformat()
        skip_urls = get_used_sources()
        from agents.research import _format_exclude
        exclude_str = _format_exclude(skip_urls)
        print("=== STEP 1: World Events Search & Evaluate ===\n")
        print(WORLD_EVENTS_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(), cutoff_14d=cutoff_14d, exclude_sources=exclude_str
        ))
        print("\n=== STEP 2: World Events Draft ===\n")
        print("(drafts from selected event — no web search in this step)")
        print("\n=== STEP 3: Quality Review ===\n")
        print("(drafts reviewed against voice checklist, revisions applied if needed)")
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
