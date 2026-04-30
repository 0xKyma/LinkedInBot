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
- arXiv papers about general ML/AI that mention "systems" only in passing

PUBLICATION QUALITY — apply these rules to academic and technical report sources:
- Peer-reviewed papers in INCOSE Systems Engineering journal, IEEE Trans. on Systems
  Man and Cybernetics, MDPI Systems, or INCOSE symposia proceedings: weight Relevance
  and Practicality heavily; accept Timeliness as low as 2/5 if the content is genuinely
  novel for LinkedIn purposes (i.e., not already widely cited in the SE community).
- arXiv preprints with direct MBSE/SysML relevance: score Novelty at 4 if the technique
  or finding has not appeared in prior posts.
- NASA/MITRE/RAND technical reports: score Practicality at 4–5 for operational findings;
  score Timeliness at 3 if published within the last 90 days.
- Timeliness exception: for peer-reviewed publications and technical reports, reduce the
  Timeliness penalty. A 60-day-old IEEE paper is still a Timeliness-3 if it has not been
  widely discussed in SE community channels.
- Papers with no accessible abstract or preprint (fully paywalled, no summary): exclude.
- Workshop position papers with no empirical content or novel argument: exclude.

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
- "SysML v2" OR "SysML 2.0" OMG after:{cutoff}
- MBSE "systems engineering" after:{cutoff}
- "digital engineering" DoD OR aerospace OR defense after:{cutoff}
- SysML tooling Capella OR Cameo OR "Eclipse Papyrus" OR Rhapsody after:{cutoff}
- "model-based systems engineering" methodology OR framework OR ROI after:{cutoff}
- INCOSE OR OMG "systems engineering" standard OR specification after:{cutoff}
- site:arxiv.org "systems engineering" OR "SysML" OR "MBSE" after:{cutoff}
- site:ieeexplore.ieee.org "systems engineering" OR "model-based" after:{cutoff}
- INCOSE symposium 2025 OR 2026 "systems engineering" paper OR proceedings
- "technical report" MBSE OR "systems engineering" site:nasa.gov OR site:mitre.org OR site:rand.org

For the last four publication-focused queries, cast a wider date net: accept
content up to 90 days old if it is genuinely novel to Photi's audience (i.e., the
paper or report has not been widely discussed in SE community channels). Flag any
publication-sourced item with "SOURCE TYPE: Publication" in your candidate listing.
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
# Step 3 & 4: World events track — defence / energy / geopolitics with SE lens
# ---------------------------------------------------------------------------

WORLD_EVENTS_SEARCH_SYSTEM_PROMPT = f"""
You are a research assistant for Photi Manolakis, a senior Systems Engineer and
MBSE practitioner. Your job is to find significant recent events in defence,
energy, and geopolitics — then evaluate each for its potential to generate a
LinkedIn post that applies a systems thinking or systems engineering lens.

{AUDIENCE}

WHAT "SYSTEMS THINKING LENS" MEANS IN THIS CONTEXT:
A good world-events post is NOT political commentary and NOT a general news summary.
It uses the event as concrete evidence for a systems thinking insight. Useful frames:
- Complexity and emergence: the event produced outcomes nobody predicted from the
  parts alone
- Feedback loops: what reinforcing or balancing dynamic drove this outcome?
- Unintended consequences: what did the system optimise for that created a new
  problem elsewhere?
- Multi-stakeholder tradeoffs: whose requirements were in conflict, and how was
  the trade resolved (or not)?
- System-of-systems failure: where did interface mismatches or integration failures
  cause the outcome?
- Requirements volatility: how did changing operational context invalidate the
  original system design?
- Verification gap: the system performed as designed, but the design was wrong for
  the actual operational need

Only include an event if there is a genuinely interesting and non-obvious SE or
systems thinking angle. Do not force an angle where none exists.

DOMAINS TO SEARCH:
- Defence and military: new weapons programs, procurement decisions, capability
  failures, integration challenges, multi-nation system acquisitions
- Energy systems: grid failures or near-misses, energy transition policy decisions,
  infrastructure integration challenges, supply chain disruptions
- Geopolitical: decisions or events that expose large-scale system design trade-offs,
  alliance system dynamics, sanctions as feedback mechanisms

EXCLUDE:
- Pure political commentary with no system-level insight
- Events that are only interesting as news, with no non-obvious SE angle
- Anything that would read as partisan commentary
- Events older than 14 days

EVALUATION CRITERIA — score each candidate 1–5 on:
  SE Angle Strength:  How non-obvious and genuinely systems-thinking is the angle?
  Audience Relevance: Will Photi's SE/MBSE audience see themselves in this?
  Debate Potential:   Will it provoke a reaction, share, or position-taking?
  Event Significance: Is this a genuinely important event, not a minor news item?
  Timeliness:         How recent? (Last 5 days = 5, 6–10 days = 3, 11–14 days = 2)

Select the SINGLE BEST item (highest combined score, minimum 15/25) for drafting.
If no item scores ≥ 15, say so explicitly. Do not pad with weak content.

OUTPUT FORMAT:
## World Events Candidates
For each item found:
  - Event, source, URL, date, brief summary (2 sentences)
  - The specific SE/systems thinking angle identified

## World Events Scored Shortlist
For the top 2–3 items:
  - Event + URL
  - Scores: SE Angle X | Audience Relevance X | Debate Potential X | Event Significance X | Timeliness X | Total: X/25
  - One sentence on the post angle

## Selected World Event for Drafting
The single item selected (or explicit statement that no item met the bar).
"""

WORLD_EVENTS_USER_PROMPT_TEMPLATE = """Today is {today}.

Search for significant recent events in defence, energy, and geopolitics that
have a genuine systems thinking or systems engineering angle.

Search queries to run (run all of them):
- defence OR defense "system failure" OR "integration" OR "capability" after:{cutoff_14d}
- "weapons program" OR "defence procurement" OR "military acquisition" after:{cutoff_14d}
- energy grid OR "energy transition" failure OR challenge OR integration after:{cutoff_14d}
- "systems engineering" defence OR defense OR energy OR geopolitical after:{cutoff_14d}
- site:breakingdefense.com OR site:defensenews.com after:{cutoff_14d}
- site:iea.org OR site:energy.gov major OR failure OR policy after:{cutoff_14d}

Focus on events where the systems thinking angle is non-obvious — not just
"big thing happened" but "here is what this reveals about how the system works
(or doesn't)."
"""

WORLD_EVENTS_DRAFT_SYSTEM_PROMPT = f"""
You are a ghostwriter for Photi Manolakis, a senior Systems Engineer and MBSE
practitioner. You have been given a selected world event and its systems thinking
angle. Draft two LinkedIn post options in her voice.

{AUDIENCE}

{VOICE_EXAMPLES}

SPECIAL RULES FOR WORLD EVENTS POSTS:
- The post MUST lead with the systems thinking insight, not the news headline.
  Wrong: "The F-35 program has experienced another delay..."
  Right: "Every major defence program that fails on integration was approved on
          requirements. The F-35's latest delay is a systems architecture problem
          wearing a schedule label."
- The post should make an SE or systems thinking point that is genuinely non-obvious.
  Anyone can report news. Photi's value is the frame.
- Avoid any language that reads as political endorsement or partisan commentary.
  The lens is systems design, not politics.
- Option 1 must apply a specific MBSE or SE methodology frame (requirements
  traceability, interface management, V-model, system-of-systems architecture,
  verification gap, etc.).
- Option 2 must use a broader systems thinking frame (feedback loops, unintended
  consequences, emergence, complexity).
- 150–250 words each.
- Include source link naturally or as "Source:" at the end.
- 2–3 hashtags; at least one of #SystemsEngineering or #SystemsThinking.

OUTPUT FORMAT:
### World Event Option 1 — [SE methodology frame]
[post text]

### World Event Option 2 — [systems thinking frame]
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


def run_world_events_search(client: Anthropic, today: str, cutoff_14d: str) -> str:
    """Step 3: web search for defence/energy/geopolitical events with SE lens."""
    user_prompt = WORLD_EVENTS_USER_PROMPT_TEMPLATE.format(
        today=today, cutoff_14d=cutoff_14d
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        system=WORLD_EVENTS_SEARCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = [block.text for block in msg.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip()


def run_world_events_draft(client: Anthropic, world_evaluation: str) -> str:
    """Step 4: draft two world-events posts from the selected event."""
    user_prompt = (
        "Here is the selected world event and systems thinking angle:\n\n"
        + world_evaluation
        + "\n\nNow draft the two LinkedIn post options as instructed."
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=WORLD_EVENTS_DRAFT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = [block.text for block in msg.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_post_file(
    date: dt.date,
    evaluation: str,
    drafts: str,
    world_evaluation: str = "",
    world_drafts: str = "",
) -> Path:
    path = POSTS_DIR / f"{date.isoformat()}.md"

    mbse_section = (
        f"# LinkedIn Drafts — {date.isoformat()}\n\n"
        f"## Track 1: MBSE / SysML / Systems Engineering\n\n"
        f"### Research & Scoring\n\n{evaluation}\n\n"
        f"---\n\n"
        f"### Drafts\n\n{drafts}\n"
    )

    world_section = ""
    if world_evaluation:
        world_section = (
            f"\n---\n\n"
            f"## Track 2: World Events — Defence / Energy / Geopolitics (SE Lens)\n\n"
            f"### Research & Scoring\n\n{world_evaluation}\n"
        )
        if world_drafts:
            world_section += f"\n---\n\n### Drafts\n\n{world_drafts}\n"

    path.write_text(mbse_section + world_section, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the search prompts without calling Claude.")
    p.add_argument("--mbse-only", action="store_true",
                   help="Skip the world events track (saves ~2 API calls).")
    args = p.parse_args(argv)

    today = dt.date.today()
    cutoff = (today - dt.timedelta(days=10)).isoformat()
    cutoff_14d = (today - dt.timedelta(days=14)).isoformat()

    if args.dry_run:
        print("=== STEP 1: MBSE Search & Evaluate ===\n")
        print(SEARCH_USER_PROMPT_TEMPLATE.format(today=today.isoformat(), cutoff=cutoff))
        print("\n=== STEP 2: MBSE Draft ===\n")
        print("(drafts from shortlist — no web search in this step)")
        if not args.mbse_only:
            print("\n=== STEP 3: World Events Search & Evaluate ===\n")
            print(WORLD_EVENTS_USER_PROMPT_TEMPLATE.format(
                today=today.isoformat(), cutoff_14d=cutoff_14d
            ))
            print("\n=== STEP 4: World Events Draft ===\n")
            print("(drafts from selected event — no web search in this step)")
        return 0

    client = Anthropic()

    # --- MBSE Track ---
    print("Step 1: Searching and evaluating MBSE/SysML candidates...")
    evaluation = run_search_and_evaluate(client, today.isoformat(), cutoff)
    print(evaluation)

    drafts = ""
    if "cannot find" in evaluation.lower() or "no strong candidates" in evaluation.lower():
        print("\nNot enough MBSE candidates found today. Continuing to world events track.")
    else:
        print("\nStep 2: Drafting MBSE posts...")
        drafts = run_draft(client, evaluation)

    # --- World Events Track ---
    world_evaluation = ""
    world_drafts = ""

    if not args.mbse_only:
        print("\nStep 3: Searching for world events with SE lens...")
        world_evaluation = run_world_events_search(client, today.isoformat(), cutoff_14d)
        print(world_evaluation)

        no_world_event = (
            "no item" in world_evaluation.lower()
            or "no strong candidates" in world_evaluation.lower()
            or "did not meet" in world_evaluation.lower()
            or "no event" in world_evaluation.lower()
        )
        if not no_world_event:
            print("\nStep 4: Drafting world events posts...")
            world_drafts = run_world_events_draft(client, world_evaluation)
        else:
            print("\nNo qualifying world event found today. Skipping world events drafts.")

    path = write_post_file(today, evaluation, drafts, world_evaluation, world_drafts)
    print(f"\nWrote {path}\n")
    if drafts:
        print("--- MBSE DRAFTS ---\n", drafts)
    if world_drafts:
        print("--- WORLD EVENTS DRAFTS ---\n", world_drafts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
