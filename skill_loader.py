"""
Agent Skills loader.

Skills live under ``skills/<name>/SKILL.md`` in the documented Agent Skills
format: YAML frontmatter (``name`` + ``description``) followed by the skill
body. They are the single source of truth for reusable, model-facing context
(voice rules, audience, scoring rubrics) and are deliberately portable — the
same folders can be consumed by Claude Code, claude.ai, or a Managed Agent.

This module lets the daily pipeline compose those same skills into the system
prompts it sends through the Claude API. Frontmatter is parsed without a YAML
dependency: the format is simple ``key: value`` lines between ``---`` fences.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str


def _split_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Split a SKILL.md into (frontmatter dict, body).

    Frontmatter is the block between a leading ``---`` line and the next
    ``---`` line. Returns an empty dict and the full text if absent.
    """
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw.strip("\n")

    meta: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        key, sep, value = lines[i].partition(":")
        if sep:
            meta[key.strip()] = value.strip()
        i += 1
    body = "\n".join(lines[i + 1:]).strip("\n")
    return meta, body


@lru_cache(maxsize=None)
def load_skill(name: str) -> Skill:
    """Load and cache a skill by folder name (e.g. ``"linkedin-voice"``)."""
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Skill '{name}' not found at {path}. "
            f"Available: {', '.join(s.name for s in list_skills()) or 'none'}"
        )
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return Skill(
        name=meta.get("name", name),
        description=meta.get("description", ""),
        body=body,
    )


def list_skills() -> list[Skill]:
    """Return every available skill, sorted by name. Useful for discovery."""
    if not SKILLS_DIR.exists():
        return []
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta, body = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
        skills.append(
            Skill(
                name=meta.get("name", skill_md.parent.name),
                description=meta.get("description", ""),
                body=body,
            )
        )
    return skills


def compose_system(intro: str, skills: list[str], outro: str = "") -> str:
    """Assemble a system prompt from an intro, a list of skill bodies, and an outro.

    Each section is separated by a blank line. This is how an agent declares the
    reusable skills it depends on while keeping its orchestration-specific
    instructions (intro/outro) local.
    """
    parts: list[str] = [intro.strip()]
    parts.extend(load_skill(name).body for name in skills)
    if outro.strip():
        parts.append(outro.strip())
    return "\n\n".join(p for p in parts if p)
