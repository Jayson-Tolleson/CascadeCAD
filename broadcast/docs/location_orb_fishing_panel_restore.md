# Location orb / fishing panel restore

The Locations pill now draws both layers at each fishing report:

1. true Google 3D stacked green cylinder/glow polygons for the visible orb body;
2. the old zippy green `gmp-marker-3d-interactive` orb above it as the reliable click target.

This fixes the fishing Location Intel pane opening problem on browsers where polygon hit-testing is unreliable.
The marker uses the original green orb SVG/glyph style and calls `pane.selectReport(report, buildLocationIntelContext(report))`, so the glass panel receives CSV/PostGIS fields plus nearest ocean/atmosphere intel.
