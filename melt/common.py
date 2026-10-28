"""Shared paths, season dates and state for the Nivl Melt Watch scripts."""
import datetime as dt
import json
import math
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "static"
WORK = Path(os.environ.get("MELTWATCH_WORK") or (REPO / "_work"))      # scratch (not published)
SEASON_START = dt.date(2026, 10, 1)                 # day 0 of the season (as the climatology)
PDD_START = dt.date(2026, 11, 1)                    # running counts start 1 November
SEASON_END = dt.date(2027, 3, 1)                    # updates stop after February 2027
ZONES_V = 2                                         # bump when zones change: satellite scenes are re-measured once
UA = {"User-Agent": "nivl-melt-watch (research field monitoring; github.com/vikramonice/nivl-melt-watch)"}


def today():
    return dt.datetime.now(dt.timezone.utc).date()


def offset(d):
    """Days since SEASON_START (index into the climatology arrays)."""
    return (d - SEASON_START).days


def clean(o):
    """numpy -> plain Python; NaN -> None, so the JSON is valid for the page."""
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            o = float(o)
    except ImportError:
        pass
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 3)
    return o


def load_state(site):
    f = Path(site) / "season.json"
    return json.loads(f.read_text()) if f.exists() else {}


def save_state(site, state):
    (Path(site) / "season.json").write_text(json.dumps(clean(state), separators=(",", ":")))


def static(name):
    return json.loads((STATIC / name).read_text())
