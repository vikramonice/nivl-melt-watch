"""
s1.py
=====
Sentinel-1 radar (C-band, HH, RTC gamma0 from the Microsoft Planetary Computer, anonymous). Wet snow
absorbs the radar signal, so a wet surface is darker than the same place when dry; 3 dB or more darker
is the usual wet-snow mark (Nagler & Rott), and January melt on Nivlisen darkens the shelf by 5-10 dB.

Each scene is read over the route area on a 100 m EPSG:3031 grid (averaged from 10 m), and compared with
a baseline from the same relative orbit (the per-pixel median of October 2026 scenes,
static/s1_baseline_<orbit>.tif). Per zone: mean backscatter change in dB (averaged in linear power) and
the share of the zone at least 3 dB darker. Each new scene also gives a change map (img/s1_latest.jpg).

    python -m melt.s1 SITE_DIR              new scenes since the last run
    python -m melt.s1 --baseline            build the October baselines (run once, locally)
"""
import argparse
import datetime as dt
import json

import numpy as np

from melt.common import REPO, SEASON_START, STATIC, clean, load_state, save_state

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
BOX = (418e3, 2040e3, 482e3, 2136e3)                 # route area, EPSG:3031 (zones A, B, C)
RES = 100.0
BASE_DATES = ("2026-10-01", "2026-10-31")
ZONES_SHOWN = ("A", "B", "C")


def grid():
    from rasterio.transform import from_origin
    w, h = int((BOX[2] - BOX[0]) / RES), int((BOX[3] - BOX[1]) / RES)
    return from_origin(BOX[0], BOX[3], RES, RES), (h, w)


def bbox_ll():
    from pyproj import Transformer
    t = Transformer.from_crs(3031, 4326, always_xy=True)
    xs = np.linspace(BOX[0], BOX[2], 20); ys = np.linspace(BOX[1], BOX[3], 20)
    X, Y = np.meshgrid(xs, ys); lo, la = t.transform(X.ravel(), Y.ravel())
    return (float(lo.min()), float(la.min()), float(lo.max()), float(la.max()))


def search(start, end):
    from pystac_client import Client
    cat = Client.open(STAC)
    items = list(cat.search(collections=["sentinel-1-rtc"], bbox=list(bbox_ll()), datetime="%s/%s" % (start, end)).items())
    return sorted(items, key=lambda i: i.datetime)


def read(item):
    """Linear gamma0 HH on the 100 m route-area grid (NaN outside the scene)."""
    import planetary_computer as pc
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    tr, shape = grid()
    href = pc.sign(item.assets["hh"].href)
    with rasterio.open(href) as src, WarpedVRT(src, crs="EPSG:3031", transform=tr, width=shape[1], height=shape[0],
                                                resampling=Resampling.average, nodata=np.nan, src_nodata=0) as v:
        a = v.read(1).astype("float32")
    a[(a <= 0) | ~np.isfinite(a)] = np.nan
    return a


def zone_masks():
    import geopandas as gpd
    from rasterio.features import rasterize
    tr, shape = grid()
    Z = gpd.read_file(STATIC / "zones.geojson").to_crs(3031)
    return {r.zone: rasterize([r.geometry], out_shape=shape, transform=tr).astype(bool) for _, r in Z.iterrows()}


def baseline():
    import rasterio
    tr, shape = grid()
    by = {}
    for it in search(*BASE_DATES):
        o = int(it.properties.get("sat:relative_orbit"))
        try:
            by.setdefault(o, []).append(10 * np.log10(read(it)))
            print("baseline scene", it.id, "orbit", o)
        except Exception as e:
            print("skip", it.id, e)
    for o, st in by.items():
        med = np.nanmedian(np.array(st), axis=0).astype("float32")
        with rasterio.open(STATIC / ("s1_baseline_%03d.tif" % o), "w", driver="GTiff", height=shape[0], width=shape[1], count=1,
                           dtype="float32", crs="EPSG:3031", transform=tr, nodata=np.nan, compress="deflate") as dst:
            dst.write(med, 1)
        print("orbit %d: %d scenes -> static/s1_baseline_%03d.tif" % (o, len(st), o))


def change_map(dd, title, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd
    Z = gpd.read_file(STATIC / "zones.geojson").to_crs(3031)
    route = json.loads((STATIC / "zones_route.json").read_text())
    ext = [BOX[0] / 1e3, BOX[2] / 1e3, BOX[1] / 1e3, BOX[3] / 1e3]
    fig, ax = plt.subplots(figsize=(5.2, 7.6), constrained_layout=True)
    ax.set_facecolor("#888")
    h = ax.imshow(dd, extent=ext, cmap="RdBu", vmin=-8, vmax=8, interpolation="nearest")
    col = {"A": "#d6336c", "B": "#f08c00", "C": "#fab005"}
    for _, r in Z[Z.zone.isin(list(col))].iterrows():
        for part in getattr(r.geometry, "geoms", [r.geometry]):
            xx, yy = part.exterior.xy
            ax.plot(np.array(xx) / 1e3, np.array(yy) / 1e3, color=col[r.zone], lw=1.2)
    xy = np.array(route["route"]) / 1e3
    ax.plot(xy[:, 0], xy[:, 1], color="black", lw=1.2)
    for m in route["km_marks"]:
        if 20 <= m["km"] <= 110:
            ax.annotate(str(m["km"]), (m["x"] / 1e3, m["y"] / 1e3), fontsize=7, xytext=(3, 0), textcoords="offset points")
    ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    cb = fig.colorbar(h, ax=ax, orientation="horizontal", fraction=0.04, pad=0.01)
    cb.set_label("change from October (dB); blue = darker, wetter")
    ax.set_title(title, fontsize=9, loc="left")
    fig.savefig(out, dpi=110, pil_kwargs={"quality": 85})
    plt.close(fig)


def update(site):
    import rasterio
    from pathlib import Path
    st = load_state(site)
    S = st.setdefault("s1", dict(scenes={}))
    done = set(S["scenes"])
    start = max([SEASON_START.isoformat()] + [v["date"] for v in S["scenes"].values()])
    end = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    masks = zone_masks()
    new = [it for it in search(start, end) if it.id not in done]
    latest = None
    for it in new:
        o = int(it.properties.get("sat:relative_orbit"))
        bf = STATIC / ("s1_baseline_%03d.tif" % o)
        if not bf.exists():
            S["scenes"][it.id] = dict(date=it.datetime.strftime("%Y-%m-%d"), orbit=o, note="no October baseline for this orbit")
            continue
        try:
            lin = read(it)
        except Exception as e:
            print("skip", it.id, e); continue
        with rasterio.open(bf) as b:
            base = b.read(1)
        dd = 10 * np.log10(lin) - base
        rec = dict(date=it.datetime.strftime("%Y-%m-%d"), time=it.datetime.strftime("%H:%M"), orbit=o, zones={})
        for z, m in masks.items():
            ok = m & np.isfinite(dd)
            if ok.sum() < 0.5 * m.sum():
                continue
            mean_db = 10 * np.log10(np.nanmean(lin[ok])) - 10 * np.log10(np.nanmean(10 ** (base[ok] / 10)))
            rec["zones"][z] = dict(change_db=round(float(mean_db), 2), frac_3db=round(float(np.mean(dd[ok] <= -3)), 3))
        S["scenes"][it.id] = rec
        latest = (it, dd, rec)
        print(it.id, rec["zones"])
    if latest:
        it, dd, rec = latest
        img = Path(site) / "img"; img.mkdir(exist_ok=True)
        change_map(dd, "Sentinel-1 %s %s UTC, orbit %d, change from October median"
                   % (rec["date"], rec["time"], rec["orbit"]), img / "s1_latest.jpg")
        S["latest_image"] = dict(date=rec["date"], file="img/s1_latest.jpg")
    S["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save_state(site, st)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?")
    ap.add_argument("--baseline", action="store_true")
    a = ap.parse_args()
    baseline() if a.baseline else update(a.site)
