"""
LinkedIn Post Drafting Agent

Uses Claude with web search to find, evaluate, and rank recent SysML / MBSE /
Systems Engineering content, then drafts three LinkedIn post options in
Photi's voice. Output is written to posts/YYYY-MM-DD.md.

Usage:
    python prompts.py            # full run
    python prompts.py --dry-run  # print prompt without calling Claude
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent
POSTS_DIR = REPO_ROOT / "posts"
POSTS_DIR.mkdir(exist_ok=True)

MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Audience definition (used in both steps)
# ---------------------------------------------------------------------------

AUDIENCE = """
Photi's LinkedIn audience (~60–70% of followers):
- Mid-to-senior Systems Engineers and MBSE leads in aerospace, defense, automotive, and space
- Architects and technical leads evaluating or already using SysML v1/v2 tooling
- Program managers with enough technical depth to care about modeling methodology
- A smaller slice of students and early-career engineers who follow for career signal

They are NOT:
- Software engineers who stumbled in from a general tech feed
- Executives who want high-level digital transformation talking points
- Beginners who need "what is MBSE" explained
"""

# ---------------------------------------------------------------------------
# Voice examples — patterns from top-performing technical LinkedIn posts
# ---------------------------------------------------------------------------
# These are stylistic templates, not content to copy verbatim.

VOICE_EXAMPLES = """
VOICE AND FORMAT RULES (derived from top-performing technical LinkedIn posts):

Structure:
- Line 1 is everything. It must stand alone and create tension or curiosity.
  It is the only line visible before "see more." Make it count.
- Use white space aggressively. Two to four sentences per paragraph max.
- No walls of text. No corporate speak. No passive voice.
- Lists only when each item genuinely earns its own line.
- End with a single, specific question — not "What do you think?" but something
  that forces the reader to take a position.

Opening hook patterns that perform well:
  Contrarian:    "Everyone's adopting SysML v2. Almost no one is ready for what comes after."
  Confession:    "Three years ago I would have told you SysML v2 was years away from mattering. I was wrong."
  Surprising gap: "We've had a published SysML v2 spec for months. The tooling still hasn't caught up."
  Hard question: "If your MBSE model disappeared tomorrow, would your program actually slow down?"
  Specific stat:  "Of the last eight MBSE programs I've reviewed, two had interfaces that matched their models."

Tone markers:
- Opinionated but grounded in practice ("in my experience", "on programs I've worked")
- Skeptical of hype, respectful of effort
- Calls out the gap between what vendors claim and what engineers experience
- Occasionally dry. Never sarcastic about individuals.
- Uses "we" for the engineering community, "I" for personal experience

What to avoid:
- "I'm excited to share..."
- "In today's fast-paced world..."
- "Game-changer", "revolutionary", "paradigm shift"
- More than three hashtags
- Tagging vendors unless the post is genuinely praising specific functionality
- Ending with "Drop a comment below!"

Example post structure (150–250 words):

[Hook — 1 punchy line]

[2–3 sentences expanding the tension or stakes]

[Concrete insight, observation, or what you actually found — this is the meat]

[Your personal take or the uncomfortable implication]

[One specific question that forces a position]

#MBSE #SysML #SystemsEngineering
"""

# ---------------------------------------------------------------------------
# Step 1: Search and evaluate
# ---------------------------------------------------------------------------

SEARCH_SYSTEM_PROMPT = f"""
You are a research assistant for Photi Manolakis, a senior Systems Engineer and
MBSE practitioner. Your job is to find and critically evaluate recent content
about SysML, MBSE, and Systems Engineering so she can write informed LinkedIn posts.

{AUDIENCE}

TOPIC PRIORITY (high to low):
1. SysML v2 — spec updates, OMG balloting, tooling support, adoption reports, migration guides
2. SysML v1 — community usage trends, v1-to-v2 migration discussions, deprecation signals
3. MBSE methodology — new frameworks, ROI studies, failure post-mortems, process debates
4. Digital engineering standards — DoD DE Strategy updates, UPDM, UAF, OpenMBEE, Capella
5. Systems Engineering research — peer-reviewed papers with practical implications
6. Adjacent signals — formal methods, model-based testing, digital twin integration with SE

EXCLUDE — do not surface these:
- Vendor press releases with no technical substance ("Company X announces partnership")
- "Introduction to MBSE / SysML" evergreen explainers with no new angle
- Paywalled content with no accessible summary or preprint
- Blog posts older than 10 days
- Anything primarily about software engineering or DevOps that only mentions SE in passing

EVALUATION CRITERIA — score each candidate 1–5 on:
  Relevance:    How directly does it address SysML/MBSE practice?
  Novelty:      Is this genuinely new information or a fresh angle on a live debate?
  Practicality: Can a working systems engineer act on or argue with this?
  Timeliness:   How recent is it? (Last 3 days = 5, 4–7 days = 3, older = 1)
  Debate potential: Will this make Photi's audience agree, disagree, or share?

After scoring, select the TOP 2–3 items (highest combined score) to write posts about.
If you cannot find at least 2 strong candidates (combined score ≥ 15), say so explicitly
rather than padding with weak content.

OUTPUT FORMAT for this step:
## Candidates Found
For each item found (before filtering):
  - Title, source, URL, date, brief summary (2 sentences max)

## Scored Shortlist
For each item you're keeping:
  - Title + URL
  - Scores: Relevance X | Novelty X | Practicality X | Timeliness X | Debate X | Total: X/25
  - One sentence on why this is worth a post

## Selected for Drafting
List the 2–3 items you will draft posts from.
"""

SEARCH_USER_PROMPT_TEMPLATE = """Today is {today}.

Search the web for content published in the last 10 days matching the topic
priorities above. Cast a wide net first (8–12 candidates), then score and
filter down to the 2–3 strongest items.

Search queries to run (run all of them):
- "SysML v2" after:{cutoff}
- "SysML 2.0" OMG after:{cutoff}
- MBSE "systems engineering" after:{cutoff}
- "digital engineering" DoD OR aerospace OR defense after:{cutoff}
- SysML tooling Capella OR Cameo OR "Eclipse Papyrus" after:{cutoff}
- "model-based systems engineering" paper OR study OR report after:{cutoff}
"""

# ---------------------------------------------------------------------------
# Step 2: Draft posts
# ---------------------------------------------------------------------------

DRAFT_SYSTEM_PROMPT = f"""
You are a ghostwriter for Photi Manolakis, a senior Systems Engineer and MBSE
practitioner. You have been given a scored shortlist of recent content. Your job
is to draft three distinct, high-quality LinkedIn posts in her voice.

{AUDIENCE}

{VOICE_EXAMPLES}

DRAFTING RULES:
- Each post must be based on something specific from the shortlist — no generic takes
- Three posts should offer meaningfully different angles, not the same take reworded:
    Option 1: Practitioner angle — what does this mean for someone doing MBSE today?
    Option 2: Industry/trend angle — what does this signal about where SE is heading?
    Option 3: Contrarian or uncomfortable angle — what's the thing nobody wants to say about this?
- 150–250 words each
- Include the source link naturally in the post or as a "Source:" line at the end
- 2–3 hashtags, placed at the very end

OUTPUT FORMAT:
### Option 1 — [angle label]
[post text]

### Option 2 — [angle label]
[post text]

### Option 3 — [angle label]
[post text]
"""


# ---------------------------------------------------------------------------
# Claude calls
# ---------------------------------------------------------------------------

def run_search_and_evaluate(client: Anthropic, today: str, cutoff: str) -> str:
    """Step 1: web search + scoring. Returns the evaluation text."""
    user_prompt = SEARCH_USER_PROMPT_TEMPLATE.format(today=today, cutoff=cutoff)

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        system=SEARCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    parts = [block.text for block in msg.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip()


def run_draft(client: Anthropic, evaluation: str) -> str:
    """Step 2: draft three posts from the evaluated shortlist."""
    user_prompt = (
        "Here is the scored shortlist of content to write about:\n\n"
        + evaluation
        + "\n\nNow draft the three LinkedIn post options as instructed."
    )

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=DRAFT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    parts = [block.text for block in msg.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_post_file(date: dt.date, evaluation: str, drafts: str) -> Path:
    path = POSTS_DIR / f"{date.isoformat()}.md"
    content = (
        f"# LinkedIn Drafts — {date.isoformat()}\n\n"
        f"## Research & Scoring\n\n{evaluation}\n\n"
        f"---\n\n"
        f"## Drafts\n\n{drafts}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the search prompt without calling Claude.")
    args = p.parse_args(argv)

    today = dt.date.today()
    cutoff = (today - dt.timedelta(days=10)).isoformat()

    if args.dry_run:
        print("=== STEP 1: Search & Evaluate ===\n")
        print(SEARCH_USER_PROMPT_TEMPLATE.format(today=today.isoformat(), cutoff=cutoff))
        print("\n=== STEP 2: Draft ===\n")
        print("(drafts from shortlist — no web search in this step)")
        return 0

    client = Anthropic()

    print("Step 1: Searching and evaluating candidates...")
    evaluation = run_search_and_evaluate(client, today.isoformat(), cutoff)
    print(evaluation)

    if "cannot find" in evaluation.lower() or "no strong candidates" in evaluation.lower():
        print("\nNot enough strong candidates found today. Exiting.")
        return 0

    print("\nStep 2: Drafting posts...")
    drafts = run_draft(client, evaluation)

    path = write_post_file(today, evaluation, drafts)
    print(f"\nWrote {path}\n")
    print(drafts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
