"""
LinkedIn Post Drafting Agent — MBSE/SysML track entry point.

Agents:
  MBSEResearchAgent — web search + scoring for MBSE/SysML content
  MBSEDraftingAgent — draft 4 angles per MBSE item
  QualityAgent      — review all drafts for voice compliance
  (revision loop)   — rewrite flagged posts, max 2 rounds

For the world events track, run world_events.py instead.

Usage:
    python main.py            # full run
    python main.py --dry-run  # print prompts without calling Claude
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

from anthropic import AsyncAnthropic

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")

from agents.research import MBSEResearchAgent
from agents.drafting import MBSEDraftingAgent, DraftResult
from agents.custom import CustomTopicAgent
from agents.quality import QualityAgent, ReviewResult
from output import write_post_file, get_used_sources
from prompts.research import SEARCH_USER_PROMPT_TEMPLATE

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Adelaide")

_EMPTY_DRAFT = DraftResult(track="", raw_text="", has_drafts=False)
_EMPTY_REVIEW = ReviewResult(raw_text="", has_failures=False)

MAX_REVISION_ROUNDS = 2


async def run(
    topics: list[str] | None = None,
    topic_angles: int = 3,
) -> int:
    today = dt.datetime.now(ZoneInfo(TIMEZONE)).date()

    client = AsyncAnthropic()

    mbse_researcher = MBSEResearchAgent(client)
    mbse_drafter = MBSEDraftingAgent(client)
    custom_agent = CustomTopicAgent(client)
    quality = QualityAgent(client)

    skip_urls = get_used_sources()
    if skip_urls:
        print(f"Excluding {len(skip_urls)} source(s) from covered sources list.")

    print("Step 1: Searching MBSE/SysML candidates...")
    mbse_research = await mbse_researcher.run(today, skip_urls=skip_urls)
    print(mbse_research.raw_text)

    print("\nStep 2: Drafting posts...")
    if mbse_research.has_candidates:
        mbse_drafts = await mbse_drafter.run(mbse_research)
    else:
        print("No qualifying MBSE candidates found today.")
        mbse_drafts = _EMPTY_DRAFT

    review: ReviewResult = _EMPTY_REVIEW
    if mbse_drafts.has_drafts:
        print("\nStep 3: Quality review...")
        review = await quality.run(mbse_drafts, _EMPTY_DRAFT)
        print(review.raw_text)

        for round_num in range(1, MAX_REVISION_ROUNDS + 1):
            if not review.has_failures:
                print(f"Quality check passed (round {round_num - 1} revisions).")
                break
            print(f"\nStep 3b: Revising flagged posts (round {round_num})...")
            if review.mbse_failed_notes:
                mbse_drafts = await mbse_drafter.revise(mbse_drafts, review.mbse_failed_notes)
            review = await quality.run(mbse_drafts, _EMPTY_DRAFT)
            print(review.raw_text)
        else:
            if review.has_failures:
                print(f"Some posts still have issues after {MAX_REVISION_ROUNDS} revision rounds.")

    custom_results: list[tuple[str, DraftResult]] = []
    if topics:
        print(f"\nStep 3b: Drafting {len(topics)} custom topic(s)...")
        results = await asyncio.gather(
            *(custom_agent.run(t, topic_angles) for t in topics)
        )
        custom_results = list(zip(topics, results))

    posts_path, research_path, critique_path = write_post_file(
        today,
        mbse_research.raw_text,
        mbse_drafts,
        "",
        _EMPTY_DRAFT,
        review if review.raw_text else None,
        custom_drafts=custom_results or None,
    )
    print(f"\nWrote drafts:   {posts_path}")
    print(f"Wrote research: {research_path}")
    print(f"Wrote critique: {critique_path}\n")
    if mbse_drafts.has_drafts:
        print("--- MBSE DRAFTS ---\n", mbse_drafts.raw_text)
    for topic, draft in custom_results:
        if draft.has_drafts:
            print(f"--- CUSTOM: {topic} ---\n", draft.raw_text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the search prompts without calling Claude.")
    p.add_argument("--topic", action="append", metavar="URL_OR_TEXT", dest="topics",
                   help="Add a specific article or topic to draft posts about. "
                        "Can be a URL or free text. Repeatable.")
    p.add_argument("--topic-angles", type=int, default=3, metavar="N",
                   help="Number of post angles to draft per custom topic (default: 3, max: 5).")
    args = p.parse_args(argv)

    if args.dry_run:
        today = dt.datetime.now(ZoneInfo(TIMEZONE)).date()
        cutoff = (today - dt.timedelta(days=10)).isoformat()
        skip_urls = get_used_sources()
        from agents.research import _format_exclude
        exclude_str = _format_exclude(skip_urls)
        print("=== STEP 1: MBSE Search & Evaluate ===\n")
        print(SEARCH_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(), cutoff=cutoff, exclude_sources=exclude_str
        ))
        print("\n=== STEP 2: MBSE Draft ===\n")
        print("(drafts from shortlist — no web search in this step)")
        if args.topics:
            for t in args.topics:
                print(f"\n=== CUSTOM TOPIC: {t} ===\n")
                print(f"(targeted search + {args.topic_angles} angle(s) drafted)")
        print("\n=== STEP 3: Quality Review ===\n")
        print("(all drafts reviewed against voice checklist, revisions applied if needed)")
        return 0

    return asyncio.run(run(
        topics=args.topics,
        topic_angles=min(args.topic_angles, 5),
    ))


if __name__ == "__main__":
    sys.exit(main())
