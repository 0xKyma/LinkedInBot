# LinkedIn Drafting Agent

A Python agent that uses Claude with web search to find recent content in MBSE,
SysML, systems engineering, defence, and energy, then drafts LinkedIn posts in
your voice each day.

Two output files are written to `posts/` each run:

- `YYYY-MM-DD.md` — the draft posts, ready to review and pick from
- `YYYY-MM-DD-research.md` — scoring tables, candidates considered, and filtered items

## How it works

The agent runs two independent tracks per day:

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
- Looks for a systems thinking or SE angle on the event (feedback loops, unintended
  consequences, interface failures, requirements volatility, verification gaps, etc.)
- Selects the single best event (min 15/25) and drafts 2 posts: one using an SE
  methodology frame, one using a broader systems thinking frame
- Uses a 14-day lookback window

On a good day you get up to 11 draft posts total. On a quiet day one or both
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
python prompts.py --dry-run
```

Prints all search prompts for both tracks so you can see exactly what will be sent.

### Real run

```bash
python prompts.py
```

Output appears in `posts/YYYY-MM-DD.md` and `posts/YYYY-MM-DD-research.md`.

### MBSE track only (saves ~2 API calls)

```bash
python prompts.py --mbse-only
```

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
├── .github/workflows/daily.yml   # GitHub Actions schedule
├── posts/                        # daily output lands here
│   ├── YYYY-MM-DD.md             # draft posts
│   └── YYYY-MM-DD-research.md    # research and scoring notes
├── prompts.py                    # agent, prompts, and all logic
├── sources.yaml                  # legacy feed list (not used by current agent)
├── daily.yml                     # legacy feed config (not used by current agent)
├── requirements.txt
├── .gitignore
└── README.md
```

## Customisation

### Voice and style

Edit the `VOICE_EXAMPLES` constant in `prompts.py`. Key rules currently in place:

- Posts are 100-175 words
- Structure: hook, context, opinion, ending (question or statement)
- No em dashes
- No "it's not X, it's Y" or similar rhetorical contrasts
- Plain connectors preferred (and, but, so, because)
- Write like an early-careers professional: direct, plain, no flourishes
- AU/UK English (programme, organisation, modelling)
- No corporate clichés, no more than 3 hashtags

After a few weeks of real runs you will see what Claude gets right and wrong.
Update the prompt accordingly. Treat it as a living document.

### Search topics

Edit `SEARCH_USER_PROMPT_TEMPLATE` and `WORLD_EVENTS_USER_PROMPT_TEMPLATE` in
`prompts.py` to change what is searched or add new query strings.

### Scoring and selection

Edit `SEARCH_SYSTEM_PROMPT` and `WORLD_EVENTS_SEARCH_SYSTEM_PROMPT` to adjust
the scoring rubric, minimum score thresholds, or inclusion/exclusion rules.

### Run frequency

Change the cron line in `.github/workflows/daily.yml`. Format is
`minute hour day month day-of-week` in UTC. Examples:

- `0 21 * * *` — every day at 21:00 UTC (07:30 Adelaide ACST)
- `0 21 * * 1-5` — weekdays only

### Model

Change `MODEL` in `prompts.py`. Currently `claude-sonnet-4-6`.

## Cost

Roughly AU$9-10 per month at one full run per day (both tracks), based on
Sonnet pricing and approximately 4 API calls per run.

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
intentionally high. Lower the minimum score threshold in
`WORLD_EVENTS_SEARCH_SYSTEM_PROMPT` if you want more candidates surfaced.

**Posts sound too AI-generated**
Add more of your own writing as examples to `VOICE_EXAMPLES`, or tighten the
hard rules. The most effective lever is showing it what you actually wrote,
not telling it what tone to hit.
