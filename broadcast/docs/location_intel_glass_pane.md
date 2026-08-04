# Location Intel Glass Pane

This pass restores the developed zippy-style location intelligence pane while keeping the new PostGIS/live `/gfs` architecture.

## Contract

A click on a green location orb opens the glass `Location Intel` pane. The pane now combines:

- original `fishloclist.csv` / zippy report fields
- full `report_#` note timeline
- PostGIS spatial source diagnostics
- nearest waterbody/harbor context
- nearest live ocean sample when available: bait score, current vector, SST
- nearest live atmosphere sample when available: clouds, rain, wind, cloud family
- marine mask classification from the backend

## Important PostGIS behavior

The report loader now prefers:

```text
data/fishloclist.csv
```

and falls back to:

```text
data/reports.csv
```

PostGIS `spatial_reports.properties` stores the full `ReportPoint` JSON so the frontend receives `csv_fields`, `report_indices`, and `marine_mask`, not just title/summary/coordinates.

## Frontend behavior

The pane remains quiet by default. It opens only when a location orb or shark-intel marker is selected.

The pane is not a debug log. It is a user-facing fishing/location intelligence HUD.

