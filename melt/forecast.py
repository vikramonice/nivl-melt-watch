"""
forecast.py
===========
AMPS 5-day forecast for the route, taken from the MINIS weather site (no second AMPS download):
https://vikramonice.github.io/minis-weather/viewer_manifest.json holds each run's CSV per site.
Sites used: C13 (grounding zone, 0.7 km from the route waypoint C13, in zone A), A12 (Potsdam shear
margin, near zone B), Maitri. Per forecast day (UTC): max 2 m temperature, positive degree days on the
daily mean, snowfall (mm water), max 10 m wind.

    python -m melt.forecast SITE_DIR
"""
import argparse
import csv
import datetime as dt
import io

import requests

from melt.common import UA, load_state, save_state

MANIFEST = "https://vikramonice.github.io/minis-weather/viewer_manifest.json"
SITES = {"grounding_zone_gz_a": "C13, grounding zone (zone A)", "potsdam_shear_margin_sm_a": "A12, Potsdam shear margin (near zone B)",
         "maitri": "Maitri"}


def update(site):
    st = load_state(site)
    try:
        runs = requests.get(MANIFEST, timeout=60, headers=UA).json()
    except Exception as e:
        st.setdefault("forecast", {})["error"] = "MINIS weather manifest unavailable: %s" % str(e)[:100]
        save_state(site, st); return st
    run = max(runs, key=lambda r: r["cycle"])
    out = dict(cycle=run["cycle"], sites={})
    for s in run["sites"]:
        if s["slug"] not in SITES or not s.get("csv"):
            continue
        days = {}
        for r in csv.DictReader(io.StringIO(s["csv"])):
            t = dt.datetime.strptime(r["time"], "%Y-%m-%d %H:%M")
            d = (t - dt.timedelta(minutes=1)).date().isoformat()            # 3-h value ending at 00 UTC belongs to the day before
            x = days.setdefault(d, dict(t=[], snow=0.0, wind=[]))
            x["t"].append(float(r["t2"])); x["snow"] += float(r.get("apcp") or 0); x["wind"].append(float(r["wspd"]))
        out["sites"][s["slug"]] = dict(name=SITES[s["slug"]], days=[
            dict(date=d, tmax=round(max(v["t"]), 1), pdd=round(max(sum(v["t"]) / len(v["t"]), 0), 1), snow_mm=round(v["snow"], 1),
                 wind_max=round(max(v["wind"]), 1), n=len(v["t"])) for d, v in sorted(days.items()) if len(v["t"]) >= 4])
    out["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    st["forecast"] = out
    save_state(site, st)
    print("forecast run", out["cycle"], {k: v["days"][:2] for k, v in out["sites"].items()})
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    update(ap.parse_args().site)
