"""
optical.py
==========
Sentinel-2 L2A and Landsat 8/9 C2 L2 (Microsoft Planetary Computer, anonymous) over the route area,
only useful when the sky is clear. For each new acquisition day with at least 50 % of zone A clear:
  - surface water per zone, on cloud-free pixels: NDWI_ice = (blue - red) / (blue + red) > 0.25 (the
    threshold used in the project's lake and channel mapping) AND red at most half of the same pixel in
    October (static/optical_ref_red.tif, clear October 2026 Landsat), both scaled by the scene's own snow
    brightness so a lower sun does not count as darkening (where no reference: red < 0.45 x the scene's
    snow, the project's dark-red rule). This keeps blue ice out: it is bluish but stays as bright as in
    October, while water darkens strongly. Bright slush may be missed: it shows in the radar and
    microwave signals instead. As km2 and %;
  - a true-colour picture of the route area (img/optical_latest.jpg).
Clouds: Sentinel-2 SCL classes 8-10; Landsat QA_PIXEL cloud and cirrus bits. Cloud masks miss some cloud
over snow, so the picture is the check.

    python -m melt.optical SITE_DIR
    python -m melt.optical --reference      build the October red reference (run once, locally)
"""
import argparse
import datetime as dt
from pathlib import Path

import numpy as np

from melt.common import SEASON_START, STATIC, load_state, save_state
from melt.s1 import BOX, bbox_ll, change_map, zone_masks

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
RES = 60.0                                            # m; water area per zone at 60 m
IMG_V = 2                                             # bump to redraw the latest picture after a style fix
OPT = {"sentinel-2-l2a": dict(b="B02", g="B03", r="B04", q="SCL", sensor="Sentinel-2"),
       "landsat-c2-l2": dict(b="blue", g="green", r="red", q="qa_pixel", sensor="Landsat")}


def grid():
    from rasterio.transform import from_origin
    return from_origin(BOX[0], BOX[3], RES, RES), (int((BOX[3] - BOX[1]) / RES), int((BOX[2] - BOX[0]) / RES))


def read(href, resampling="average"):
    import planetary_computer as pc
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    tr, shape = grid()
    with rasterio.open(pc.sign(href)) as src, WarpedVRT(src, crs="EPSG:3031", transform=tr, width=shape[1], height=shape[0],
                                                       resampling=getattr(Resampling, resampling), nodata=np.nan) as v:
        a = v.read(1).astype("float32")
    a[a == 0] = np.nan
    return a


def refl(coll, dn, date):
    if coll == "sentinel-2-l2a":
        return dn / 10000.0 - (0.1 if date >= dt.date(2022, 1, 25) else 0.0)
    return dn * 2.75e-5 - 0.2


def cloud_of(coll, q):
    if coll == "sentinel-2-l2a":
        return np.isin(q, [8, 9, 10])
    qi = np.nan_to_num(q).astype(np.uint16)
    return ((qi >> 3) & 1).astype(bool) | ((qi >> 2) & 1).astype(bool)


def masks_60m():
    import geopandas as gpd
    from rasterio.features import rasterize
    tr, shape = grid()
    Z = gpd.read_file(STATIC / "zones.geojson").to_crs(3031)
    return {r.zone: rasterize([r.geometry], out_shape=shape, transform=tr).astype(bool) for _, r in Z.iterrows()}


def picture(R, G, B, title, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd
    import json
    rgb = np.dstack([R, G, B])
    rgb = np.clip(rgb / np.nanpercentile(rgb, 99.5), 0, 1) ** 1.6     # snow is very bright in L2: scale to the scene
    rgb[~np.isfinite(rgb)] = 0.5
    Z = gpd.read_file(STATIC / "zones.geojson").to_crs(3031)
    route = json.loads((STATIC / "zones_route.json").read_text())
    ext = [BOX[0] / 1e3, BOX[2] / 1e3, BOX[1] / 1e3, BOX[3] / 1e3]
    fig, ax = plt.subplots(figsize=(5.2, 7.4), constrained_layout=True)
    ax.imshow(rgb, extent=ext)
    col = {"A": "#d6336c", "B": "#f08c00", "C": "#fab005"}
    for _, r in Z[Z.zone.isin(list(col))].iterrows():
        for part in getattr(r.geometry, "geoms", [r.geometry]):
            xx, yy = part.exterior.xy
            ax.plot(np.array(xx) / 1e3, np.array(yy) / 1e3, color=col[r.zone], lw=1)
    xy = np.array(route["route"]) / 1e3
    ax.plot(xy[:, 0], xy[:, 1], color="black", lw=1)
    ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=9, loc="left")
    fig.savefig(out, dpi=110, pil_kwargs={"quality": 85})
    plt.close(fig)


def update(site, max_cloud=70):
    from pystac_client import Client
    st = load_state(site)
    O = st.setdefault("optical", dict(scenes={}))
    start = max([SEASON_START.isoformat()] + [v["date"] for v in O["scenes"].values()])
    end = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    cat = Client.open(STAC)
    masks = masks_60m()
    import rasterio
    with rasterio.open(STATIC / "optical_ref_red.tif") as r_:
        ref = r_.read(1)
    latest = None
    for coll, b in OPT.items():
        q = {"eo:cloud_cover": {"lt": max_cloud}}
        if coll == "landsat-c2-l2":
            q["platform"] = {"in": ["landsat-8", "landsat-9"]}
        items = list(cat.search(collections=[coll], bbox=list(bbox_ll()), datetime="%s/%s" % (start, end), query=q).items())
        bydate = {}
        for it in items:
            bydate.setdefault(it.datetime.strftime("%Y-%m-%d"), []).append(it)
        for d, its in sorted(bydate.items()):
            key = "%s_%s" % (b["sensor"], d)
            if key in O["scenes"]:
                continue
            acc = None
            for it in sorted(its, key=lambda i: i.properties.get("eo:cloud_cover", 100)):
                try:
                    arr = {k: read(it.assets[b[k]].href, "nearest" if k == "q" else "average") for k in ("b", "g", "r", "q")}
                except Exception as e:
                    print("skip", it.id, repr(e)[:80]); continue
                acc = arr if acc is None else {k: np.where(np.isfinite(acc[k]), acc[k], arr[k]) for k in acc}
            if acc is None:
                continue
            day = dt.date.fromisoformat(d)
            B, G, R = (refl(coll, acc[k], day) for k in ("b", "g", "r"))
            cl = cloud_of(coll, acc["q"]) | ~np.isfinite(R)
            clearA = float(np.mean(~cl[masks["A"]]))
            rec = dict(date=d, sensor=b["sensor"], clear_A=round(clearA, 2), zones={})
            if clearA >= 0.5:
                with np.errstate(invalid="ignore", divide="ignore"):
                    ndwi = (B - R) / (B + R)
                    # brightness relative to the scene's own snow, so low sun does not count as darkening
                    snow_now = np.nanmedian(R[masks["S"] & ~cl & (ndwi < 0.1)])
                    rel, rel_ref = R / snow_now, ref / np.nanmedian(ref[masks["S"]])
                    dark = np.where(np.isfinite(rel_ref), rel < 0.5 * rel_ref, rel < 0.45)
                for z, m in masks.items():
                    ok = m & ~cl
                    if ok.sum() < 0.3 * m.sum():
                        continue
                    w = (ndwi > 0.25) & dark & ok
                    rec["zones"][z] = dict(water_km2=round(float(w.sum() * RES * RES / 1e6), 2),
                                           water_pct=round(100 * float(w.sum() / ok.sum()), 2), clear=round(float(ok.sum() / m.sum()), 2))
                latest = (rec, R, G, B)
            O["scenes"][key] = rec
            print(key, rec)
    if latest is None and O.get("img_v") != IMG_V:                     # redraw the newest clear picture once after a style change
        good = sorted((v for v in O["scenes"].values() if v.get("zones")), key=lambda v: v["date"])
        if good:
            rec = good[-1]
            coll = "sentinel-2-l2a" if rec["sensor"] == "Sentinel-2" else "landsat-c2-l2"
            b_ = OPT[coll]
            its = sorted(cat.search(collections=[coll], bbox=list(bbox_ll()), datetime="%s/%s" % (rec["date"], rec["date"])).items(),
                         key=lambda i: i.properties.get("eo:cloud_cover", 100))
            acc = None
            for it in its:
                arr = {k: read(it.assets[b_[k]].href) for k in ("b", "g", "r")}
                acc = arr if acc is None else {k: np.where(np.isfinite(acc[k]), acc[k], arr[k]) for k in acc}
            if acc:
                day = dt.date.fromisoformat(rec["date"])
                latest = (rec, refl(coll, acc["r"], day), refl(coll, acc["g"], day), refl(coll, acc["b"], day))
    if latest:
        rec, R, G, B = latest
        O["img_v"] = IMG_V
        img = Path(site) / "img"; img.mkdir(exist_ok=True)
        picture(R, G, B, "%s %s, true colour (zones A red, B orange, C yellow)" % (rec["sensor"], rec["date"]), img / "optical_latest.jpg")
        O["latest_image"] = dict(date=rec["date"], sensor=rec["sensor"], file="img/optical_latest.jpg")
    O["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save_state(site, st)
    return st


def reference(dates=("2026-10-01", "2026-10-31")):
    """Median clear-sky red reflectance from October Landsat scenes with zone A at least 90 % clear."""
    import rasterio
    from pystac_client import Client
    tr, shape = grid()
    masks = masks_60m()
    cat = Client.open(STAC)
    items = list(cat.search(collections=["landsat-c2-l2"], bbox=list(bbox_ll()), datetime="%s/%s" % dates,
                            query={"platform": {"in": ["landsat-8", "landsat-9"]}, "eo:cloud_cover": {"lt": 70}}).items())
    stack = []
    for it in items:
        try:
            R = refl("landsat-c2-l2", read(it.assets["red"].href), it.datetime.date())
            q = read(it.assets["qa_pixel"].href, "nearest")
        except Exception as e:
            print("skip", it.id, repr(e)[:80]); continue
        cl = cloud_of("landsat-c2-l2", q) | ~np.isfinite(R)
        if np.mean(~cl[masks["A"]]) >= 0.9:
            R[cl] = np.nan; stack.append(R); print("reference scene", it.id)
    ref = np.nanmedian(np.array(stack), axis=0).astype("float32")
    with rasterio.open(STATIC / "optical_ref_red.tif", "w", driver="GTiff", height=shape[0], width=shape[1], count=1, dtype="float32",
                       crs="EPSG:3031", transform=tr, nodata=np.nan, compress="deflate") as dst:
        dst.write(ref, 1)
    print("%d scenes -> static/optical_ref_red.tif; zone A median red %.2f" % (len(stack), np.nanmedian(ref[masks["A"]])))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?")
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args()
    reference() if a.reference else update(a.site)
