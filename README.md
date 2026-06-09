# LinkedIn Drafting Agent

A multi-agent Python system that uses Claude with web search to find recent
content in MBSE, SysML, systems engineering, defence, and energy, then drafts
LinkedIn posts in your voice each day. Sources from previous runs are
automatically excluded so the same article is never drafted twice.

Two scripts run independently — `main.py` for the MBSE/SysML track, and
`world_events.py` for the defence/energy/geopolitics track. Run one or both.

Three output files are written each run, each to its own folder:

- `posts/YYYY-MM-DD-post.md` — the draft posts, ready to review and pick from
- `research/YYYY-MM-DD-research.md` — scoring tables and candidates considered
- `critique/YYYY-MM-DD-critique.md` — final drafts alongside the quality review notes

## Agent architecture

### MBSE track (`main.py`)

```
┌────────────────────┐
│  MBSEResearchAgent │
│                    │
│  10 web searches   │
│  Score & shortlist │
│  (MBSE/SysML/SE)   │
└────────┬───────────┘
         │
         ▼
┌────────────────────────────────────┐
│         MBSEDraftingAgent          │
│                                    │
│  4 angles per item:                │
│   Option 1 — Practitioner          │
│   Option 2 — Industry/trend        │
│   Option 3 — Contrarian            │
│   Option 4 — Balanced breakdown    │
└────────┬───────────────────────────┘
         │
         ▼
┌────────────────────┐
│    QualityAgent    │
│                    │
│  Reviews all posts │
│  against voice     │
│  checklist         │
└────────┬───────────┘
         │
┌────────┴────────────────┐
│ PASS                    │ FAIL (with specific notes)
▼                         ▼
keep draft         MBSEDraftingAgent
                   (revision mode, max 2 rounds)
                            │
                            ▼
                     write_post_file()
```

If `--topic` is passed, `CustomTopicAgent` runs after the MBSE drafting step
and its results are appended to the same output files.

### World events track (`world_events.py`)

```
┌──────────────────────────┐
│ WorldEventsResearchAgent │
│                          │
│  6 web searches          │
│  Score & select 1 event  │
│  (defence/energy/geo)    │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│ WorldEventsDraftingAgent │
│                          │
│  2 angles per event:     │
│   Option 1 — SE method   │
│   Option 2 — Systems     │
│              thinking    │
└────────┬─────────────────┘
         │
         ▼
┌────────────────────┐
│    QualityAgent    │
└────────┬───────────┘
         │
┌────────┴────────────────┐
│ PASS                    │ FAIL (with specific notes)
▼                         ▼
keep draft         WorldEventsDraftingAgent
                   (revision mode, max 2 rounds)
                            │
                            ▼
                     write_post_file()
```

### Agent summary

| Agent | File | Role |
|---|---|---|
| `MBSEResearchAgent` | `agents/research.py` | Web search + scoring for MBSE/SysML content |
| `WorldEventsResearchAgent` | `agents/research.py` | Web search + scoring for defence/energy/geopolitics |
| `MBSEDraftingAgent` | `agents/drafting.py` | Drafts 4 post angles per MBSE item |
| `WorldEventsDraftingAgent` | `agents/drafting.py` | Drafts 2 post angles for the selected world event |
| `QualityAgent` | `agents/quality.py` | Reviews all drafts against the voice checklist |
| `CustomTopicAgent` | `agents/custom.py` | Researches and drafts a user-supplied topic or URL |
| `ManualDraftAgent` | `agents/manual.py` | On-demand drafting in interactive mode (`draft.py`) |

All agents share a common `BaseAgent` harness (`agents/base.py`) that wraps
`AsyncAnthropic`, handles system prompt caching, logs token usage, and provides
the two call shapes (free-text and forced-tool/structured). Clients are built
through `create_client()`, which sets a shared retry policy so a transient
rate-limit or web-search blip during the daily run self-heals instead of
aborting the job. The two research agents run the web search tool; drafting and
quality agents do not (they work only from text already returned).

### Agent Skills

The reusable, model-facing context — the voice rules, the audience definition,
and the two scoring rubrics — lives in `skills/` as [Agent
Skills](https://platform.claude.com/docs/en/agents-and-tools/skills): folders
containing a `SKILL.md` with YAML frontmatter (`name`, `description`) and a body.

| Skill | Used by |
|---|---|
| `linkedin-voice` | drafting, quality, custom, manual prompts |
| `linkedin-audience` | research + drafting prompts |
| `mbse-scoring` | MBSE research prompt |
| `world-events-scoring` | world-events research prompt |

`skill_loader.py` parses and composes these into the system prompts the pipeline
sends. Because they are plain `SKILL.md` folders, the same skills are portable —
you can point Claude Code, claude.ai, or a Managed Agent at them and get the
identical voice and scoring behaviour without copying prompt text around.

## How it works

**Source deduplication**

Before any searches run, `output.py` loads `covered_sources.txt` — a
persistent list of every URL that has appeared in a drafted post. Both
research agents receive the list and skip any matching source. This prevents
the same article from being drafted across consecutive daily runs.

**Track 1: MBSE / SysML / Systems Engineering (`main.py`)**
- Runs 10 web searches across SysML v2, MBSE methodology, digital engineering,
  arXiv preprints, IEEE papers, INCOSE proceedings, and NASA/MITRE/RAND reports
- Scores each candidate on 5 anchored criteria (max 25 points): Relevance, Novelty,
  Practicality, Timeliness, and Debate Potential
- Scores the top 5 candidates before selecting, so the research file shows why
  borderline items were included or dropped
- Selects the top 2–3 items (minimum 15/25) and drafts **4 posts per item**:
  - **Option 1 — Practitioner:** what does this mean for someone doing MBSE today?
  - **Option 2 — Industry/trend:** adoption gap, displacement, money signal, or adjacent threat
  - **Option 3 — Contrarian:** a specific, arguable challenge to a mainstream assumption
  - **Option 4 — Balanced breakdown:** hook → what → so what → but → close
- Publications (arXiv, IEEE, INCOSE, RAND) are accepted up to 90 days old if
  the content is genuinely novel for the audience
- Up to 12 draft posts on a good day (3 items × 4 angles)

**Track 2: World Events / Defence / Energy / Geopolitics (`world_events.py`)**
- Runs 6 web searches across defence procurement, energy policy, and geopolitical events
- Looks for a systems thinking or SE angle (feedback loops, unintended consequences,
  interface failures, requirements volatility, verification gaps, etc.)
- Scores the top 4 candidates before selecting
- Selects the single best event (min 15/25) and drafts **2 posts**:
  - **Option 1 — SE methodology frame:** V-model, interface management, requirements
    traceability, verification gap, etc.
  - **Option 2 — Systems thinking frame:** feedback loops, emergence, unintended consequences
- Uses a 14-day lookback window

Run both tracks in a day and you get up to 14 draft posts. On a quiet day one
or both tracks may find nothing and say so.

## Quick start

### Prerequisites

- Python 3.11 or newer
- An Anthropic API key (https://console.anthropic.com/)

### Setup

```bash
git clone https://github.com/<your-username>/LinkedInBot.git
cd LinkedInBot
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Dry run (no API calls, no cost)

```bash
python main.py --dry-run
python world_events.py --dry-run
```

Prints all search prompts so you can see exactly what will be sent.

### Real run

```bash
# MBSE/SysML track
python main.py

# World events track (run separately, same output folders)
python world_events.py
```

Output appears in `posts/YYYY-MM-DD-post.md`, `research/YYYY-MM-DD-research.md`,
and `critique/YYYY-MM-DD-critique.md`.

### Draft a specific post on demand

Run the interactive drafter when you want to write about something specific,
without running the daily research tracks:

```bash
python draft.py
```

You will be prompted to choose a mode:

```
=== LinkedIn Post Drafter ===

How would you like to create your post?
  1. Article URL  — paste a link; the agent researches and drafts
  2. Your info    — paste dot points or guidance; draft directly from your input
  3. Topic search — describe a topic; the agent searches and drafts
```

Then choose an angle (Practitioner by default, or Contrarian / Industry/trend /
SE lens / Systems thinking).

One post is drafted per run. The final post is saved to `manual/YYYY-MM-DD-HHMM.md`.
No research or critique files are written — only the finished post.

The quality check and revision loop run the same as the daily pipeline.

**Mode 1 — Article URL:** paste a link to any article; the agent fetches and
summarises it, then drafts a post grounded in that content.

**Mode 2 — Your info:** paste dot points, a rough argument, or any guidance;
the agent drafts directly from your input without searching for anything else.
No external facts are introduced.

**Mode 3 — Topic search:** describe a topic in plain language; the agent
searches the web for relevant recent content and drafts from what it finds.

### Add a specific article or topic alongside the MBSE run

Pass `--topic` with a URL or free-text description. `CustomTopicAgent` runs
after the MBSE track and appends results to the same output files. Repeat the
flag for multiple topics.

```bash
python main.py --topic "https://example.com/some-article"
python main.py --topic "the new INCOSE paper on digital twins in defence"
python main.py --topic "https://..." --topic "another article or topic"
```

Control how many post angles are drafted per custom topic (default 3, max 5):

```bash
python main.py --topic "https://..." --topic-angles 2
```

Available angles, used in order: Practitioner, Industry/trend, Contrarian,
SE lens, Systems thinking.

## Run it daily via GitHub Actions

The included workflow (`.github/workflows/daily.yml`) runs the agent on a schedule
and commits the output files back to the repo.

To enable:

1. Push the repo to GitHub.
2. Go to **Settings > Secrets and variables > Actions > New repository secret**.
3. Name: `ANTHROPIC_API_KEY`. Value: your key.
4. Go to the **Actions** tab and enable workflows if prompted.

You can trigger a manual run any time via **Actions > Daily LinkedIn Drafts > Run workflow**.

The committed files are your daily inbox. Open the repo on your phone, read the
drafts in `posts/YYYY-MM-DD-post.md`, pick one, refine, post.

## Repository layout

```
LinkedInBot/
├── agents/
│   ├── base.py               # BaseAgent wrapping AsyncAnthropic
│   ├── research.py           # MBSEResearchAgent, WorldEventsResearchAgent
│   ├── drafting.py           # MBSEDraftingAgent, WorldEventsDraftingAgent
│   ├── quality.py            # QualityAgent
│   ├── custom.py             # CustomTopicAgent (used by --topic flag)
│   └── manual.py             # ManualDraftAgent (used by draft.py)
├── skills/                   # Agent Skills (SKILL.md folders) — single source of truth
│   ├── linkedin-voice/       # voice + format rules
│   ├── linkedin-audience/    # who the posts are for
│   ├── mbse-scoring/         # MBSE 25-point rubric
│   └── world-events-scoring/ # world-events 25-point rubric
├── skill_loader.py           # loads + composes SKILL.md files (no YAML dependency)
├── prompts/
│   ├── shared.py             # AUDIENCE, VOICE_EXAMPLES (loaded from skills)
│   ├── research.py           # search prompts (composed from skills) + user templates
│   ├── drafting.py           # draft system prompts + revision prompt
│   ├── quality.py            # quality checklist system prompt
│   ├── custom.py             # custom topic research + draft prompts
│   └── manual.py             # on-demand drafting prompts
├── main.py                   # MBSE/SysML track entry point
├── world_events.py           # world events track entry point (run separately)
├── draft.py                  # interactive on-demand drafter
├── output.py                 # writes output files, manages source deduplication
├── prompts.py                # legacy entry point (preserved for compatibility)
├── posts/                    # daily draft posts
│   └── YYYY-MM-DD-post.md
├── research/                 # candidate scoring and evaluation
│   └── YYYY-MM-DD-research.md
├── critique/                 # final drafts + quality review notes
│   └── YYYY-MM-DD-critique.md
├── manual/                   # on-demand posts from draft.py
│   └── YYYY-MM-DD-HHMM.md
├── covered_sources.txt       # persistent source deduplication list (auto-generated)
├── requirements.txt
├── .gitignore
└── README.md
```

## Customisation

### Voice and style

Edit `skills/linkedin-voice/SKILL.md` (the voice rules) and
`skills/linkedin-audience/SKILL.md` (the audience). `prompts/shared.py` loads
these, so a single edit propagates to every drafting, quality, and manual prompt.
Key rules currently in place:

- Posts are 100-175 words
- Structure: hook, context, opinion, ending (question or statement)
- Hook must make a specific, contestable claim — not a hollow tease or setup
- No em dashes
- No "it's not X, it's Y" or any structural variant (less about X more about Y,
  X is the wrong framing, forget X the real issue is Y, etc.)
- No passive voice
- Plain connectors preferred (and, but, so, because)
- Write like an early-careers professional: direct, plain, no flourishes
- AU/UK English (programme, organisation, modelling)
- No corporate clichés (including leverage, move the needle, on a journey, etc.)
- No more than 3 hashtags
- No forbidden openers (I, Just, There's a pattern, We need to talk about, etc.)

The `QualityAgent` enforces these rules automatically and triggers a rewrite
if a draft fails. After a few weeks of real runs you will see what it still
gets wrong. Tighten the rules in `skills/linkedin-voice/SKILL.md` and
`prompts/quality.py`.

The highest-leverage improvement is adding real post examples to
`skills/linkedin-voice/SKILL.md`. The model learns cadence and vocabulary from
concrete instances far better than from descriptions alone.

### Source deduplication window

By default, all previously covered sources are excluded. The list is stored in
`covered_sources.txt` and updated after each run. To change the lookback window,
edit the `get_used_sources(n=2)` call in `main.py` and `world_events.py`:

```python
skip_urls = get_used_sources(n=3)   # look back 3 runs
skip_urls = get_used_sources(n=1)   # only exclude yesterday's sources
skip_urls = get_used_sources(n=0)   # disable deduplication
```

### Search topics

Edit `prompts/research.py` — `SEARCH_USER_PROMPT_TEMPLATE` for MBSE queries,
`WORLD_EVENTS_USER_PROMPT_TEMPLATE` for world events queries.

### Scoring and selection

Edit the rubric skills — `skills/mbse-scoring/SKILL.md` and
`skills/world-events-scoring/SKILL.md` — to adjust scoring criteria,
topic priorities, or inclusion/exclusion rules. Each criterion has anchored
1 and 5 examples to keep scores consistent across runs; update these if the
domain focus shifts. The minimum qualifying score thresholds and the selection
/ output format live in the prompt outros in `prompts/research.py`. The minimum
qualifying score is 15/25 for both tracks.

### Run frequency

Change the cron line in `.github/workflows/daily.yml`. Format is
`minute hour day month day-of-week` in UTC. Examples:

- `0 21 * * *` — every day at 21:00 UTC (07:30 Adelaide ACST)
- `0 21 * * 1-5` — weekdays only

### Timezone

The bot determines today's date using your local timezone so the output file is
named correctly. Set the `TIMEZONE` environment variable to your [IANA timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones):

```bash
export TIMEZONE="Australia/Adelaide"   # default
export TIMEZONE="Australia/Sydney"
export TIMEZONE="Europe/London"
```

Without this, the server's UTC clock is used, which may name the file one day
behind if you run it after midnight local time.

### Model routing

Each step runs on the cheapest model that does it well, set by four constants
in `agents/base.py`:

| Step | Model | Why |
|---|---|---|
| Research + scoring | `claude-sonnet-4-6` | web search + 25-point rubric — balanced judgment, token-heavy |
| Drafting + revision | `claude-opus-4-8` | the actual posts — strongest writing voice, worth the premium |
| Quality review | `claude-haiku-4-5` | checklist/lexical enforcement, runs every revision round |
| Structured extraction | `claude-haiku-4-5` | pulling fields out of already-generated text — trivial |

Re-tune any of these in one line (`MODEL_RESEARCH`, `MODEL_DRAFTING`,
`MODEL_QUALITY`, `MODEL_EXTRACTION`); the harness wires each agent to its model.
The per-call usage log prints `model=...` so you can see which model ran each step.

## Cost

Roughly AU$9-12 per month at one full run per day (both tracks). Spend is
concentrated on the step that matters most: drafting runs on Opus 4.8 (pricier
per token, but small outputs), while quality review and extraction run on
Haiku 4.5 (much cheaper), and research stays on Sonnet 4.6. Net cost is broadly
similar to the previous all-Sonnet setup, with quality shifted toward the posts.

Run only `main.py` (MBSE track) to keep costs closer to AU$5-6/month.

GitHub Actions is free for public repos and has a generous free tier for
private repos (2,000 minutes/month). A single run takes 1-3 minutes.

## Troubleshooting

**Actions run failed with "ANTHROPIC_API_KEY is not set"**
You have not added the secret in repo settings, or the spelling is wrong.

**Track 1 finds nothing today**
The searches are scoped to the last 10 days. Publication queries go up to 90 days
but still require novelty. Try `--dry-run` to confirm the queries look correct.

**Track 2 always finds nothing**
Defence and energy events need a genuine SE angle to qualify. The bar is
intentionally high. Lower the minimum score threshold in the world events
system prompt in `prompts/research.py` if you want more candidates surfaced.

**Posts sound too AI-generated**
Add more of your own writing as examples to `skills/linkedin-voice/SKILL.md`,
or add specific failing patterns to the checklist in `prompts/quality.py`. The
most effective lever is showing it what you actually wrote, not telling it what
tone to hit.

**Both tracks find nothing after adding deduplication**
The exclusion list may be filtering out too many candidates if there has been
a quiet news period. Try reducing the window: `get_used_sources(n=1)` in
`main.py` and `world_events.py`, or run with `--dry-run` to see the full
exclusion list being sent to the agents.

**Quality check keeps failing after 2 revision rounds**
The offending rule is likely in `prompts/quality.py`. Check `critique/YYYY-MM-DD-critique.md`
for the `## Quality Review` section to see exactly what was flagged, then either
tighten the drafting prompt or relax the rule.
