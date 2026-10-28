"""
seaice.py
=========
Sea-ice concentration off the Nivlisen ice front (University of Bremen AMSR2 ASI v5.4, 6.25 km, daily,
no login; Spreen et al. 2008). Context only: when the fast ice and pack ice open up in front of the
shelf. Three boxes seaward of the front (EPSG:3031, as nivl_open_water.py in the Nivl project); per day,
the mean concentration of ocean pixels and the share of pixels below 15 % (open water).

    python -m melt.seaice SITE_DIR
"""
import argparse
import datetime as dt

import numpy as np
import requests

from melt.common import SEASON_START, UA, WORK, load_state, save_state

URL = "https://data.seaice.uni-bremen.de/amsr2/asi_daygrid_swath/s6250/{y}/{m}/Antarctic/asi-AMSR2-s6250-{d}-v5.4.tif"
MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
BOXES = {"W": ("west front", (395e3, 430e3, 2150e3, 2185e3)),
         "C": ("central front", (430e3, 462e3, 2140e3, 2175e3)),
         "E": ("east front, Leningradkollen bay", (462e3, 482e3, 2133e3, 2160e3))}


def box_stats(path):
    import rasterio
    from pyproj import Transformer
    out = {}
    with rasterio.open(path) as s:
        t = Transformer.from_crs(3031, s.crs, always_xy=True)
        for k, (_, (x0, x1, y0, y1)) in BOXES.items():
            cx, cy = t.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
            w = rasterio.windows.from_bounds(min(cx), min(cy), max(cx), max(cy), s.transform).round_offsets().round_lengths()
            a = s.read(1, window=w).astype(float)
            a = a[a <= 100]                                   # 120 = land / ice shelf, >100 = no data
            if a.size:
                out[k] = dict(sic=round(float(a.mean()), 1), open_frac=round(float(np.mean(a < 15)), 2))
    return out


def update(site):
    st = load_state(site)
    S = st.setdefault("seaice", dict(days={}))
    WORK.mkdir(parents=True, exist_ok=True)
    d = max([SEASON_START] + [dt.date.fromisoformat(x) for x in S["days"]])
    end = dt.datetime.now(dt.timezone.utc).date()
    while d <= end:
        key = d.isoformat()
        if key not in S["days"] or d >= end - dt.timedelta(days=2):
            r = requests.get(URL.format(y=d.year, m=MON[d.month - 1], d=d.strftime("%Y%m%d")), timeout=60, headers=UA)
            if r.status_code == 200 and len(r.content) > 1000:
                f = WORK / "asi.tif"
                f.write_bytes(r.content)
                S["days"][key] = box_stats(f)
        d += dt.timedelta(days=1)
    S["latest"] = max(S["days"]) if S["days"] else None
    S["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save_state(site, st)
    print("sea ice latest", S["latest"], S["days"].get(S["latest"]))
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    update(ap.parse_args().site)
