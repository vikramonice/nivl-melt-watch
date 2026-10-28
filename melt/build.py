"""
build.py
========
Builds the Nivl Melt Watch page (index.html) and status.txt from season.json and the static files.
Plain HTML with inline SVG charts; no scripts needed to read it.

    python -m melt.build SITE_DIR
"""
import argparse
import datetime as dt
import html
import json
from pathlib import Path

from melt.common import SEASON_START, STATIC, load_state, offset, static, today

ZN = {"A": "Grounding-line crossing", "B": "Blue-ice ponds before Maitri", "C": "Grounding zone near the crossing",
      "L": "Terminal lake", "S": "Rest of the shelf"}
ZKM = {"A": "route km 24-60", "B": "route km 60-100", "C": "early-warning area", "L": "", "S": ""}
E = html.escape


def dstr(iso, year=False):
    if not iso:
        return "&ndash;"
    d = dt.date.fromisoformat(iso[:10])
    return d.strftime("%d %b %Y" if year else "%d %b")


def off_date(o):
    return (SEASON_START + dt.timedelta(days=int(o))).strftime("%d %b")


def age(iso):
    if not iso:
        return ""
    n = (today() - dt.date.fromisoformat(iso[:10])).days
    return "today" if n == 0 else "1 day ago" if n == 1 else "%d days ago" % n


# ---------------------------------------------------------------- small SVG charts
def svg_lines(series, band=None, ymin=0, ymax=1, n=151, ylab="", w=640, h=190, mark=None, xmax=None):
    """series: [(label, colour, [values or None per day offset])]; band: (lo, hi, colour)."""
    pl, pr, pt, pb = 40, 10, 10, 26
    W, H = w - pl - pr, h - pt - pb
    xmax = xmax or n - 1
    X = lambda i: pl + W * i / xmax
    Y = lambda v: pt + H * (1 - (v - ymin) / ((ymax - ymin) or 1))
    s = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (w, h)]
    for k in range(5):
        v = ymin + (ymax - ymin) * k / 4
        s.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/>' % (pl, w - pr, Y(v), Y(v)))
        s.append('<text x="%d" y="%.1f" class="ax" text-anchor="end">%s</text>' % (pl - 4, Y(v) + 3, ("%d" % round(v)) if ymax - ymin >= 8 else ("%g" % round(v, 2))))
    for o, lab in ((31, "1 Nov"), (61, "1 Dec"), (92, "1 Jan"), (123, "1 Feb")):
        if o <= xmax:
            s.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" class="grid"/><text x="%.1f" y="%d" class="ax" text-anchor="middle">%s</text>'
                     % (X(o), X(o), pt, pt + H, X(o), h - 8, lab))
    if band:
        lo, hi, col = band
        pts = [(X(i), Y(min(max(v, ymin), ymax))) for i, v in enumerate(hi[:xmax + 1]) if v is not None]
        pts += [(X(i), Y(min(max(v, ymin), ymax))) for i, v in reversed(list(enumerate(lo[:xmax + 1]))) if v is not None]
        if pts:
            s.append('<polygon points="%s" fill="%s" opacity="0.35"/>' % (" ".join("%.1f,%.1f" % p for p in pts), col))
    for lab, col, vals, dash in series:
        seg, cur = [], []
        for i, v in enumerate(vals[:xmax + 1]):
            if v is None:
                if cur:
                    seg.append(cur); cur = []
            else:
                cur.append("%.1f,%.1f" % (X(i), Y(min(max(v, ymin), ymax))))
        if cur:
            seg.append(cur)
        for c in seg:
            if len(c) == 1:
                x, y = c[0].split(","); s.append('<circle cx="%s" cy="%s" r="2.5" fill="%s"/>' % (x, y, col))
            else:
                s.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2"%s/>' % (" ".join(c), col, ' stroke-dasharray="5 3"' if dash else ""))
    if mark is not None and 0 <= mark <= xmax:
        s.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" class="today"/>' % (X(mark), X(mark), pt, pt + H))
    s.append('<text x="%d" y="%d" class="ax">%s</text></svg>' % (pl + 4, pt + 10, E(ylab)))
    return "".join(s)


def legend(items):
    return '<div class="legend">' + " ".join('<span><i style="background:%s"></i>%s</span>' % (c, E(t)) for t, c in items) + "</div>"


# ---------------------------------------------------------------- sections
def zone_row(z, st, clim):
    a = st.get("amsr", {}).get(z, {})
    c = clim["amsr"]["zones"][z]
    seasons = c["seasons"]
    last = a.get("latest")
    o = offset(dt.date.fromisoformat(last)) if last else None
    lastday = a.get("days", {}).get(last, {}) if last else {}
    by_now = sum(1 for s in seasons if s["first_wet"] is not None and o is not None and s["first_wet"] <= o)
    fw = sorted(s["first_wet"] for s in seasons if s["first_wet"] is not None)
    med = fw[len(fw) // 2] if fw else None
    amsr = ("%s: %d of %d cells wet" % (dstr(last), lastday.get("n_wet", 0), lastday.get("n", 0)) if last else "no data")
    first = ("first wet day this season <b>%s</b>" % dstr(a["first_wet"])) if a.get("first_wet") else "no wet day yet this season"
    clim_txt = ("2002-25: first wet day median %s (earliest %s, latest %s); by %s, %d of %d seasons had had a wet day"
                % (off_date(med), off_date(fw[0]), off_date(fw[-1]), dstr(last), by_now, len(seasons))) if (fw and last) else ""
    s1 = sorted((v for v in st.get("s1", {}).get("scenes", {}).values() if z in v.get("zones", {})), key=lambda v: (v["date"], v.get("time", "")))
    s1t = ("%s (orbit %d): %+.1f dB, %.0f %% of the zone 3 dB or more darker"
           % (dstr(s1[-1]["date"]), s1[-1]["orbit"], s1[-1]["zones"][z]["change_db"], 100 * s1[-1]["zones"][z]["frac_3db"])) if s1 else "no scene yet"
    op = sorted((v for v in st.get("optical", {}).get("scenes", {}).values() if z in v.get("zones", {})), key=lambda v: v["date"])
    opt = ("%s (%s): %.1f km&sup2; open water (%.1f %% of the clear part, %.0f %% clear)"
           % (dstr(op[-1]["date"]), op[-1]["sensor"], op[-1]["zones"][z]["water_km2"], op[-1]["zones"][z]["water_pct"], 100 * op[-1]["zones"][z]["clear"])) if op else "no clear scene yet"
    ni = sorted((v for v in st.get("nisar", {}).get("scenes", {}).values() if z in v.get("zones", {})), key=lambda v: v["date"])
    nit = ("%s (track %s): %+.1f dB, %.0f %% 3 dB or more darker"
           % (dstr(ni[-1]["date"]), ni[-1]["track"], ni[-1]["zones"][z]["change_db"], 100 * ni[-1]["zones"][z]["frac_3db"])) if ni else "no acquisition yet"
    return ('<div class="zone z%s"><h3><span class="tag">%s</span> %s <small>%s</small></h3><dl>'
            '<dt>Passive microwave (wet snow, 10 km)</dt><dd>%s; %s<br><small>%s</small></dd>'
            '<dt>Sentinel-1 radar (change from October)</dt><dd>%s</dd>'
            '<dt>Sentinel-2 / Landsat (clear days only)</dt><dd>%s</dd>'
            '<dt>NISAR L-band (provisional)</dt><dd>%s</dd></dl></div>'
            % (z, z, ZN[z], ZKM[z], amsr, first, clim_txt, s1t, opt, nit))


def station_block(st, clim):
    rows = []
    for wmo in ("89514", "89512"):
        s = st.get("stations", {}).get(wmo)
        if not s:
            continue
        m = s["summary"]
        c = clim["stations"].get(wmo, {})
        latest = m.get("latest_day")
        o = offset(dt.date.fromisoformat(latest)) if latest else None
        pdd_c = ""
        if c.get("pdd_p50") and o is not None and 0 <= o < len(c["pdd_p50"]):
            pdd_c = " <small>(1990-2025 on this date: median %.1f, 10-90 %%: %.1f-%.1f)</small>" % (c["pdd_p50"][o], c["pdd_p10"][o], c["pdd_p90"][o])
        warm_c = ""
        if c.get("warm_p50") and o is not None and 0 <= o < len(c["warm_p50"]):
            warm_c = " <small>(median %d, 10-90 %%: %d-%d)</small>" % (c["warm_p50"][o], c["warm_p10"][o], c["warm_p90"][o])
        days = s["days"]
        last10 = [d for d in sorted(days) if days[d]["tmax"] is not None][-10:]
        strip = "".join('<td class="%s">%s<br><b>%s</b>%s</td>' % (
            "warm" if days[d]["tmax"] > 0 else "", dt.date.fromisoformat(d).strftime("%d"), "%.1f" % days[d]["tmax"],
            "<br>&#10052;" if days[d]["snow"] else ("<br>&#8776;" if days[d]["blow"] else "")) for d in last10)
        rows.append('<div class="station"><h3>%s <small>WMO %s, on rock; data to %s</small></h3>'
                    '<p>Since 1 Nov: <b>%d</b> days with max above 0&nbsp;&deg;C%s; current warm run <b>%d</b> days; '
                    'positive degree days <b>%.1f</b>%s.</p>'
                    '<p>Last snowfall or drifting/blowing snow reported: <b>%s</b> (%s days ago); since 1 Nov: %d snow days, %d drift/blowing-snow days.</p>'
                    '<table class="strip"><tr>%s</tr></table><p class="note">Daily max &deg;C, last 10 days (red: above 0; &#10052; snow, &#8776; drifting/blowing snow).</p></div>'
                    % (E(s["name"]), wmo, dstr(latest), m["warm_days"], warm_c, m["warm_run"], m["pdd"], pdd_c,
                       dstr(m.get("last_snow")), m.get("days_since_snow") if m.get("days_since_snow") is not None else "&ndash;",
                       m["snow_days"], m["blow_days"], strip))
    return "".join(rows)


def forecast_block(st):
    f = st.get("forecast", {})
    if not f.get("sites"):
        return "<p>No forecast available.</p>"
    c = f["cycle"]
    head = "AMPS run %s %s UTC (from the MINIS weather site)" % (dt.datetime.strptime(c, "%Y%m%d%H").strftime("%d %b"), c[8:])
    out = ['<p class="note">%s</p><div class="scroll"><table class="fc"><tr><th>Site</th>' % head]
    sites = [f["sites"][k] for k in ("grounding_zone_gz_a", "potsdam_shear_margin_sm_a", "maitri") if k in f["sites"]]
    dates = [d["date"] for d in sites[0]["days"]][:6]
    out.append("".join("<th>%s</th>" % dt.date.fromisoformat(d).strftime("%a %d") for d in dates) + "</tr>")
    for s in sites:
        cells = []
        for d in s["days"][:6]:
            cells.append('<td class="%s">%.0f&deg;<br><small>%s%s wind %d</small></td>' % (
                "warm" if d["tmax"] > 0 else "", d["tmax"], ("PDD %.1f, " % d["pdd"]) if d["pdd"] > 0 else "",
                ("snow %.1f mm," % d["snow_mm"]) if d["snow_mm"] >= 0.2 else "", round(d["wind_max"])))
        out.append("<tr><th>%s</th>%s</tr>" % (E(s["name"]), "".join(cells)))
    out.append('</table></div><p class="note">Max 2&nbsp;m temperature; PDD = positive degree days (daily mean above 0); snow in mm water; max mean wind m/s.</p>')
    return "".join(out)


def charts(st, clim, now_o):
    out = []
    for z in ("A", "B", "C"):
        c = clim["amsr"]["zones"][z]
        days = st.get("amsr", {}).get(z, {}).get("days", {})
        cur = [None] * 151
        for d, v in days.items():
            o = offset(dt.date.fromisoformat(d))
            if 0 <= o < 151:
                cur[o] = v["frac"]
        out.append("<h3>%s: share of the zone wet (passive microwave)</h3>" % ZN[z])
        out.append(svg_lines([("this season", "#d6336c", cur, False), ("2002-25 median", "#555", c["f50"], True)],
                             band=(c["f10"], c["f90"], "#74c0fc"), ymin=0, ymax=1, ylab="share of cells wet", mark=now_o))
        out.append(legend([("this season", "#d6336c"), ("2002-25 median", "#555"), ("2002-25, 10-90 %", "#74c0fc")]))
    s = st.get("stations", {}).get("89512")
    c = clim["stations"].get("89512", {})
    if s and c.get("pdd_p50"):
        cur, acc = [None] * 151, 0.0
        for d in sorted(s["days"]):
            o = offset(dt.date.fromisoformat(d))
            if 31 <= o < 151 and s["days"][d]["tavg"] is not None:
                acc += max(s["days"][d]["tavg"], 0); cur[o] = acc
        import math
        ymax = max(8, math.ceil(max(c["pdd_p90"]) * 1.05 / 8) * 8)          # round ticks (quarters of ymax)
        out.append("<h3>Novolazarevskaya: positive degree days since 1 Nov</h3>")
        out.append(svg_lines([("this season", "#d6336c", cur, False), ("1990-2025 median", "#555", c["pdd_p50"], True)],
                             band=(c["pdd_p10"], c["pdd_p90"], "#ffa8a8"), ymin=0, ymax=ymax, ylab="degree days", mark=now_o))
        out.append(legend([("this season", "#d6336c"), ("1990-2025 median", "#555"), ("1990-2025, 10-90 %", "#ffa8a8")]))
    sc = st.get("s1", {}).get("scenes", {})
    if sc:
        ser = []
        for z, col in (("A", "#d6336c"), ("B", "#f08c00"), ("C", "#e0a800")):
            v = [None] * 151
            for r in sc.values():
                if z in r.get("zones", {}):
                    o = offset(dt.date.fromisoformat(r["date"]))
                    if 0 <= o < 151:
                        v[o] = r["zones"][z]["change_db"]
            ser.append((ZN[z], col, v, False))
        out.append("<h3>Sentinel-1: backscatter change from October, per zone</h3>")
        out.append(svg_lines(ser, ymin=-12, ymax=4, ylab="dB (below 0 = darker)", mark=now_o))
        out.append(legend([(z[0], z[1]) for z in ser]) + '<p class="note">Dots are single passes; different orbits see the surface at different angles.</p>')
    return "".join(out)


def images(st, site):
    out = []
    for key, title in (("s1", "Sentinel-1 change map"), ("optical", "Latest clear optical image"), ("nisar", "NISAR change map")):
        li = st.get(key, {}).get("latest_image")
        if li and (Path(site) / li["file"]).exists():
            v = int((Path(site) / li["file"]).stat().st_mtime)
            out.append('<figure><a href="%s?v=%d"><img src="%s?v=%d" loading="lazy" alt="%s"></a><figcaption>%s, %s</figcaption></figure>'
                       % (li["file"], v, li["file"], v, title, title, dstr(li["date"], True)))
    return '<div class="imgs">%s</div>' % "".join(out) if out else "<p>No images yet.</p>"


def context(st, clim):
    rows = []
    for z in ("L", "S"):
        a = st.get("amsr", {}).get(z, {})
        fw = sorted(s["first_wet"] for s in clim["amsr"]["zones"][z]["seasons"] if s["first_wet"] is not None)
        rows.append("<li><b>%s</b>: first wet day this season %s (2002-25 median %s)</li>"
                    % (ZN[z], dstr(a.get("first_wet")) if a.get("first_wet") else "none yet", off_date(fw[len(fw) // 2])))
    si = st.get("seaice", {})
    if si.get("latest"):
        v = si["days"][si["latest"]]
        rows.append("<li><b>Sea ice in front of the shelf</b> (%s): concentration west %s %%, central %s %%, east %s %%</li>"
                    % (dstr(si["latest"]), v.get("W", {}).get("sic", "-"), v.get("C", {}).get("sic", "-"), v.get("E", {}).get("sic", "-")))
    return "<ul>%s</ul>" % "".join(rows)


def map_svg(st):
    """Route-area map (static/map.jpg) with zone outlines; fill shows the latest passive-microwave wet share."""
    import geopandas as gpd
    from melt.s1 import BOX
    Z = gpd.read_file(STATIC / "zones.geojson").to_crs(3031)
    W, H = BOX[2] - BOX[0], BOX[3] - BOX[1]
    w, h = 640, round(640 * H / W)
    col = {"A": "#d6336c", "B": "#f08c00", "C": "#e0a800"}
    polys = []
    for _, r in Z[Z.zone.isin(list(col))].set_index("zone", drop=False).loc[["C", "B", "A"]].iterrows():   # A on top
        a = st.get("amsr", {}).get(r.zone, {})
        last = a.get("latest"); fr = a.get("days", {}).get(last, {}).get("frac", 0) if last else 0
        for part in getattr(r.geometry.simplify(200), "geoms", [r.geometry.simplify(200)]):
            pts = " ".join("%.1f,%.1f" % ((x - BOX[0]) / W * w, (BOX[3] - y) / H * h) for x, y in part.exterior.coords)
            polys.append('<polygon points="%s" fill="#1c7ed6" fill-opacity="%.2f" stroke="%s" stroke-width="2"/>' % (pts, 0.6 * fr, col[r.zone]))
    route = json.loads((STATIC / "zones_route.json").read_text())
    rp = " ".join("%.1f,%.1f" % ((x - BOX[0]) / W * w, (BOX[3] - y) / H * h) for x, y in route["route"])
    km = "".join('<text x="%.1f" y="%.1f" class="km">%d</text>' % ((m["x"] - BOX[0]) / W * w + 4, (BOX[3] - m["y"]) / H * h, m["km"])
                 for m in route["km_marks"] if 10 <= m["km"] <= 120)
    lab = "".join('<text x="%.1f" y="%.1f" class="zl">%s</text>' % ((r.geometry.representative_point().x - BOX[0]) / W * w,
                                                                    (BOX[3] - r.geometry.representative_point().y) / H * h, r.zone)
                  for _, r in Z[Z.zone.isin(list(col))].iterrows())
    v = int((STATIC / "map.jpg").stat().st_mtime) if (STATIC / "map.jpg").exists() else 0
    return ('<svg viewBox="0 0 %d %d" class="map"><image href="map.jpg?v=%d" width="%d" height="%d"/>%s'
            '<polyline points="%s" fill="none" stroke="#fff" stroke-width="2"/>%s%s</svg>' % (w, h, v, w, h, "".join(polys), rp, km, lab))


def status_txt(st, clim):
    L = ["Nivl Melt Watch %s UTC" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")]
    for z in ("A", "B", "C"):
        a = st.get("amsr", {}).get(z, {}); last = a.get("latest")
        d = a.get("days", {}).get(last, {}) if last else {}
        s1 = sorted((v for v in st.get("s1", {}).get("scenes", {}).values() if z in v.get("zones", {})), key=lambda v: v["date"])
        L.append("%s %s: AMSR %s %s/%s cells wet, first wet %s; S1 %s" % (
            z, ZN[z], last or "-", d.get("n_wet", "-"), d.get("n", "-"), a.get("first_wet") or "none",
            ("%s %+.1f dB" % (s1[-1]["date"], s1[-1]["zones"][z]["change_db"])) if s1 else "-"))
    for wmo in ("89514", "89512"):
        s = st.get("stations", {}).get(wmo)
        if s:
            m = s["summary"]
            L.append("%s to %s: warm days %d, warm run %d, PDD %.1f, last snow/drift %s" % (
                s["name"], m.get("latest_day"), m["warm_days"], m["warm_run"], m["pdd"], m.get("last_snow")))
    return "\n".join(L) + "\n"


def build(site):
    st = load_state(site)
    clim = static("climatology.json")
    now_o = offset(today())
    tpl = (Path(__file__).parent / "page_template.html").read_text(encoding="utf-8")
    src_dates = [("Passive microwave", st.get("amsr_latest")), ("Sentinel-1", max([v["date"] for v in st.get("s1", {}).get("scenes", {}).values()] or [None], key=lambda x: x or "")),
                 ("Optical", max([v["date"] for v in st.get("optical", {}).get("scenes", {}).values()] or [None], key=lambda x: x or "")),
                 ("NISAR", max([v["date"] for v in st.get("nisar", {}).get("scenes", {}).values()] or [None], key=lambda x: x or "")),
                 ("Stations", max([v["summary"].get("latest_day") or "" for v in st.get("stations", {}).values()] or [None]))]
    fresh = " &middot; ".join("%s: %s" % (k, ("%s (%s)" % (dstr(v), age(v))) if v else "no data") for k, v in src_dates)
    errs = [e for e in (st.get("amsr_error"), st.get("s1", {}).get("error"), st.get("nisar", {}).get("error"), *(st.get("stations_errors") or []))
            if e and "no Earthdata login" not in e]                  # not an error: NISAR waits for the login
    from melt import figs
    page = (tpl.replace("{{UPDATED}}", dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y %H:%M UTC"))
            .replace("{{FRESH}}", fresh)
            .replace("{{ERRORS}}", ('<p class="note err">Last update could not reach: %s</p>' % E("; ".join(errs))) if errs else "")
            .replace("{{TEMP}}", figs.temp_chart(st))
            .replace("{{TILES}}", figs.tiles(st, clim))
            .replace("{{PDD}}", figs.pdd_chart(st, clim))
            .replace("{{GRID}}", figs.status_grid(st))
            .replace("{{FIRSTWET}}", figs.firstwet_chart(st, clim))
            .replace("{{WETCHARTS}}", figs.wet_charts(st, clim))
            .replace("{{S1CHART}}", figs.s1_chart(st))
            .replace("{{ZONES}}", "".join(zone_row(z, st, clim) for z in ("A", "B", "C")))
            .replace("{{MAP}}", map_svg(st))
            .replace("{{IMAGES}}", images(st, site))
            .replace("{{CONTEXT}}", context(st, clim)))
    Path(site, "index.html").write_text(page, encoding="utf-8")
    Path(site, "status.txt").write_text(status_txt(st, clim), encoding="utf-8")
    print("page written:", Path(site, "index.html"), "%.0f kB" % (Path(site, "index.html").stat().st_size / 1e3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    build(ap.parse_args().site)
