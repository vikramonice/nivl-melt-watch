"""
publish.py
==========
One update of the Nivl Melt Watch site (GitHub Pages, branch gh-pages). The site folder is a checkout
of gh-pages and holds the page, the images and season.json (everything gathered this season).

    python publish.py SITE_DIR            station reports only (every 6 h)
    python publish.py SITE_DIR --full     all sources (daily)
    python publish.py SITE_DIR --rebuild  page only, from the stored data (after a template change)

Each source runs on its own: a failure is recorded and shown on the page, the others still update.
The workflow publishes only when season.json or the page inputs changed (AMPS_CHANGED_FLAG file).
"""
import hashlib
import os
import shutil
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from melt import build  # noqa: E402
from melt.common import SEASON_END, today  # noqa: E402


def digest(site):
    f = Path(site) / "season.json"
    return hashlib.md5(f.read_bytes()).hexdigest() if f.exists() else ""


def main():
    site = Path(sys.argv[1]).resolve()
    site.mkdir(parents=True, exist_ok=True)
    if today() >= SEASON_END:
        print("season over (%s): no update" % SEASON_END); return
    full, rebuild = "--full" in sys.argv, "--rebuild" in sys.argv
    before = digest(site)
    if not rebuild:
        from melt import amsr, forecast, nisar, optical, s1, seaice, stations
        steps = [("stations", stations.update)]
        if full:
            steps += [("forecast", forecast.update), ("amsr", amsr.update), ("s1", s1.update), ("optical", optical.update),
                      ("seaice", seaice.update), ("nisar", nisar.update)]
        for name, fn in steps:
            try:
                fn(site)
            except Exception:
                print("%s failed:\n%s" % (name, traceback.format_exc()[-1500:]))
    shutil.copy2(HERE / "static" / "map.jpg", site / "map.jpg")
    build.build(site)
    (site / ".nojekyll").write_text("")
    if rebuild or digest(site) != before:
        flag = os.environ.get("AMPS_CHANGED_FLAG")
        if flag:
            Path(flag).write_text("changed")
        print("changes to publish")
    else:
        print("no new data")


if __name__ == "__main__":
    main()
