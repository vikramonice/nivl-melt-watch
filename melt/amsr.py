"""
amsr.py
=======
AMSR2 wet snow per zone, this season (Picard & Fily near-real-time product, Grenoble:
https://snow.univ-grenoble-alpes.fr/melting/nrt-antarctic/; 10 km, daily; the producers call the recent
days experimental). A cell is wet on a day if the ascending or the descending pass is wet. The zone
cells are fixed in static/amsr_cells.json (cells whose centre is within 5 km of a route zone, or inside
a larger zone), made by code/python/melt/meltwatch_climatology.py in the Nivl project.

The whole-continent NetCDF (about 106 MB, updated daily) is downloaded and only the zone cells are read.

    python -m melt.amsr SITE_DIR
"""
import argparse
import datetime as dt

import numpy as np
import requests

from melt.common import SEASON_START, UA, WORK, clean, load_state, save_state, static

URL = "https://snow.univ-grenoble-alpes.fr/opendata/melt-AMSRJ-antarctic-10km.nc"


def update(site):
    import netCDF4
    st = load_state(site)
    WORK.mkdir(parents=True, exist_ok=True)
    f = WORK / "amsr.nc"
    try:
        with requests.get(URL, stream=True, timeout=300, headers=UA) as r:
            r.raise_for_status()
            with open(f, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
    except Exception as e:
        st["amsr_error"] = "download failed: %s" % str(e)[:160]
        save_state(site, st)
        print(st["amsr_error"]); return st
    cells = static("amsr_cells.json")
    with netCDF4.Dataset(f) as d:
        tv = d.variables["time"]
        times = netCDF4.num2date(tv[:], tv.units, only_use_cftime_datetimes=False)
        days = np.array([dt.date(t.year, t.month, t.day) for t in times])
        k = np.flatnonzero(days >= SEASON_START)
        out = {}
        if k.size:
            iy_all = sorted({i for c in cells.values() for i in c["iy"]})
            ix_all = sorted({j for c in cells.values() for j in c["ix"]})
            ys, xs = slice(min(iy_all), max(iy_all) + 1), slice(min(ix_all), max(ix_all) + 1)
            a = d.variables["snow_status_wet_dry_19H_ASC_filter"][k[0]:k[-1] + 1, ys, xs]
            b = d.variables["snow_status_wet_dry_19H_DSC_filter"][k[0]:k[-1] + 1, ys, xs]
            a = np.ma.filled(a.astype("float32"), np.nan); b = np.ma.filled(b.astype("float32"), np.nan)
            a[a < 0] = np.nan; b[b < 0] = np.nan
            wet = np.fmax(a, b)
            for z, c in cells.items():
                iy = np.array(c["iy"]) - ys.start; ix = np.array(c["ix"]) - xs.start
                w = wet[:, iy, ix]
                rows = {}
                for n, kk in enumerate(range(k[0], k[-1] + 1)):
                    v = w[n]
                    if np.isfinite(v).sum() == 0:
                        continue
                    rows[days[kk].isoformat()] = dict(frac=float(np.nanmean(v)), n_wet=int(np.nansum(v > 0)), n=int(np.isfinite(v).sum()))
                first = next((d_ for d_ in sorted(rows) if rows[d_]["n_wet"] > 0), None)
                out[z] = dict(days=rows, first_wet=first, wet_days=sum(r["n_wet"] > 0 for r in rows.values()),
                              latest=max(rows) if rows else None)
        st["amsr"] = out
        st["amsr_latest"] = max((v["latest"] for v in out.values() if v["latest"]), default=None)
        st["amsr_error"] = None
    st["amsr_updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save_state(site, st)
    print("AMSR latest day:", st["amsr_latest"], {z: (v["first_wet"], v["wet_days"]) for z, v in out.items()})
    f.unlink(missing_ok=True)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    update(ap.parse_args().site)
