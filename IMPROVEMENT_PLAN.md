# CascadeCAD 0.7.0 — Production and Improvement Plan

## Release goal

Preserve the working XBF/CadQuery/Open CASCADE pipeline while making very large projects easier to edit, inspect, export, and discuss safely with project members and the wider opt-in CascadeCAD community. Geometry remains canonical in millimeters; the editor converts values for imperial or metric display.

## Implemented in 0.7.0 collaboration layer

- Persistent UUID users and random device-session tokens.
- Username uniqueness on one CascadeCAD server.
- Private project membership with Owner, Admin, Editor, Reviewer, and Viewer roles.
- Owner/Admin username invitations.
- Persistent project chat, direct messages, and global board messages.
- WebSocket delivery with REST history and posting endpoints.
- Project-chat links to selected component IDs.
- Available, Busy, and Invisible presence.
- Hidden, Category Only, and Public Showcase project disclosure modes.
- Public global board slow mode, length limits, 30-day retention, bounded history, reporting, muting, and blocking.
- Draggable collaboration toolbar and tabbed right sidebar.

### Required before broad commercial account launch

The UUID device session is a sound protocol foundation but not a complete customer identity product. Before storing outside customers' confidential CAD projects, add verified account authentication or SSO, token rotation/revocation, account recovery, CSRF review, administrative moderation, database migrations, PostgreSQL identity/chat storage, Redis presence/pub-sub for multiple web workers, storage quotas, billing entitlements, audit export, backups, and a privacy/retention policy.

## Implemented in 0.6.0

### Editor and layout

- User-facing product title changed to **CascadeCAD**.
- Two draggable toolbar rows begin with **Project** and **Share**, followed by **Edit**, **Solids**, **Draft**, **Boolean**, and **Inspect**.
- Toolbar order can be moved between rows, is stored locally, and can be reset from Preferences.
- Selection sidebar has separate Close and Clear Selection controls and can be reopened.
- A lower **Part Properties** panel appears when a part is highlighted.

### Written part parameters

- Editable part name.
- Position X/Y/Z.
- Orientation X/Y/Z in degrees.
- Scale X/Y/Z displayed to five decimal places.
- Persistent material name, density, color, and description.
- Multi-part material assignment.
- Spacebar toggles visibility of all selected parts.

### Units and preferences

- Starts in imperial IN/FT display mode.
- One-click imperial/metric toggle.
- Canonical geometry remains in millimeters to avoid repeated conversion drift.
- STEP export explicitly declares MM or INCH output units.
- Low, Medium, Good, and Exceptional viewer-resolution profiles.
- Independent Grid, Origin, and XYZ Axis checkboxes.
- OSnap mode preferences.

### Modeling and inspection

- Uniform and nonuniform Scale.
- Linear, rectangular, and polar linked arrays without duplicating the source at the origin.
- Round/Fillet and Chamfer using selected edge numbers.
- Additive and Subtractive Helix with pitch, height, radius, axis direction, starting angle, taper/cone angle, and handedness.
- Measure/Info endpoint with exact Open CASCADE values where B-rep geometry is available:
  - bounding-box X/Y/Z and diagonal;
  - volume and area;
  - edge length/perimeter;
  - radius and diameter values;
  - face/edge/vertex/solid counts;
  - center of mass;
  - minimum distance between two selected parts;
  - material-derived mass.
- OSnap foundation for origin, grid, centers, endpoints, and midpoints using cached component preview bounds.

### Large-model performance

- Viewer renders on demand rather than running an endless animation loop while idle.
- Continuous rendering occurs only during orbit or transform interaction.
- `preserveDrawingBuffer` is disabled during ordinary viewing; captures request a fresh frame.
- Preview cache invalidation uses the actual project revision instead of a timestamp on every request.
- Project polling is centralized to avoid overlapping refresh loops.
- Scene/component maps are retained instead of rebuilt for every minor state change.
- Assembly tree interactions use delegation rather than reconnecting every row handler.
- Revision snapshots try same-filesystem hard links first. Because masters are atomically replaced, this preserves the old XBF/GLB without copying a huge file; unsupported filesystems safely fall back to `copy2`.

### Packaging and regression safety

- Geometry/editor foundation originated in package version 0.6.0 and remains regression protected.
- The pinned Three.js vendor installer tries unpkg, jsDelivr, and the official GitHub tag in sequence.
- Python compilation, shell validation, JavaScript syntax checks, structural validation, and 46 automated tests pass in the build environment.

## Remaining hard architecture work

These items are intentionally not disguised as completed. They require testing on the real CadQuery/OCP server with the user's very large original XBF.

### Exact browser topology picking

The current Round/Chamfer interface accepts exact edge numbers obtained from Info. The next topology bridge should emit stable face/edge/vertex pick IDs beside each GLB preview so the user can click an exact edge directly. Stable IDs must be regenerated after every topology-changing operation and verified against the source XBF.

### Chunked component previews

The current exact master remains one `master.xbf`, and topology-changing operations still regenerate the complete overview GLB. The next performance phase should add:

- one low-detail preview per top-level component;
- progressive loading of visible components;
- per-component bounding-box manifest;
- changed-component-only preview regeneration;
- optional high-detail preview on selection;
- a deliberate **Commit XBF** step that rebuilds the monolithic interchange master.

This should be introduced behind a project-format version flag and tested against duplicate assemblies, nested placements, material colors, and mixed exact/faceted geometry before becoming the default.

### Source module split

`geometry.py` and `project.js` remain large because a blind rewrite would be riskier than the current working release. After native regression fixtures cover the new operations, split them into modeling, inspection, export, viewer, snapping, materials, units, and toolbar modules without changing routes or saved-project contracts.

## Native-server acceptance tests

Run these after installing on the CascadeCAD server where CadQuery 2.8, OCP, and FreeCAD are present:

1. Import the large original XBF and compare component count, names, placements, colors, and preview appearance.
2. Assign materials to one part and to a multi-selection; refresh and restart services; confirm persistence and mass.
3. Edit position, rotation, and scale from Part Properties; Commit XBF; reopen and verify exact values.
4. Test Spacebar hide/show before and after refresh.
5. Create each array type and confirm the original is not duplicated at the origin.
6. Fillet and chamfer known edge numbers on a box and cylinder.
7. Sweep additive and subtractive helices with cylindrical and tapered paths.
8. Export STEP once in MM and once in INCH and inspect the declared unit in FreeCAD.
9. Compare idle CPU/GPU use and interaction frame rate against 0.5.1.
10. Measure commit time and revision disk usage on the large original file; verify hard-linked revisions remain independently recoverable after atomic master replacement.
