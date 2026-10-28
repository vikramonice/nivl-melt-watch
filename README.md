# Nivl Melt Watch

Melt signals for the MINIS return route on Nivlisen (Dronning Maud Land, Antarctica), from satellites
and stations, updated automatically on GitHub Pages:

**https://vikramonice.github.io/nivl-melt-watch/** · plain text: [status.txt](https://vikramonice.github.io/nivl-melt-watch/status.txt)

The page follows one question: is the 43D-Maitri route still passable where it leaves the shelf? Melt
starts at the grounding line, so the page focuses on three zones (static/zones.geojson):

| Zone | Where | Why |
|---|---|---|
| A | route across the grounding line, km 24-60 from Depot 43D (crossing at km 31) | where the route leaves the shelf; highest melt-day count on the route (36-37 days/yr) |
| B | route km 60-100, grounded blue ice before Maitri | recurrent ponds (Landsat water in up to 12 of 16 seasons) |
| C | grounding zone within 15 km of zone A | where melt usually shows first (early warning) |

Context: terminal lake, rest of the shelf, sea ice in front of the shelf.

It shows information, not decisions: numbers, dates, images and how this season compares with past ones.
Every metric and threshold, with its source: [RULES.md](RULES.md).

## Sources
- AMSR2 wet snow (Picard & Fily NRT product, Grenoble), 10 km, daily (about 10 days behind)
- Sentinel-1 radar (Planetary Computer, anonymous), every few days
- Sentinel-2 / Landsat (Planetary Computer), clear days only
- NISAR L-band (ASF DAAC; repository secret `EARTHDATA_TOKEN`, an Earthdata user token valid 60 days), 12-day repeat, provisional
- Maitri and Novolazarevskaya: Ogimet SYNOP (6-hourly) and NOAA GHCN-Daily
- AMPS forecast, taken from the [MINIS weather site](https://vikramonice.github.io/minis-weather/)
- Sea ice: University of Bremen AMSR2 ASI, daily

## How it updates
`.github/workflows/update.yml`: all sources daily at 06:07 UTC; station reports at 01:17, 07:17, 13:17 and
19:17 UTC. `publish.py` reads the season so far from the `gh-pages` branch (`season.json`), adds new data,
rebuilds the page and force-pushes `gh-pages` as a single commit when something changed. Run by hand from
the Actions tab (mode `full`, `stations` or `rebuild`). Updates stop after February 2027 (`SEASON_END` in
`melt/common.py`); a monthly keep-alive keeps the schedule running.

Static inputs (`static/`) come from the Nivl project: zones and map from `code/python/melt/meltwatch_zones.py`,
climatology from `meltwatch_climatology.py`; Sentinel-1 and optical October references from
`python -m melt.s1 --baseline` and `python -m melt.optical --reference`; NISAR references from
`python -m melt.nisar --baseline <Nivl folder>`.
