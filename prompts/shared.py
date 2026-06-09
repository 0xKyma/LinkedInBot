"""
Shared prompt fragments.

The canonical text for the audience and voice rules now lives in versioned
Agent Skills under ``skills/`` (``linkedin-audience`` and ``linkedin-voice``).
These module-level constants load that text so every prompt module that already
imports ``AUDIENCE`` / ``VOICE_EXAMPLES`` keeps working unchanged, while the
single source of truth is the SKILL.md files.
"""

from skill_loader import load_skill

AUDIENCE = load_skill("linkedin-audience").body
VOICE_EXAMPLES = load_skill("linkedin-voice").body
