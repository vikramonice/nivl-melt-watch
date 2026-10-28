"""
nisar.py
========
NISAR L-band radar (GCOV, HH; NASA/ISRO, PROVISIONAL data, 12-day repeat; ASF DAAC, needs a NASA
Earthdata login). L-band reaches deeper into firn than Sentinel-1's C-band, so it also sees water held
below the surface; like C-band, wet snow and water darken it.

Each new acquisition over the route area is read as a window over HTTPS (no full download), averaged
to the 100 m route-area grid, and compared with the October 2026 mosaic of the same look direction
(static/nisar_baseline_<A|D>.tif, made from the Nivl project's outputs/gis/nisar_gcov_*_dB_2026oct.tif).
Per zone: mean change in dB (in linear power) and the share at least 3 dB darker; a change map.

Login: EARTHDATA_USERNAME / EARTHDATA_PASSWORD (or EARTHDATA_TOKEN) as GitHub secrets; locally ~/_netrc.

    python -m melt.nisar SITE_DIR
    python -m melt.nisar --baseline PATH_TO_NIVL     (once, locally)
"""
import argparse
import datetime as dt
import os
import re
from pathlib import Path

import numpy as np
import requests

from melt.common import SEASON_START, STATIC, load_state, save_state
from melt.s1 import BOX, bbox_ll, change_map, grid, zone_masks

CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
SHORT = "NISAR_L2_GCOV_PROVISIONAL_V1"


def baseline(nivl):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    tr, shape = grid()
    for ad, name in (("A", "asc"), ("D", "desc")):
        src_f = Path(nivl) / "outputs" / "gis" / ("nisar_gcov_%s_dB_2026oct.tif" % name)
        with rasterio.open(src_f) as src, WarpedVRT(src, crs="EPSG:3031", transform=tr, width=shape[1], height=shape[0],
                                                   resampling=Resampling.average, nodata=np.nan) as v:
            db = v.read(1).astype("float32")
        with rasterio.open(STATIC / ("nisar_baseline_%s.tif" % ad), "w", driver="GTiff", height=shape[0], width=shape[1], count=1,
                           dtype="float32", crs="EPSG:3031", transform=tr, nodata=np.nan, compress="deflate") as dst:
            dst.write(db, 1)
        print(ad, "baseline from", src_f.name, "valid %.0f %%" % (100 * np.isfinite(db).mean()))


def search(start):
    r = requests.get(CMR, params={"short_name": SHORT, "bounding_box": ",".join(str(v) for v in bbox_ll()),
                                  "temporal": "%sT00:00:00Z," % start, "page_size": 200}, timeout=120)
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        u = it["umm"]; gid = u["GranuleUR"]
        m = re.search(r"GCOV_(\d+)_(\d+)_([AD])_(\d+)_", gid)
        href = next((x["URL"] for x in u.get("RelatedUrls", []) if x.get("Type") == "GET DATA" and x["URL"].endswith(".h5")), "")
        if m and href:
            out.append(dict(gid=gid, url=href, track=m.group(2), ad=m.group(3), frame=m.group(4),
                            date=u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][:10]))
    return sorted(out, key=lambda g: g["date"])


def read_window(url):
    """HHHH (linear gamma0) on the route-area grid, read through earthaccess's authenticated session."""
    import earthaccess
    import h5py
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    if Path.home().joinpath("_netrc").exists():
        os.environ.setdefault("NETRC", str(Path.home() / "_netrc"))
    earthaccess.login(strategy="environment" if (os.environ.get("EARTHDATA_USERNAME") or os.environ.get("EARTHDATA_TOKEN")) else "netrc")
    fs = earthaccess.get_fsspec_https_session()
    tr, shape = grid()
    with fs.open(url, block_size=2 * 2 ** 20) as f, h5py.File(f, "r") as h:
        g = h["science/LSAR/GCOV/grids/frequencyA"]
        if "HHHH" not in g:
            return None
        x = g["xCoordinates"][:]; y = g["yCoordinates"][:]
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
        ix = np.where((x >= BOX[0] - abs(dx)) & (x <= BOX[2] + abs(dx)))[0]
        iy = np.where((y >= BOX[1] - abs(dy)) & (y <= BOX[3] + abs(dy)))[0]
        if not len(ix) or not len(iy):
            return None
        a = g["HHHH"][iy.min():iy.max() + 1, ix.min():ix.max() + 1].astype("float32")
        a[~np.isfinite(a) | (a <= 0)] = np.nan
        dst = np.full(shape, np.nan, "float32")
        reproject(a, dst, src_transform=from_origin(x[ix.min()] - dx / 2, y[iy.min()] - dy / 2, dx, -dy), src_crs="EPSG:3031",
                  dst_transform=tr, dst_crs="EPSG:3031", src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def update(site):
    import rasterio
    st = load_state(site)
    N = st.setdefault("nisar", dict(scenes={}))
    if not (os.environ.get("EARTHDATA_USERNAME") or os.environ.get("EARTHDATA_TOKEN") or Path.home().joinpath("_netrc").exists()
            or Path.home().joinpath(".netrc").exists()):
        N["error"] = "NISAR: no Earthdata login set up yet (repository secrets EARTHDATA_USERNAME, EARTHDATA_PASSWORD)"
        save_state(site, st); print(N["error"]); return st
    start = max([SEASON_START.isoformat()] + [v["date"] for v in N["scenes"].values()])
    try:
        grans = [g for g in search(start) if g["gid"] not in N["scenes"]]
    except Exception as e:
        N["error"] = "search failed: %s" % str(e)[:120]; save_state(site, st); return st
    masks = zone_masks()
    latest = None
    for g in grans:
        try:
            lin = read_window(g["url"])
        except Exception as e:
            N["error"] = "read failed (%s): %s" % (g["gid"][:40], str(e)[:120]); print(N["error"]); continue
        if lin is None or np.isfinite(lin).mean() < 0.05:
            N["scenes"][g["gid"]] = dict(date=g["date"], track=g["track"], ad=g["ad"], note="does not cover the route area")
            continue
        with rasterio.open(STATIC / ("nisar_baseline_%s.tif" % g["ad"])) as b:
            base = b.read(1)
        dd = 10 * np.log10(lin) - base
        rec = dict(date=g["date"], track=g["track"], ad=g["ad"], zones={})
        for z, m in masks.items():
            ok = m & np.isfinite(dd)
            if ok.sum() < 0.5 * m.sum():
                continue
            rec["zones"][z] = dict(change_db=round(float(10 * np.log10(np.nanmean(lin[ok])) - 10 * np.log10(np.nanmean(10 ** (base[ok] / 10)))), 2),
                                   frac_3db=round(float(np.mean(dd[ok] <= -3)), 3))
        N["scenes"][g["gid"]] = rec
        latest = (rec, dd)
        print(g["gid"][:60], rec["zones"])
        N["error"] = None
    if latest:
        rec, dd = latest
        img = Path(site) / "img"; img.mkdir(exist_ok=True)
        change_map(dd, "NISAR L-band %s, track %s %s, change from October mosaic (PROVISIONAL)"
                   % (rec["date"], rec["track"], "ascending" if rec["ad"] == "A" else "descending"), img / "nisar_latest.jpg")
        N["latest_image"] = dict(date=rec["date"], file="img/nisar_latest.jpg")
    N["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    save_state(site, st)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?")
    ap.add_argument("--baseline", metavar="NIVL")
    a = ap.parse_args()
    baseline(a.baseline) if a.baseline else update(a.site)
