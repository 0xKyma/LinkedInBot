"""
LinkedIn post drafter — interactive or scripted.

Interactive:
    python draft.py
    Follow the prompts to select a mode and provide your input.

Non-interactive (e.g. from CI / GitHub Actions):
    python draft.py --topic "https://example.com/article"
    python draft.py --mode info --topic "some dot points" --angle Contrarian
    python draft.py --mode search --topic "digital twins in defence"

One post is drafted per run (Practitioner angle by default).
Output is saved to manual/YYYY-MM-DD-HHMM.md — no research or critique files.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from agents.base import create_client
from agents.drafting import DraftResult, MBSEDraftingAgent
from agents.manual import ManualDraftAgent
from agents.quality import QualityAgent

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Adelaide")
MANUAL_DIR = Path(__file__).resolve().parent / "manual"
MAX_REVISION_ROUNDS = 2
_EMPTY = DraftResult(track="", raw_text="", has_drafts=False)

ANGLES = {
    "1": "Practitioner",
    "2": "Contrarian",
    "3": "Industry/trend",
    "4": "SE lens",
    "5": "Systems thinking",
}

# Input modes. "url" and "search" both research the topic via web search;
# "info" drafts directly from user-provided text with no search.
MODES = {
    "url": "url",       # paste a link; the agent researches and drafts
    "info": "info",     # paste dot points/guidance; draft directly from input
    "search": "search", # describe a topic; the agent searches and drafts
}


def _ask(prompt: str, default: str = "") -> str:
    val = input(prompt).strip()
    return val if val else default


def _collect_multiline(intro: str) -> str:
    print(intro)
    print("Press Enter on a blank line when done.\n")
    lines: list[str] = []
    while True:
        line = input()
        if not line and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


async def draft_post(mode: str, topic: str, angle: str) -> int:
    """Draft one post from the given mode/topic/angle, review it, and save it."""
    client = create_client()
    agent = ManualDraftAgent(client)
    quality = QualityAgent(client)
    reviser = MBSEDraftingAgent(client)

    print(f"\nDrafting ({angle} angle)...\n")

    if mode == "info":
        draft = await agent.run_from_info(topic, angle)
    else:  # "url" or "search"
        draft = await agent.run_from_source(topic, angle)

    # Quality review + revision loop
    review = await quality.run(draft, _EMPTY)
    for round_num in range(1, MAX_REVISION_ROUNDS + 1):
        if not review.has_failures:
            break
        print(f"Revising (round {round_num})...")
        draft = await reviser.revise(draft, review.failed_notes)
        review = await quality.run(draft, _EMPTY)
    else:
        if review.has_failures:
            print("Note: some quality issues remain after maximum revision rounds.")

    if not review.has_failures:
        print("Quality check passed.\n")

    # Save final post only
    MANUAL_DIR.mkdir(exist_ok=True)
    now = dt.datetime.now(ZoneInfo(TIMEZONE))
    out_path = MANUAL_DIR / f"{now.strftime('%Y-%m-%d-%H%M')}.md"
    out_path.write_text(
        f"# LinkedIn Draft — {now.strftime('%Y-%m-%d %H:%M')}\n\n{draft.raw_text}\n",
        encoding="utf-8",
    )

    print(f"Saved: {out_path}\n")
    print("--- DRAFT ---\n")
    print(draft.raw_text)
    return 0


def _resolve_angle(value: str) -> str | None:
    """Accept an angle by number ('1'-'5') or by name ('Practitioner', ...)."""
    if value in ANGLES:
        return ANGLES[value]
    for name in ANGLES.values():
        if value.strip().lower() == name.lower():
            return name
    return None


async def interactive() -> int:
    print("\n=== LinkedIn Post Drafter ===\n")
    print("How would you like to create your post?")
    print("  1. Article URL  — paste a link; the agent researches and drafts")
    print("  2. Your info    — paste dot points or guidance; draft directly from your input")
    print("  3. Topic search — describe a topic; the agent searches and drafts\n")

    choice = _ask("Enter 1, 2, or 3: ")
    mode = {"1": "url", "2": "info", "3": "search"}.get(choice)
    if mode is None:
        print("Invalid selection. Please enter 1, 2, or 3.")
        return 1

    print()

    if mode == "url":
        topic = _ask("Paste the URL: ")
        if not topic:
            print("No URL provided.")
            return 1
    elif mode == "info":
        topic = _collect_multiline("Enter your dot points or guidance:")
        if not topic:
            print("No input provided.")
            return 1
    else:
        topic = _ask("Describe the topic to search for: ")
        if not topic:
            print("No topic provided.")
            return 1

    print()
    print("Which angle?")
    for k, v in ANGLES.items():
        print(f"  {k}. {v}")
    angle = ANGLES.get(_ask("\nEnter 1–5 (press Enter for Practitioner): ", "1"), "Practitioner")

    return await draft_post(mode, topic, angle)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Draft one LinkedIn post (manual track).")
    p.add_argument("--mode", choices=list(MODES), default="url",
                   help="url: research a link; info: draft from your text; "
                        "search: research a topic. Default: url.")
    p.add_argument("--topic", metavar="URL_OR_TEXT",
                   help="URL, dot points, or topic. If omitted, runs interactively.")
    p.add_argument("--angle", default="Practitioner", metavar="ANGLE",
                   help="Post angle by name (Practitioner, Contrarian, Industry/trend, "
                        "SE lens, Systems thinking) or number 1–5. Default: Practitioner.")
    args = p.parse_args(argv)

    # No topic supplied → fall back to the interactive prompt flow.
    if not args.topic:
        return asyncio.run(interactive())

    angle = _resolve_angle(args.angle)
    if angle is None:
        print(f"Invalid angle: {args.angle!r}. "
              f"Choose one of: {', '.join(ANGLES.values())} (or 1–5).")
        return 1

    return asyncio.run(draft_post(args.mode, args.topic, angle))


if __name__ == "__main__":
    sys.exit(main())
