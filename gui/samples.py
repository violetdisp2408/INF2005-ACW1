"""Finds the team's sample image and audio for the Protect page."""

import os

from . import media

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = {"team-image": "sample.png", "team-audio": "sample.wav"}


def path(mode: str) -> str | None:
    """Returns the path of a team sample, or None."""
    if mode == "team-image":
        p = os.path.join(ROOT, "sample.png")
        return p if os.path.exists(p) else None
    if mode == "team-audio":
        p = os.path.join(ROOT, "sample.wav")
        if os.path.exists(p):
            return p
        made = os.path.join(ROOT, "instance", "sample.wav")
        if not os.path.exists(made):
            try:
                from src.test_member1_2 import generate_sample_wav
            except ImportError:
                return None
            os.makedirs(os.path.dirname(made), exist_ok=True)
            generate_sample_wav(made)
        return made
    return None


def info() -> dict:
    """Returns sample details for the Protect page."""
    out = {}
    for mode in TEAM:
        p = path(mode)
        if not p:
            continue
        m = media.load(p)
        out[mode] = {"units": m.unit_count, "describe": m.describe(), "name": TEAM[mode],
                     "seconds": m.meta.get("seconds", 0)}
    return out
