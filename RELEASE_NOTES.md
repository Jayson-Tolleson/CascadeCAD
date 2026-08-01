# CascadeCAD 1.0 Production (RX) Release Notes

CascadeCAD 1.0 Production (RX) hardens the extracted standalone tree into a maintainable production baseline without removing existing 0.7.x functionality.

## Highlights

- Package version is now `1.0.0`.
- Engineering units are centralized in `webcad_xbf.units` with support for inches, feet, feet + inches, yards, millimeters, centimeters, and meters.
- Numeric formula evaluation is provided by `webcad_xbf.formula` and supports arithmetic, `pi`, `e`, common math functions, and unit literals.
- Viewer preferences now expose rendering quality, triangle budget, project/display/export units, diagnostics, and lazy loading controls.
- The renderer prepares imported GLB scenes with frustum culling, triangle accounting, and budget-aware lazy hiding.
- A diagnostics overlay reports FPS, triangle count, GPU resource counts, CPU/heap availability, and draw calls.

## Compatibility

Existing CascadeCAD project geometry continues to use high-precision millimetre internal units. Display and export preferences are layered on top of that representation so older project data remains readable.

## Operational Notes

Use `scripts/validate.sh` as the primary source-tree validation check. The larger pytest suite still depends on optional CAD/runtime packages such as CadQuery/OCP in environments that run geometry integration tests.
