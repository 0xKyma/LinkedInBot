"""
LinkedIn Post Drafting Agent — multi-agent system entry point.

Agents:
  MBSEResearchAgent        — web search + scoring for MBSE/SysML content
  WorldEventsResearchAgent — web search + scoring for defence/energy/geopolitics
  MBSEDraftingAgent        — draft 3 angles per MBSE item
  WorldEventsDraftingAgent — draft 2 angles for selected world event
  QualityAgent             — review all drafts for voice compliance
  (revision loop)          — rewrite flagged posts, max 2 rounds

Execution DAG:
  [MBSEResearch] ──┐                             ┌── [MBSEDrafting] ──┐
  (parallel)       ├──► (await both) ─────────── ┤   (parallel)       ├──► QualityAgent ──► revise loop ──► output
  [WorldResearch] ─┘                             └── [WorldDrafting] ─┘

Usage:
    python main.py            # full run
    python main.py --dry-run  # print prompts without calling Claude
    python main.py --mbse-only
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from anthropic import AsyncAnthropic

from agents.research import MBSEResearchAgent, WorldEventsResearchAgent
from agents.drafting import MBSEDraftingAgent, WorldEventsDraftingAgent, DraftResult
from agents.custom import CustomTopicAgent
from agents.quality import QualityAgent, ReviewResult
from output import write_post_file, get_used_sources
from prompts.research import SEARCH_USER_PROMPT_TEMPLATE, WORLD_EVENTS_USER_PROMPT_TEMPLATE

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Adelaide")

_EMPTY_DRAFT = DraftResult(track="", raw_text="", has_drafts=False)
_EMPTY_REVIEW = ReviewResult(raw_text="", has_failures=False)

MAX_REVISION_ROUNDS = 2


async def run(
    mbse_only: bool = False,
    topics: list[str] | None = None,
    topic_angles: int = 3,
) -> int:
    today = dt.datetime.now(ZoneInfo(TIMEZONE)).date()
    cutoff = (today - dt.timedelta(days=10)).isoformat()
    cutoff_14d = (today - dt.timedelta(days=14)).isoformat()

    client = AsyncAnthropic()

    mbse_researcher = MBSEResearchAgent(client)
    world_researcher = WorldEventsResearchAgent(client)
    mbse_drafter = MBSEDraftingAgent(client)
    world_drafter = WorldEventsDraftingAgent(client)
    custom_agent = CustomTopicAgent(client)
    quality = QualityAgent(client)

    # Load sources used in the last 2 runs to avoid repeats
    skip_urls = get_used_sources(n=2)
    if skip_urls:
        print(f"Excluding {len(skip_urls)} source(s) already covered in the last 2 runs.")

    # Phase 1: parallel research
    print("Step 1: Searching MBSE/SysML candidates and world events in parallel...")
    if mbse_only:
        mbse_research = await mbse_researcher.run(today, skip_urls=skip_urls)
        world_research = None
    else:
        mbse_research, world_research = await asyncio.gather(
            mbse_researcher.run(today, skip_urls=skip_urls),
            world_researcher.run(today, skip_urls=skip_urls),
        )

    print(mbse_research.raw_text)
    if world_research:
        print(world_research.raw_text)

    # Phase 2: parallel drafting
    print("\nStep 2: Drafting posts...")
    if mbse_only:
        if mbse_research.has_candidates:
            mbse_drafts = await mbse_drafter.run(mbse_research)
        else:
            print("No qualifying MBSE candidates found today.")
            mbse_drafts = _EMPTY_DRAFT
        world_drafts = _EMPTY_DRAFT
    else:
        async def _draft_mbse():
            if mbse_research.has_candidates:
                return await mbse_drafter.run(mbse_research)
            print("No qualifying MBSE candidates found today.")
            return _EMPTY_DRAFT

        async def _draft_world():
            if world_research and world_research.has_candidates:
                return await world_drafter.run(world_research)
            print("No qualifying world event found today.")
            return _EMPTY_DRAFT

        mbse_drafts, world_drafts = await asyncio.gather(_draft_mbse(), _draft_world())

    # Phase 3: quality review + revision loop
    review: ReviewResult = _EMPTY_REVIEW
    if mbse_drafts.has_drafts or world_drafts.has_drafts:
        print("\nStep 3: Quality review...")
        review = await quality.run(mbse_drafts, world_drafts)
        print(review.raw_text)

        for round_num in range(1, MAX_REVISION_ROUNDS + 1):
            if not review.has_failures:
                print(f"Quality check passed (round {round_num - 1} revisions).")
                break
            print(f"\nStep 3b: Revising flagged posts (round {round_num})...")

            async def _revise_mbse():
                if mbse_drafts.has_drafts and review.failed_notes:
                    return await mbse_drafter.revise(mbse_drafts, review.failed_notes)
                return mbse_drafts

            async def _revise_world():
                if world_drafts.has_drafts and review.failed_notes:
                    return await world_drafter.revise(world_drafts, review.failed_notes)
                return world_drafts

            mbse_drafts, world_drafts = await asyncio.gather(_revise_mbse(), _revise_world())
            review = await quality.run(mbse_drafts, world_drafts)
            print(review.raw_text)
        else:
            if review.has_failures:
                print(f"Some posts still have issues after {MAX_REVISION_ROUNDS} revision rounds.")

    # Phase 3b: custom topics (run in parallel with each other)
    custom_results: list[tuple[str, DraftResult]] = []
    if topics:
        print(f"\nStep 3b: Drafting {len(topics)} custom topic(s)...")
        results = await asyncio.gather(
            *(custom_agent.run(t, topic_angles) for t in topics)
        )
        custom_results = list(zip(topics, results))

    # Phase 4: write output
    world_eval_text = world_research.raw_text if world_research else ""
    posts_path, research_path, critique_path = write_post_file(
        today,
        mbse_research.raw_text,
        mbse_drafts,
        world_eval_text,
        world_drafts,
        review if review.raw_text else None,
        custom_drafts=custom_results or None,
    )
    print(f"\nWrote drafts:   {posts_path}")
    print(f"Wrote research: {research_path}")
    print(f"Wrote critique: {critique_path}\n")
    if mbse_drafts.has_drafts:
        print("--- MBSE DRAFTS ---\n", mbse_drafts.raw_text)
    if world_drafts.has_drafts:
        print("--- WORLD EVENTS DRAFTS ---\n", world_drafts.raw_text)
    for topic, draft in custom_results:
        if draft.has_drafts:
            print(f"--- CUSTOM: {topic} ---\n", draft.raw_text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the search prompts without calling Claude.")
    p.add_argument("--mbse-only", action="store_true",
                   help="Skip the world events track (saves ~2 API calls).")
    p.add_argument("--topic", action="append", metavar="URL_OR_TEXT", dest="topics",
                   help="Add a specific article or topic to draft posts about. "
                        "Can be a URL or free text. Repeatable.")
    p.add_argument("--topic-angles", type=int, default=3, metavar="N",
                   help="Number of post angles to draft per custom topic (default: 3, max: 5).")
    args = p.parse_args(argv)

    today = dt.datetime.now(ZoneInfo(TIMEZONE)).date()
    cutoff = (today - dt.timedelta(days=10)).isoformat()
    cutoff_14d = (today - dt.timedelta(days=14)).isoformat()

    if args.dry_run:
        skip_urls = get_used_sources(n=2)
        from agents.research import _format_exclude
        exclude_str = _format_exclude(skip_urls)
        print("=== STEP 1: MBSE Search & Evaluate ===\n")
        print(SEARCH_USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(), cutoff=cutoff, exclude_sources=exclude_str
        ))
        print("\n=== STEP 2: MBSE Draft ===\n")
        print("(drafts from shortlist — no web search in this step)")
        if not args.mbse_only:
            print("\n=== STEP 3: World Events Search & Evaluate ===\n")
            print(WORLD_EVENTS_USER_PROMPT_TEMPLATE.format(
                today=today.isoformat(), cutoff_14d=cutoff_14d, exclude_sources=exclude_str
            ))
            print("\n=== STEP 4: World Events Draft ===\n")
            print("(drafts from selected event — no web search in this step)")
        if args.topics:
            for t in args.topics:
                print(f"\n=== CUSTOM TOPIC: {t} ===\n")
                print(f"(targeted search + {args.topic_angles} angle(s) drafted)")
        print("\n=== STEP 5: Quality Review ===\n")
        print("(all drafts reviewed against voice checklist, revisions applied if needed)")
        return 0

    return asyncio.run(run(
        mbse_only=args.mbse_only,
        topics=args.topics,
        topic_angles=min(args.topic_angles, 5),
    ))


if __name__ == "__main__":
    sys.exit(main())
