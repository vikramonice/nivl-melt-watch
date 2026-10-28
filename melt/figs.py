"""Figures for the Nivl Melt Watch page: inline SVG and small HTML graphics (light theme)."""
import datetime as dt
import html
import math

from melt.common import SEASON_START, offset, today

E = html.escape
INK, MUTED, GRID = "#1d2329", "#5d6872", "#e3e7eb"
COL = {"maitri": "#1971c2", "novo": "#2f9e44", "c13": "#e8590c", "A": "#d6336c", "B": "#f08c00", "C": "#e0a800"}
REFC = "#7048e8"                                   # reference season (last summer)
ZN = {"A": "Grounding-line crossing (km 24-60)", "B": "Blue-ice ponds before Maitri (km 60-100)", "C": "Grounding zone near the crossing"}


def odate(o, fmt="%d %b"):
    return (SEASON_START + dt.timedelta(days=int(o))).strftime(fmt)


def dshort(iso):
    return dt.date.fromisoformat(iso[:10]).strftime("%d %b") if iso else "-"


def svg_series(series, xmin, xmax, yticks, ylab="", w=660, h=230, band=None, hlines=(), marks=(), today_x=None, xstep=None):
    """series: [(colour, [(x, y)], dashed, dot)]; x in days since 1 Oct."""
    pl, pr, pt, pb = 42, 12, 14, 28
    W, H = w - pl - pr, h - pt - pb
    ymin, ymax = yticks[0], yticks[-1]
    X = lambda x: pl + W * (x - xmin) / max(1, xmax - xmin)
    Y = lambda y: pt + H * (1 - (min(max(y, ymin), ymax) - ymin) / (ymax - ymin))
    s = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (w, h)]
    for v in yticks:
        s.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s"/><text x="%d" y="%.1f" class="ax" text-anchor="end">%s</text>'
                 % (pl, w - pr, Y(v), Y(v), GRID, pl - 5, Y(v) + 4, ("%g" % v)))
    step = xstep or (7 if xmax - xmin <= 70 else 14 if xmax - xmin <= 140 else 30)
    first = xmin + (-(SEASON_START + dt.timedelta(days=xmin)).weekday()) % 7 if step == 7 else xmin
    for x in range(int(first), int(xmax) + 1, step):
        s.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s"/><text x="%.1f" y="%d" class="ax" text-anchor="middle">%s</text>'
                 % (X(x), X(x), pt, pt + H, GRID, X(x), h - 9, odate(x)))
    if band:
        lo, hi, colr = band
        pts = [(X(x), Y(y)) for x, y in hi] + [(X(x), Y(y)) for x, y in reversed(lo)]
        if pts:
            s.append('<polygon points="%s" fill="%s" opacity="0.35"/>' % (" ".join("%.1f,%.1f" % p for p in pts), colr))
    for y, colr, dash, lab in hlines:
        s.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="1.6"%s/>' % (pl, w - pr, Y(y), Y(y), colr, ' stroke-dasharray="6 4"' if dash else ""))
        if lab:
            s.append('<text x="%d" y="%.1f" class="ax" fill="%s">%s</text>' % (w - pr - 4 - 6 * len(lab), Y(y) - 4, colr, E(lab)))
    if today_x is not None and xmin <= today_x <= xmax:
        s.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-dasharray="2 3"/><text x="%.1f" y="%d" class="ax" text-anchor="middle">today</text>'
                 % (X(today_x), X(today_x), pt, pt + H, INK, X(today_x), pt + 9))
    for colr, pts, dash, dot in series:
        pts = [(x, y) for x, y in pts if y is not None and xmin <= x <= xmax]
        segs, cur, last = [], [], None
        for x, y in pts:
            if last is not None and x - last > 1.5:
                segs.append(cur); cur = []
            cur.append((x, y)); last = x
        if cur:
            segs.append(cur)
        for c in segs:
            if len(c) > 1:
                s.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.2"%s/>'
                         % (" ".join("%.1f,%.1f" % (X(x), Y(y)) for x, y in c), colr, ' stroke-dasharray="5 4"' if dash else ""))
            if dot or len(c) == 1:
                s.extend('<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s"/>' % (X(x), Y(y), colr) for x, y in c)
    for x, txt, colr in marks:
        if xmin <= x <= xmax:
            s.append('<text x="%.1f" y="%d" font-size="12" text-anchor="middle" fill="%s">%s</text>' % (X(x), pt + H - 4, colr, txt))
    s.append('<text x="%d" y="%d" class="ax">%s</text></svg>' % (pl + 4, pt + 10, E(ylab)))
    return "".join(s)


def legend(items):
    return '<div class="legend">' + "".join('<span><i style="background:%s%s"></i>%s</span>'
                                            % (c, ";height:2px;border-top:2px dashed %s;background:none" % c if d else "", E(t)) for t, c, d in items) + "</div>"


# ------------------------------------------------------------------ temperature
def temp_chart(st):
    S = st.get("stations", {})
    now = offset(today())
    pts, ys, marks = {}, [], []
    for wmo, key in (("89514", "maitri"), ("89512", "novo")):
        days = S.get(wmo, {}).get("days", {})
        p = [(offset(dt.date.fromisoformat(d)), v["tmax"]) for d, v in sorted(days.items()) if v["tmax"] is not None]
        pts[key] = p; ys += [y for _, y in p]
        for d, v in days.items():
            if v["snow"]:
                marks.append((offset(dt.date.fromisoformat(d)), "&#10052;", "#1c7ed6"))
            elif v["blow"]:
                marks.append((offset(dt.date.fromisoformat(d)), "&#8776;", "#868e96"))
    fc = st.get("forecast", {}).get("sites", {})
    fcp = {}
    for slug, key in (("grounding_zone_gz_a", "c13"), ("maitri", "maitri")):
        p = [(offset(dt.date.fromisoformat(d["date"])), d["tmax"]) for d in fc.get(slug, {}).get("days", []) if dt.date.fromisoformat(d["date"]) >= today()]
        fcp[key] = p; ys += [y for _, y in p]
    xmax = max([now + 6] + [x for p in fcp.values() for x, _ in p])
    xmin = max(0, xmax - 70)
    lo = 5 * math.floor((min(ys + [-15]) - 1) / 5); hi = 5 * math.ceil((max(ys + [3]) + 1) / 5)
    ser = [(COL["maitri"], pts.get("maitri", []), False, True), (COL["novo"], pts.get("novo", []), False, True),
           (COL["maitri"], fcp.get("maitri", []), True, False), (COL["c13"], fcp.get("c13", []), True, False)]
    svg = svg_series(ser, xmin, xmax, list(range(lo, hi + 1, 5)), ylab="daily maximum, °C", hlines=[(0, "#e03131", True, "0 °C")],
                     marks=marks, today_x=now)
    leg = legend([("Maitri", COL["maitri"], False), ("Novolazarevskaya", COL["novo"], False), ("forecast Maitri (AMPS)", COL["maitri"], True),
                  ("forecast C13, grounding zone (AMPS)", COL["c13"], True)])
    return svg + leg


def pdd_chart(st, clim):
    s = st.get("stations", {}).get("89512")
    c = clim["stations"].get("89512", {})
    if not s or not c.get("pdd_p50"):
        return ""
    now = offset(today())
    acc, cur = 0.0, []
    for d in sorted(s["days"]):
        o = offset(dt.date.fromisoformat(d))
        if o >= 31 and s["days"][d]["tavg"] is not None:
            acc += max(s["days"][d]["tavg"], 0); cur.append((o, acc))
    top = max(8, math.ceil(max(c["pdd_p90"]) / 10) * 10)
    band = ([(i, v) for i, v in enumerate(c["pdd_p10"]) if i >= 31], [(i, v) for i, v in enumerate(c["pdd_p90"]) if i >= 31], "#ffa8a8")
    ref = c.get("ref") or {}
    refp = [(i, v) for i, v in enumerate(ref.get("pdd") or []) if i >= 31]
    top = max(top, math.ceil(max([v for _, v in refp] + [0]) / 10) * 10)
    svg = svg_series([(REFC, refp, False, False), ("#c92a2a", cur, False, False), (MUTED, [(i, v) for i, v in enumerate(c["pdd_p50"]) if i >= 31], True, False)],
                     31, 150, list(range(0, top + 1, top // 4)), ylab="degree days since 1 Nov (Novolazarevskaya)", band=band, today_x=now, h=200)
    return svg + legend([("this season", "#c92a2a", False), ("last summer, %s" % ref.get("season", "2025/26"), REFC, False),
                         ("1990-2025 median", MUTED, True), ("1990-2025, 10-90 %", "#ffa8a8", False)])


def tiles(st, clim):
    S = st.get("stations", {})
    m = S.get("89514", {}).get("summary", {}); n = S.get("89512", {}).get("summary", {})
    c = clim["stations"].get("89512", {})
    o = offset(dt.date.fromisoformat(n["latest_day"])) if n.get("latest_day") else None
    med = (" <small>median %.0f</small>" % c["pdd_p50"][o]) if (c.get("pdd_p50") and o is not None and 0 <= o < 151) else ""
    t = [("Days above 0 °C since 1 Nov", "%s / %s" % (m.get("warm_days", "-"), n.get("warm_days", "-")), "Maitri / Novolazarevskaya"),
         ("Current warm run", "%s / %s days" % (m.get("warm_run", "-"), n.get("warm_run", "-")), "consecutive days above 0 °C"),
         ("Degree days since 1 Nov", "%.0f%s" % (n.get("pdd", 0), med), "Novolazarevskaya (daily mean above 0)"),
         ("Since snow or blowing snow", "%s days" % (n.get("days_since_snow") if n.get("days_since_snow") is not None else "-"),
          "last: %s" % dshort(n.get("last_snow")))]
    return '<div class="tiles">' + "".join('<div class="tile"><div class="tl">%s</div><div class="tv">%s</div><div class="ts">%s</div></div>'
                                           % (E(a), b, E(cc)) for a, b, cc in t) + "</div>"


# ------------------------------------------------------------------ route crossing
def _blue(x):
    """0..1 -> light grey to blue."""
    x = max(0.0, min(1.0, x))
    r = round(241 + (28 - 241) * x); g = round(243 + (126 - 243) * x); b = round(245 + (214 - 245) * x)
    return "#%02x%02x%02x" % (r, g, b), ("#fff" if x > 0.55 else INK)


def status_grid(st):
    def latest(key, z):
        sc = [v for v in st.get(key, {}).get("scenes", {}).values() if z in v.get("zones", {})]
        return max(sc, key=lambda v: (v["date"], v.get("time", ""))) if sc else None
    rows = []
    for z in ("A", "B", "C"):
        a = st.get("amsr", {}).get(z, {}); last = a.get("latest")
        cells = []
        if last:
            d = a["days"][last]; bg, fg = _blue(d["frac"])
            cells.append((bg, fg, "%d / %d cells wet" % (d["n_wet"], d["n"]), dshort(last)))
        else:
            cells.append(("#dee2e6", INK, "no data", ""))
        s1 = latest("s1", z)
        if s1:
            ch = s1["zones"][z]["change_db"]; bg, fg = _blue(-ch / 6 if ch < 0 else 0)
            cells.append((bg, fg, "%+.1f dB" % ch, dshort(s1["date"])))
        else:
            cells.append(("#dee2e6", INK, "no scene", ""))
        op = latest("optical", z)
        if op:
            w = op["zones"][z]["water_km2"]; bg, fg = _blue(w / 10)
            cells.append((bg, fg, "%.1f km² water" % w, dshort(op["date"])))
        else:
            cells.append(("#dee2e6", INK, "no clear scene", ""))
        ni = latest("nisar", z)
        if ni:
            ch = ni["zones"][z]["change_db"]; bg, fg = _blue(-ch / 6 if ch < 0 else 0)
            cells.append((bg, fg, "%+.1f dB" % ch, dshort(ni["date"])))
        else:
            cells.append(("#dee2e6", INK, "no data yet", ""))
        rows.append('<tr><th><span class="zt z%s">%s</span> %s</th>%s</tr>' % (z, z, E(ZN[z]), "".join(
            '<td style="background:%s;color:%s">%s<br><small style="color:%s">%s</small></td>' % (bg, fg, v, fg, d) for bg, fg, v, d in cells)))
    return ('<div class="scroll"><table class="grid"><tr><th></th><th>Wet snow<br><small>microwave</small></th><th>Radar<br><small>Sentinel-1</small></th>'
            '<th>Open water<br><small>optical</small></th><th>Radar<br><small>NISAR</small></th></tr>%s</table></div>' % "".join(rows))


def firstwet_chart(st, clim):
    xmin, xmax = 31, 135                                   # 1 Nov - 13 Feb
    w, h, pl, pr = 660, 190, 150, 14
    W = w - pl - pr
    X = lambda x: pl + W * (min(max(x, xmin), xmax) - xmin) / (xmax - xmin)
    now = offset(today())
    s = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (w, h)]
    for x in (31, 46, 61, 76, 92, 107, 123):
        s.append('<line x1="%.1f" x2="%.1f" y1="12" y2="%d" stroke="%s"/><text x="%.1f" y="%d" class="ax" text-anchor="middle">%s</text>'
                 % (X(x), X(x), h - 26, GRID, X(x), h - 10, odate(x)))
    for i, z in enumerate(("A", "B", "C")):
        y = 34 + i * 48
        seasons = clim["amsr"]["zones"][z]["seasons"]
        fw = sorted(v["first_wet"] for v in seasons if v["first_wet"] is not None)
        s.append('<text x="%d" y="%d" class="zlab" fill="%s">%s</text><text x="%d" y="%d" class="ax">%s</text>'
                 % (8, y - 2, COL[z], "Zone " + z, 8, y + 12, {"A": "crossing, km 24-60", "B": "blue-ice ponds, km 60-100", "C": "grounding zone"}[z]))
        for v in fw:
            s.append('<circle cx="%.1f" cy="%d" r="4" fill="%s" opacity="0.45"/>' % (X(v), y, MUTED))
        last = next((v for v in seasons if v["season"] == "2025/26"), None)
        if last and last["first_wet"] is not None:
            s.append('<circle cx="%.1f" cy="%d" r="6" fill="none" stroke="%s" stroke-width="2.5"/><text x="%.1f" y="%d" class="ax" text-anchor="middle" fill="%s">%s</text>'
                     % (X(last["first_wet"]), y, REFC, X(last["first_wet"]), y + 20, REFC, odate(last["first_wet"])))
        med = fw[len(fw) // 2]
        s.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="2.5"/>' % (X(med), X(med), y - 10, y + 10, INK))
        a = st.get("amsr", {}).get(z, {})
        if a.get("first_wet"):
            o = offset(dt.date.fromisoformat(a["first_wet"]))
            s.append('<path d="M%.1f %d l7 9 l-7 9 l-7 -9 z" fill="%s"/>' % (X(o), y - 9, COL[z]))
            s.append('<text x="%.1f" y="%d" class="ax" text-anchor="middle" fill="%s">%s</text>' % (X(o), y - 12, COL[z], dshort(a["first_wet"])))
        elif a.get("latest"):
            o = offset(dt.date.fromisoformat(a["latest"]))
            if o >= xmin:
                s.append('<text x="%.1f" y="%d" class="ax" fill="%s">not yet wet (data to %s) &#8594;</text>' % (X(o) + 4, y + 4, COL[z], dshort(a["latest"])))
            else:
                s.append('<text x="%.1f" y="%d" class="ax" fill="%s">not yet wet (data to %s)</text>' % (X(xmin) + 2, y - 10, COL[z], dshort(a["latest"])))
    if xmin <= now <= xmax:
        s.append('<line x1="%.1f" x2="%.1f" y1="12" y2="%d" stroke="%s" stroke-dasharray="2 3"/><text x="%.1f" y="10" class="ax" text-anchor="middle">today</text>'
                 % (X(now), X(now), h - 26, INK, X(now)))
    s.append("</svg>")
    return "".join(s) + legend([("2002-25 seasons (one dot each)", MUTED, False), ("median", INK, False), ("last summer, 2025/26 (ring)", REFC, False),
                                ("this season", COL["A"], False)])


def wet_charts(st, clim):
    out, now = [], offset(today())
    for z in ("A", "B", "C"):
        c = clim["amsr"]["zones"][z]
        days = st.get("amsr", {}).get(z, {}).get("days", {})
        cur = sorted((offset(dt.date.fromisoformat(d)), v["frac"]) for d, v in days.items())
        band = ([(i, v) for i, v in enumerate(c["f10"]) if v is not None], [(i, v) for i, v in enumerate(c["f90"]) if v is not None], "#a5d8ff")
        out.append('<div class="mini"><div class="mt" style="color:%s">Zone %s</div>%s</div>' % (COL[z], z, svg_series(
            [(REFC, [(i, v) for i, v in enumerate((c.get("ref") or {}).get("frac") or []) if v is not None], False, False),
             (COL[z], cur, False, False), (MUTED, [(i, v) for i, v in enumerate(c["f50"]) if v is not None], True, False)],
            31, 135, [0, 0.5, 1], ylab="share wet", band=band, today_x=now, h=150, w=420, xstep=31)))
    return '<div class="minis">%s</div>' % "".join(out) + legend([("this season", COL["A"], False), ("last summer, 2025/26", REFC, False),
                                                                    ("2002-25 median", MUTED, True), ("2002-25, 10-90 %", "#a5d8ff", False)])


def radar_chart(st):
    """Per zone: Sentinel-1 (C-band, filled dots) and NISAR (L-band, open squares) change from October."""
    s1 = st.get("s1", {}).get("scenes", {})
    ni = st.get("nisar", {}).get("scenes", {})
    if not s1 and not ni:
        return ""
    now = offset(today())
    xmax = max(now + 3, 45)
    out = []
    for z in ("A", "B", "C"):
        p1 = sorted((offset(dt.date.fromisoformat(r["date"])), r["zones"][z]["change_db"]) for r in s1.values() if z in r.get("zones", {}))
        p2 = sorted((offset(dt.date.fromisoformat(r["date"])), r["zones"][z]["change_db"]) for r in ni.values() if z in r.get("zones", {}))
        svg = svg_series([(COL[z], p1, False, True)], 0, xmax, [-12, -6, -3, 0, 3], ylab="change from October, dB",
                         hlines=[(-3, "#1c7ed6", True, "-3 dB")], today_x=now, h=165, w=420, xstep=14)
        if p2:                                              # NISAR as open squares, drawn on the same axes
            pl, pr, pt, pb, w, h = 42, 12, 14, 28, 420, 165
            W, H = w - pl - pr, h - pt - pb
            sq = "".join('<rect x="%.1f" y="%.1f" width="7" height="7" fill="none" stroke="%s" stroke-width="1.8"/>'
                         % (pl + W * x / xmax - 3.5, pt + H * (1 - (min(max(y, -12), 3) + 12) / 15) - 3.5, INK) for x, y in p2)
            svg = svg.replace("</svg>", sq + "</svg>")
        out.append('<div class="mini"><div class="mt" style="color:%s">Zone %s</div>%s</div>' % (COL[z], z, svg))
    return ('<div class="minis">%s</div>' % "".join(out) +
            '<div class="legend"><span><i style="background:%s;width:8px;height:8px;border-radius:50%%"></i>Sentinel-1, C-band (surface; every few days)</span>'
            '<span><i style="background:none;border:2px solid %s;width:6px;height:6px"></i>NISAR, L-band (deeper; every 12 days, provisional)</span></div>' % (COL["A"], INK))
