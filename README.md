# LinkedIn Drafting Agent

A small Python agent that pulls the latest items from a curated set of MBSE,
SysML, systems engineering, and defence industry RSS feeds, then asks Claude
to draft three LinkedIn post options in your voice each day.

Output goes to `posts/YYYY-MM-DD.md`, one file per day, including:

- the titles and links of the source items considered
- three draft posts, each tagged with its archetype (technical insight,
  industry commentary, contrarian take, lesson learned, or question)
- the rationale for each angle

You review on your phone, pick one, refine, post.

## Quick start (Windows)

### Prerequisites

- Python 3.11 or newer (`python --version` to check)
- A GitHub account
- An Anthropic API key (https://console.anthropic.com/)
- Git installed (https://git-scm.com/download/win)

### One-time setup

1. Create a new private repo on GitHub, e.g. `linkedin-agent`.
2. Clone it locally:
   ```powershell
   git clone https://github.com/<your-username>/linkedin-agent.git
   cd linkedin-agent
   ```
3. Drop the contents of this folder into the repo.
4. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
5. Set your API key for local testing (PowerShell):
   ```powershell
   $env:ANTHROPIC_API_KEY = "sk-ant-..."
   ```
   To set it permanently for your user account:
   ```powershell
   [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
   ```

### Test the feed harvest (no API call, no cost)

```powershell
python scripts/linkedin_agent.py --dry-run
```

This pulls the feeds, dedupes, and prints what would be sent to Claude. Use it
to validate your sources without burning tokens.

### Run a real draft

```powershell
python scripts/linkedin_agent.py
```

Output appears in `posts/YYYY-MM-DD.md`.

## Run it daily and commit to GitHub

The included GitHub Actions workflow (`.github/workflows/daily.yml`) runs the
agent every day at 07:30 Adelaide time and commits the output file back to the
repo. To enable it:

1. Push the repo to GitHub.
2. In the repo, go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Name: `ANTHROPIC_API_KEY`. Value: your key.
4. Go to the **Actions** tab and enable workflows if prompted.

You can manually trigger a run any time via **Actions → Daily LinkedIn Drafts
→ Run workflow**. Useful for testing or for catching up after a quiet day.

The committed post file is your daily inbox: open the repo on your phone or
laptop, read the drafts, copy the one you want.

## Repository layout

```
linkedin-agent/
├── .github/workflows/daily.yml   # GitHub Actions schedule
├── scripts/
│   ├── linkedin_agent.py         # main agent
│   ├── prompts.py                # system prompt + voice samples
│   └── .seen_items.json          # dedupe cache (auto-managed)
├── posts/                        # daily drafts land here
│   └── YYYY-MM-DD.md
├── sources.yaml                  # RSS feed list
├── requirements.txt
├── .gitignore
└── README.md
```

## Customisation

### Voice and archetypes
Edit `scripts/prompts.py`. The `SYSTEM_PROMPT` constant contains:
- positioning statement
- voice samples (currently anchored in your INCOSE 2025 and SETE 2024 papers)
- post archetypes and selection logic
- hard rules (no em-dashes, no emojis, AU/UK English, length, etc.)

After a few weeks of real drafts you will notice patterns in what Claude gets
right and wrong. Update the prompt accordingly. Treat it as a living document.

### Sources
Edit `sources.yaml`. To add a feed:

```yaml
- name: "Some Blog"
  url: "https://example.com/feed/"
```

If a feed breaks (returns no entries), you'll see a `[WARN]` line in the run
log. Either replace it with a working URL or remove it.

### Run frequency
Change the cron line in `.github/workflows/daily.yml`. The format is
`minute hour day month day-of-week` in UTC. Some examples:

- `0 21 * * *` — every day at 21:00 UTC (07:30 Adelaide ACST)
- `0 21 * * 1-5` — weekdays only
- `0 21 * * 1,3,5` — Mon, Wed, Fri only

### Model
Change `MODEL` in `scripts/linkedin_agent.py`. Sonnet 4.5 is the default and
the best price/quality fit for drafting. Use Opus only if you find Sonnet
consistently weak on a particular type of source, or want occasional
high-stakes drafts.

## Cost

Roughly AU$4 to AU$5 per month at one run per day, based on Sonnet pricing and
a typical input of ~15-20k tokens (sources plus prompt) and ~2-3k tokens of
output (three drafts).

GitHub Actions is free for public repos and has a generous free tier for
private repos (2,000 minutes/month). A single agent run takes well under a
minute.

## Troubleshooting

**The Actions run failed with "ANTHROPIC_API_KEY is not set"**
You haven't added the secret in repo settings, or you spelled it wrong.

**The dry-run shows no items**
Either the feeds are quiet today, or the lookback window is too tight. Adjust
`LOOKBACK_DAYS` in `scripts/linkedin_agent.py`.

**A specific feed always shows 0 items**
The URL may have changed. Open it in a browser. If it doesn't return XML,
find the new feed URL on the source's website and update `sources.yaml`.

**Claude's output isn't quite my voice**
Add more voice samples to `prompts.py`, or sharpen the hard rules section.
The single most effective lever is showing it what you actually wrote, not
telling it what tone to hit.

## Future extensions

- Add a critic agent that tears apart weak drafts before you see them
  (multi-agent path, ~AU$15/month).
- Pipe selected posts back into a "what worked" log to refine the voice
  prompt over time.
- Add a Slack or email notification step in the Actions workflow so the
  drafts come to you instead of you going to them.