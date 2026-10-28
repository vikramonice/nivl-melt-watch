# How the numbers on Nivl Melt Watch are made

The page reports measurements and how they compare with past seasons. It does not combine them into
a verdict. Below: every number, how it is computed, and its known limits.

## Zones
Made in the Nivl project (`code/python/melt/meltwatch_zones.py`) from the MINIS route
(`route_43d_maitri`), the Rignot et al. 2023 grounding line, the Nivlisen outline, AMSR melt-day
climatology and Tuckett et al. meltwater recurrence. Corridors are 2 km either side of the route.

## Passive microwave (AMSR2 wet snow)
- Product: Picard & Fily near-real-time wet/dry snow, 10 km, daily, from JAXA AMSR2
  ([Grenoble](https://snow.univ-grenoble-alpes.fr/melting/nrt-antarctic/)). The producers call the recent
  days experimental. About 10 days behind.
- A cell is wet on a day if the ascending or the descending pass is wet (filtered product).
- Zone cells: every cell whose centre lies within 5 km of a route corridor (A: 5 cells, B: 6), or inside
  a larger zone (C: 11, terminal lake: 1, rest of shelf: 63).
- First wet day: the first day with any zone cell wet. Climatology: 2002/03-2025/26 (2011/12 missing).
  Checked against known seasons: zone B first wet 8 Nov 2007, 21 Nov 2017, 7 Dec 2019, 10 Dec 2024,
  28 Nov 2025, the same dates as the project's site analysis.
- Limits: 10 km cells are larger than the zones; the product sees wet snow well but blue-ice ponds poorly.

## Sentinel-1 radar
- RTC gamma0, HH, from the Microsoft Planetary Computer; resampled to 100 m (EPSG:3031).
- Change = this scene minus the per-pixel median of October 2026 scenes from the same relative orbit
  (orbits 74, 93, 118). Zone means are taken in linear power, then converted to dB.
- "3 dB or more darker" is the common wet-snow mark (Nagler & Rott 2000). January melt on Nivlisen
  darkens the shelf by 5-10 dB (project analysis). Orbits without an October baseline are listed, not used.
- Limits: refrozen smooth ice is also dark; wind crusts and new snow change backscatter a little.

## Sentinel-2 / Landsat (open water)
- Only acquisitions with at least half of zone A cloud-free (Sentinel-2 SCL 8-10, Landsat QA cloud and
  cirrus bits). 60 m grid.
- Water: NDWI_ice = (blue - red) / (blue + red) > 0.25 (the project's lake mapping threshold) AND red at
  most half of the same pixel in October, both scaled by the scene's own snow brightness (where there is
  no October value: red below 0.45 x the scene's snow). The second test keeps blue ice out.
- Checked: no water on clear October scenes except up to 2 km² in zone A at low sun (18°, 4 Oct 2026);
  keeps 15.3 of 16.2 km² of mapped channel water on 28 Dec 2025.
- Limits: clouds; bright slush may be missed; values under about 2 km² in zone A are within the
  false-detection level.

## NISAR L-band radar
- GCOV HHHH (provisional), read as a window over HTTPS with an Earthdata user token (secret
  `EARTHDATA_TOKEN`, valid 60 days). Each track is compared with its own first October 2026 pass, so
  viewing geometry cancels (a track first seen later falls back to the October mosaic of its look
  direction). Same zone statistics as Sentinel-1.
- L-band reaches deeper than C-band. A thin wet surface layer darkens Sentinel-1 first; water or slush
  below a refrozen crust can keep NISAR dark after Sentinel-1 has recovered. The page shows both on one
  chart per zone for that comparison. Secondary signal: 12-day repeat, provisional data, no melt-season
  experience yet on Nivlisen.
- October 2026 check: route zones within -0.6 to +0.2 dB of the October mosaic (before per-track baselines).

## Stations
- Maitri (WMO 89514) and Novolazarevskaya (89512), both on rock in the Schirmacher Oasis.
- Daily max: NOAA GHCN-Daily TMAX where available, else the highest of the SYNOP temperatures and the
  reported 12-h maximum (section 333, group 1snTxTxTx). Daily mean: GHCN TAVG, else the mean of at least
  two SYNOP temperatures.
- Since 1 November: days with daily max above 0 °C; the current run of such days; positive degree days =
  sum of daily means above 0 °C (as in the project's analysis, where degree days follow AMSR melt days at
  r = 0.79 against 0.21 for counts of warm days).
- Snow: SYNOP present weather 22, 26, 70-79, 85-87 (snowfall); 36-39 (drifting or blowing snow).
- Climatology: GHCN 1990-2025 (Novolazarevskaya: 26 complete seasons; Maitri's record is too gappy
  for running totals, so only Novolazarevskaya has the comparison band).
- Limits: rock stations have about 60 % more days above 0 °C than the shelf (project analysis).

## Forecast
AMPS (Polar WRF, 8 km) from the MINIS weather site: C13 (grounding zone, in zone A), A12 (near zone B),
Maitri. Per day: max 2 m temperature, degree days on the daily mean, snowfall, max mean wind.

## Sea ice
University of Bremen AMSR2 ASI v5.4, 6.25 km: mean concentration of ocean pixels in three boxes in front
of the shelf (west, central, east). Context only.
