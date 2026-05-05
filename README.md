# LinkedIn Drafting Agent

A multi-agent Python system that uses Claude with web search to find recent
content in MBSE, SysML, systems engineering, defence, and energy, then drafts
LinkedIn posts in your voice each day. Sources from the last 2 runs are
automatically excluded so the same article is never drafted twice.

Three output files are written each run, each to its own folder:

- `posts/YYYY-MM-DD-post.md` — the draft posts, ready to review and pick from
- `research/YYYY-MM-DD-research.md` — scoring tables and candidates considered
- `critique/YYYY-MM-DD-critique.md` — final drafts alongside the quality review notes

## Agent architecture

Six specialist agents run each day, orchestrated by `main.py`:

```
┌─────────────────────┐     ┌──────────────────────────┐
│  MBSEResearchAgent  │     │ WorldEventsResearchAgent  │
│                     │     │                           │
│  10 web searches    │     │  6 web searches           │
│  Score & shortlist  │     │  Score & select 1 event   │
│  (MBSE/SysML/SE)    │     │  (defence/energy/geo)     │
└────────┬────────────┘     └────────────┬──────────────┘
         │   run in parallel             │
         ▼                               ▼
┌─────────────────────┐     ┌──────────────────────────┐
│  MBSEDraftingAgent  │     │ WorldEventsDraftingAgent  │
│                     │     │                           │
│  3 angles per item  │     │  2 angles per event       │
│  (practitioner,     │     │  (SE methodology frame,   │
│  industry/trend,    │     │  systems thinking frame)  │
│  contrarian)        │     │                           │
└────────┬────────────┘     └────────────┬──────────────┘
         │   run in parallel             │
         └──────────────┬────────────────┘
                        ▼
             ┌─────────────────────┐
             │    QualityAgent     │
             │                     │
             │  Reviews all posts  │
             │  against voice      │
             │  checklist          │
             └──────────┬──────────┘
                        │
            ┌───────────┴────────────┐
            │ PASS                   │ FAIL (with specific notes)
            ▼                        ▼
       keep draft            MBSEDraftingAgent /
                             WorldEventsDraftingAgent
                             (revision mode, max 2 rounds)
                                      │
                                      ▼
                               write_output()
                          posts/YYYY-MM-DD.md
                          posts/YYYY-MM-DD-research.md
```

| Agent | File | Role |
|---|---|---|
| `MBSEResearchAgent` | `agents/research.py` | Web search + scoring for MBSE/SysML content |
| `WorldEventsResearchAgent` | `agents/research.py` | Web search + scoring for defence/energy/geopolitics |
| `MBSEDraftingAgent` | `agents/drafting.py` | Drafts 3 post angles per MBSE item |
| `WorldEventsDraftingAgent` | `agents/drafting.py` | Drafts 2 post angles for world event |
| `QualityAgent` | `agents/quality.py` | Reviews all drafts against the voice checklist |
| Revision loop | `main.py` | Sends failed posts back to drafting agents with notes |

The two research agents run in parallel. The two drafting agents run in parallel
after research completes. Total wall-clock time is roughly half that of sequential
execution.

## How it works

**Source deduplication**

Before any searches run, `output.py` scans the two most recent
`research/YYYY-MM-DD-research.md` files and extracts every URL they mention.
Both research agents receive that list and are instructed not to select any
of those sources. This prevents the same article from appearing across
consecutive daily runs.

**Track 1: MBSE / SysML / Systems Engineering**
- Runs 10 web searches across SysML v2, MBSE methodology, digital engineering,
  arXiv preprints, IEEE papers, INCOSE proceedings, and NASA/MITRE/RAND reports
- Scores each candidate on relevance, novelty, practicality, timeliness, and
  debate potential (max 25 points)
- Selects the top 2-3 items and drafts 3 posts per item (practitioner angle,
  industry/trend angle, contrarian angle)
- Publications (arXiv, IEEE, INCOSE, RAND) are accepted up to 90 days old if
  the content is genuinely novel for the audience

**Track 2: World Events (Defence / Energy / Geopolitics)**
- Runs 6 web searches across defence procurement, energy policy, and geopolitical events
- Looks for a systems thinking or SE angle (feedback loops, unintended consequences,
  interface failures, requirements volatility, verification gaps, etc.)
- Selects the single best event (min 15/25) and drafts 2 posts: one using an SE
  methodology frame, one using a broader systems thinking frame
- Uses a 14-day lookback window

On a good day you get up to 17 draft posts. On a quiet day one or both
tracks may find nothing and say so.

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
```

Prints all search prompts for both tracks so you can see exactly what will be sent.

### Real run

```bash
python main.py
```

Output appears in `posts/YYYY-MM-DD.md` and `posts/YYYY-MM-DD-research.md`.

### MBSE track only (saves ~2 API calls)

```bash
python main.py --mbse-only
```

### Add a specific article or topic

Pass `--topic` with a URL or free-text description. The agent searches for
context, then drafts posts alongside the regular tracks. Repeat the flag for
multiple topics.

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
drafts in `posts/YYYY-MM-DD.md`, pick one, refine, post.

## Repository layout

```
LinkedInBot/
├── agents/
│   ├── base.py               # BaseAgent wrapping AsyncAnthropic
│   ├── research.py           # MBSEResearchAgent, WorldEventsResearchAgent
│   ├── drafting.py           # MBSEDraftingAgent, WorldEventsDraftingAgent
│   └── quality.py            # QualityAgent
├── prompts/
│   ├── shared.py             # AUDIENCE, VOICE_EXAMPLES
│   ├── research.py           # search system prompts + user prompt templates
│   ├── drafting.py           # draft system prompts + revision prompt
│   └── quality.py            # quality checklist system prompt
├── main.py                   # async orchestrator entry point
├── output.py                 # writes output files
├── prompts.py                # legacy entry point (preserved for compatibility)
├── posts/                    # draft posts
│   └── YYYY-MM-DD-post.md
├── research/                 # candidate scoring and evaluation
│   └── YYYY-MM-DD-research.md
├── critique/                 # final drafts + quality review notes
│   └── YYYY-MM-DD-critique.md
├── requirements.txt
├── .gitignore
└── README.md
```

## Customisation

### Voice and style

Edit `prompts/shared.py`. Key rules currently in place:

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
gets wrong. Tighten the rules in `prompts/shared.py` and `prompts/quality.py`.

The highest-leverage improvement is adding real post examples to `VOICE_EXAMPLES`
in `prompts/shared.py`. The model learns cadence and vocabulary from concrete
instances far better than from descriptions alone.

### Source deduplication window

By default, sources from the last 2 runs are excluded. To change the window,
edit the `get_used_sources(n=2)` call in `main.py`:

```python
skip_urls = get_used_sources(n=3)   # look back 3 runs
skip_urls = get_used_sources(n=1)   # only exclude yesterday's sources
skip_urls = get_used_sources(n=0)   # disable deduplication
```

### Search topics

Edit `prompts/research.py` — `SEARCH_USER_PROMPT_TEMPLATE` for MBSE queries,
`WORLD_EVENTS_USER_PROMPT_TEMPLATE` for world events queries.

### Scoring and selection

Edit the system prompts in `prompts/research.py` to adjust scoring rubrics,
minimum score thresholds, or inclusion/exclusion rules.

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

### Model

Change `MODEL` in `agents/base.py`. Currently `claude-sonnet-4-6`.

## Cost

Roughly AU$9-10 per month at one full run per day (both tracks), based on
Sonnet pricing and approximately 6 API calls per run (4 core + up to 2 revision
rounds if quality check fails).

Use `--mbse-only` to run only Track 1 and keep costs closer to AU$4-5/month.

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
Add more of your own writing as examples to `VOICE_EXAMPLES` in `prompts/shared.py`,
or add specific failing patterns to the checklist in `prompts/quality.py`. The
most effective lever is showing it what you actually wrote, not telling it what
tone to hit.

**Both tracks find nothing after adding deduplication**
The exclusion list may be filtering out too many candidates if there has been
a quiet news period. Try reducing the window: `get_used_sources(n=1)` in
`main.py`, or run with `--dry-run` to see the full exclusion list being sent
to the agents.

**Quality check keeps failing after 2 revision rounds**
The offending rule is likely in `prompts/quality.py`. Check `critique/YYYY-MM-DD-critique.md`
for the `## Quality Review` section to see exactly
what was flagged, then either tighten the drafting prompt or relax the rule.
