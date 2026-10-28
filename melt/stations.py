"""
stations.py
===========
Maitri (WMO 89514) and Novolazarevskaya (89512), Schirmacher Oasis, both on rock (warmer than the shelf).

Sources
  Ogimet SYNOP (https://www.ogimet.com, free, no key): every report, decoded for
    air temperature (1sTTT), daily max / min (section 333: 1snTxTxTx, 2snTnTnTn), present weather
    (7wwW1W2: snow ww 22, 26, 70-79, 85-87; drifting / blowing snow ww 36-39), wind (Nddff).
  GHCN-Daily (NOAA NCEI, free): daily TMAX, TAVG, PRCP, a few days late; used where present.

Per station and UTC day: TMAX (GHCN, else the highest of the reports and the reported max), TAVG
(GHCN, else the mean of the reports, at least 2), snow / blowing-snow flags from the reports.
Derived since 1 November: days with TMAX > 0, the run of consecutive warm days up to the latest day,
positive degree days (sum of TAVG above 0, as in the project's analysis), days since the last snowfall
or drifting / blowing snow report.

    python -m melt.stations SITE_DIR [--days 4]
"""
import argparse
import datetime as dt
import io
import time

import requests

from melt.common import PDD_START, SEASON_START, UA, clean, load_state, save_state, today

OGIMET = "https://www.ogimet.com/cgi-bin/getsynop"
GHCN = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/%s.csv"
STATIONS = {"89514": ("Maitri", "AYM00089514"), "89512": ("Novolazarevskaya", "AYM00089512")}
SNOW_WW = set([22, 26, 85, 86, 87]) | set(range(70, 80))
BLOW_WW = set(range(36, 40))


def fetch_synop(block, begin, end):
    why = ""
    for k in range(3):
        try:
            r = requests.get(OGIMET, params=dict(block=block, begin=begin.strftime("%Y%m%d%H%M"), end=end.strftime("%Y%m%d%H%M")),
                             timeout=60, headers=UA)
            if r.ok and r.text.startswith(block):
                return r.text.splitlines()
            if r.ok:
                return []
            why = "HTTP %d" % r.status_code
        except requests.RequestException as e:
            why = "%s: %s" % (type(e).__name__, str(e)[:160])
        time.sleep(15 * (k + 1))
    raise RuntimeError("Ogimet did not answer for %s (%s)" % (block, why))


def _t(x):
    """Temperature group sTTT -> degC (s: 0 positive, 1 negative)."""
    return (-1 if x[1] == "1" else 1) * int(x[2:]) / 10


def decode(line):
    """One Ogimet line 'IIiii,Y,M,D,h,m,AAXX ...=' -> dict (missing values = None)."""
    f = line.split(",", 6)
    t = dt.datetime(int(f[1]), int(f[2]), int(f[3]), int(f[4]), int(f[5]))
    g = f[6].rstrip("=").split()
    if len(g) < 5 or g[0] != "AAXX":
        return None
    kt = g[1][4] in "34"
    rec = dict(t=t.strftime("%Y-%m-%d %H:%M"), T=None, Tx=None, Tn=None, ww=None, ws=None)
    nddff, i = g[4], 5
    if "/" not in nddff[1:]:
        ff = int(nddff[3:5])
        if ff == 99 and len(g) > 5 and g[5].startswith("00"):
            ff = int(g[5][2:]); i = 6
        rec["ws"] = round(ff * (0.514444 if kt else 1.0), 1)
    sec3 = False
    for x in g[i:]:
        if x == "333":
            sec3 = True; continue
        if x in ("444", "555"):
            break
        if len(x) != 5 or "/" in x[:3]:
            continue
        if not sec3:
            if x[0] == "1" and "/" not in x:
                rec["T"] = _t(x)
            elif x[0] == "7" and x[1:3].isdigit():
                rec["ww"] = int(x[1:3])
        else:
            if x[0] == "1" and "/" not in x:
                rec["Tx"] = _t(x)
            elif x[0] == "2" and "/" not in x:
                rec["Tn"] = _t(x)
    return rec


def ghcn(code):
    import pandas as pd
    r = requests.get(GHCN % code, timeout=120, headers=UA)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text), low_memory=False, parse_dates=["DATE"])
    d = d[d.DATE >= pd.Timestamp(SEASON_START)]
    out = {}
    for _, row in d.iterrows():
        v = {k: (float(row[k]) / 10 if k in row and pd.notna(row[k]) else None) for k in ("TMAX", "TAVG", "PRCP")}
        out[row.DATE.strftime("%Y-%m-%d")] = v
    return out


def daily(reports, gh):
    """{date: {...}} from the reports and GHCN."""
    by = {}
    for r in reports.values():
        by.setdefault(r["t"][:10], []).append(r)
    days = sorted(set(by) | set(gh))
    out = {}
    for d in days:
        rs = by.get(d, [])
        Ts = [r["T"] for r in rs if r["T"] is not None]
        Txs = [r["Tx"] for r in rs if r["Tx"] is not None]
        g = gh.get(d, {})
        tmax = g.get("TMAX") if g.get("TMAX") is not None else (max(Ts + Txs) if (Ts or Txs) else None)
        tavg = g.get("TAVG") if g.get("TAVG") is not None else (sum(Ts) / len(Ts) if len(Ts) >= 2 else None)
        ww = [r["ww"] for r in rs if r["ww"] is not None]
        out[d] = dict(tmax=tmax, tavg=tavg, n_reports=len(rs), src="GHCN" if g.get("TMAX") is not None else "SYNOP",
                      snow=any(w in SNOW_WW for w in ww), blow=any(w in BLOW_WW for w in ww), prcp=g.get("PRCP"),
                      wsmax=max([r["ws"] for r in rs if r["ws"] is not None], default=None))
    return out


def summary(days):
    ds = sorted(d for d in days if d >= PDD_START.isoformat())
    warm = [d for d in ds if (days[d]["tmax"] or -99) > 0]
    run, last = 0, None
    for d in reversed(ds):
        if days[d]["tmax"] is None:
            continue
        if days[d]["tmax"] > 0:
            run += 1
        else:
            break
    pdd = sum(max(days[d]["tavg"], 0) for d in ds if days[d]["tavg"] is not None)
    snowy = [d for d in sorted(days) if days[d]["snow"] or days[d]["blow"]]
    latest = max((d for d in days if days[d]["tmax"] is not None), default=None)
    since_snow = (dt.date.fromisoformat(latest) - dt.date.fromisoformat(snowy[-1])).days if snowy and latest else None
    return dict(warm_days=len(warm), warm_run=run, pdd=round(pdd, 1), latest_day=latest,
                last_snow=snowy[-1] if snowy else None, days_since_snow=since_snow,
                snow_days=sum(days[d]["snow"] for d in ds), blow_days=sum(days[d]["blow"] for d in ds),
                first_warm=warm[0] if warm else None)


def update(site, days_back=4):
    st = load_state(site)
    S = st.setdefault("stations", {})
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    errors = []
    for wmo, (name, code) in STATIONS.items():
        s = S.setdefault(wmo, dict(name=name, reports={}, ghcn={}))
        start = now - dt.timedelta(days=days_back)
        if not s["reports"]:                                   # first run: back to the season start, 10 days a request
            start = dt.datetime.combine(SEASON_START, dt.time())
        t0 = start
        while t0 < now:
            t1 = min(t0 + dt.timedelta(days=10), now)
            try:
                for ln in fetch_synop(wmo, t0, t1):
                    rec = decode(ln)
                    if rec:
                        s["reports"][rec["t"]] = rec
            except RuntimeError as e:
                errors.append(str(e)); break
            t0 = t1
            time.sleep(2)
        try:
            s["ghcn"] = ghcn(code)
        except Exception as e:                                 # keep the last copy
            errors.append("GHCN %s: %s" % (code, str(e)[:120]))
        s["days"] = daily(s["reports"], s["ghcn"])
        s["summary"] = summary(s["days"])
        print(name, s["summary"])
    st["stations_updated"] = now.strftime("%Y-%m-%d %H:%M")
    st["stations_errors"] = errors
    save_state(site, st)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--days", type=float, default=4)
    a = ap.parse_args()
    update(a.site, a.days)
