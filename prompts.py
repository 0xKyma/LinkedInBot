"""
LinkedIn Post Drafting Agent

Pulls fresh items from a curated set of MBSE / Systems Engineering / SysML RSS
feeds, asks Claude to pick the most LinkedIn-worthy stories of the day, and
drafts three post options in Photi's voice. Output is written to
posts/YYYY-MM-DD.md and committed to the repo by GitHub Actions (or manually).

Usage:
    python linkedin_agent.py            # full run
    python linkedin_agent.py --dry-run  # skip Claude call, just show feed harvest
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import feedparser
import yaml
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = REPO_ROOT / "sources.yaml"
PROMPTS_FILE = REPO_ROOT / "scripts" / "prompts.py"
POSTS_DIR = REPO_ROOT / "posts"
SEEN_FILE = REPO_ROOT / "scripts" / ".seen_items.json"

POSTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-5"  # adjust if you want to switch model
MAX_FEED_ITEMS_PER_SOURCE = 5
LOOKBACK_DAYS = 3  # how far back to consider items "fresh"
TARGET_CANDIDATES = 12  # how many items to send to Claude for selection


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FeedItem:
    source: str
    title: str
    link: str
    summary: str
    published: str  # ISO date string

    @property
    def fingerprint(self) -> str:
        return hashlib.sha1(self.link.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Feed harvesting
# ---------------------------------------------------------------------------

def load_sources() -> list[dict]:
    with SOURCES_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        with SEEN_FILE.open("r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen: set[str]) -> None:
    # keep the file from growing forever
    trimmed = list(seen)[-2000:]
    with SEEN_FILE.open("w", encoding="utf-8") as f:
        json.dump(trimmed, f)


def parse_published(entry) -> dt.datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            try:
                return dt.datetime(*val[:6], tzinfo=dt.timezone.utc)
            except Exception:
                continue
    return dt.datetime.now(dt.timezone.utc)


def harvest_feed(source: dict) -> list[FeedItem]:
    name = source["name"]
    url = source["url"]
    items: list[FeedItem] = []

    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        print(f"[WARN] {name}: parse error {e}", file=sys.stderr)
        return items

    if parsed.bozo and not parsed.entries:
        print(f"[WARN] {name}: no entries (bozo={parsed.bozo_exception})",
              file=sys.stderr)
        return items

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=LOOKBACK_DAYS)

    for entry in parsed.entries[:MAX_FEED_ITEMS_PER_SOURCE]:
        published = parse_published(entry)
        if published < cutoff:
            continue

        summary = (
            entry.get("summary")
            or entry.get("description")
            or ""
        )
        # strip HTML crudely so we don't blow tokens on markup
        summary = strip_html(summary)[:600]

        items.append(FeedItem(
            source=name,
            title=entry.get("title", "Untitled").strip(),
            link=entry.get("link", "").strip(),
            summary=summary,
            published=published.isoformat(),
        ))

    return items


def strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def harvest_all() -> list[FeedItem]:
    all_items: list[FeedItem] = []
    sources = load_sources()
    print(f"Loading {len(sources)} sources...")

    for src in sources:
        items = harvest_feed(src)
        print(f"  {src['name']}: {len(items)} fresh items")
        all_items.extend(items)
        time.sleep(0.5)  # be polite

    return all_items


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

def build_user_prompt(items: list[FeedItem]) -> str:
    lines = ["Today's harvested items (most recent first):", ""]
    for i, it in enumerate(items, 1):
        lines.append(f"[{i}] {it.title}")
        lines.append(f"    Source: {it.source}")
        lines.append(f"    Link: {it.link}")
        lines.append(f"    Published: {it.published}")
        if it.summary:
            lines.append(f"    Summary: {it.summary}")
        lines.append("")
    lines.append("Now produce the three post options as instructed.")
    return "\n".join(lines)


def call_claude(items: list[FeedItem]) -> str:
    # Late import so --dry-run works without the package configured
    from prompts import SYSTEM_PROMPT

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": build_user_prompt(items)},
        ],
    )

    # Concatenate text blocks
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_post_file(date: dt.date, items_used: list[FeedItem],
                    claude_output: str) -> Path:
    path = POSTS_DIR / f"{date.isoformat()}.md"

    lines = [
        f"# LinkedIn Drafts — {date.isoformat()}",
        "",
        "## Sources considered",
        "",
    ]
    for it in items_used:
        lines.append(f"- **{it.title}** — {it.source}")
        lines.append(f"  {it.link}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Drafts")
    lines.append("")
    lines.append(claude_output)
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Harvest feeds and print, but don't call Claude.")
    args = p.parse_args(argv)

    items = harvest_all()
    if not items:
        print("No fresh items today. Exiting.")
        return 0

    # dedupe against history, then sort newest first, take top N
    seen = load_seen()
    unseen = [i for i in items if i.fingerprint not in seen]
    print(f"\n{len(unseen)} unseen items "
          f"(after filtering {len(items) - len(unseen)} already covered)")

    unseen.sort(key=lambda i: i.published, reverse=True)
    candidates = unseen[:TARGET_CANDIDATES]

    if args.dry_run:
        print("\n--- DRY RUN: candidates that would go to Claude ---\n")
        for c in candidates:
            print(f"- {c.title} [{c.source}]")
            print(f"  {c.link}")
        return 0

    if not candidates:
        print("No new candidates after dedupe. Exiting.")
        return 0

    print(f"\nCalling Claude with {len(candidates)} candidates...")
    output = call_claude(candidates)

    today = dt.date.today()
    path = write_post_file(today, candidates, output)
    print(f"\nWrote {path}")

    # update seen
    for c in candidates:
        seen.add(c.fingerprint)
    save_seen(seen)

    return 0


if __name__ == "__main__":
    # ensure scripts/ is on path so we can `import prompts`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
