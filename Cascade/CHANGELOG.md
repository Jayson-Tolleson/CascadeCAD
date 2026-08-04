
## 0.7.1 Large-Model Production

- Raised the default guarded faceted conversion/export ceiling to 5,000,000 triangles.
- Added a safe installer migration from the former stock 750,000 value while preserving administrator customizations.
- Documented all preview, queue, timeout, cache, memory and fallback controls.
- Expanded server diagnostics to report effective large-model settings.
# CascadeCAD 0.7.0

## UUID collaboration

- Adds typed CascadeCAD usernames backed by persistent `usr_...` UUIDs and hashed device-session tokens.
- Adds Available, Busy, and Invisible presence modes.
- Adds Hidden, Category Only, and Public Showcase controls for the active project label.
- Keeps hidden and category-only project UUIDs and names out of the global user response.

## Project users and chat

- The first collaboration user on a project claims Owner membership.
- Owners and Admins can invite a typed username as Admin, Editor, Reviewer, or Viewer.
- Adds persistent private Project Chat with WebSocket updates.
- Project-chat messages can link selected component IDs and reselect those parts from the message.

## Community and direct messages

- Adds a global active-user list with privacy-safe project labels.
- Adds persistent private Direct Messages.
- Adds a public text-only Global Broadcast Board with eight-second slow mode, a 500-character limit, 30-day retention, bounded history, reports, mute/block controls, and no project/file permissions.
- Adds conservative warning copy to the global composer.

## Editor integration

- Adds a draggable Community toolbar with Users, Project Chat, and Global Board buttons.
- Converts the right editor sidebar into Selection, Users, Project Chat, Global, and Direct tabs.
- Adds a user/privacy dialog and unread collaboration badge.
- Keeps the original Selection and FCInfo tools intact.

## Production boundary

- The release intentionally labels its login as a UUID device-session foundation, not a password or enterprise authentication system.
- A commercial public deployment should connect the protocol to verified accounts, PostgreSQL, Redis presence, token rotation, recovery, abuse administration, and TLS.

# CascadeCAD 0.6.0

## Editor, inspection, materials, and large-model performance

- Renamed the user-facing application to **CascadeCAD** throughout the UI, installer messages, diagnostics, generated comments, and documentation.
- Added two draggable toolbar rows beginning with **Project** and **Share**, followed by **Edit**, **Solids**, **Draft**, **Boolean**, and **Inspect**. Toolbar placement is saved in the browser and can be reset from Preferences.
- Added persistent imperial/metric display preferences while keeping canonical geometry in millimeters. STEP export explicitly writes millimeter or inch units.
- Added resolution profiles, render-on-demand, independent grid/origin/axis controls, and revision-based preview caching for large projects.
- Added persistent part visibility with **Spacebar** hide/show, a closable Selection panel, and a lower **Part Properties** editor for name, XYZ position, XYZ rotation, five-decimal XYZ scale, material, density, and color.
- Added uniform/nonuniform scale support, linked linear/rectangular/polar arrays, OSnap foundation, measurement tools, and an FCInfo-style exact geometry report.
- Added persistent per-part materials and color, material-derived mass, exact bounding-box/area/volume/edge properties, and multi-selection totals.
- Added selected-edge Round/Fillet and Chamfer operations plus additive and subtractive helical sweeps.
- Centralized project refresh polling and reduced repeated scene traversal/tree rebuilding.

# CascadeCAD 0.5.1

## STEP hard-speed smoke-contract correction

- Recognizes native AP242 B-rep solids created from mesh by the hard-speed OCP converter as preserved mesh-origin geometry.
- Stops requiring AP242 tessellated entities after triangulation-only XBF faces have already been replaced with faceted Part solids.
- Reports `mesh_representation=faceted-solid-brep` plus original triangle and converted solid/shell provenance in STEP export reports.
- Prevents the installer from printing a false "Mixed STEP smoke test omitted geometry" warning when the file contains validated `MANIFOLD_SOLID_BREP` geometry.

## CSG closed-shell topology and winding repair

- Splits each component mesh into edge-connected shells before writing OpenSCAD `polyhedron()` objects.
- Writes every disconnected closed shell as a separate top-level solid instead of forcing unrelated shells into one invalid `Part.Solid`.
- Welds identical vertices, removes duplicate and degenerate triangles, and repairs neighboring triangle winding.
- Enforces OpenSCAD clockwise-from-outside face order and rejects open, non-manifold, non-orientable, or zero-volume shells with component-specific diagnostics.
- Strengthens the native FreeCAD validator to require one valid nonzero-volume Part solid per exported polyhedron.
- Documents that FreeCAD's `WORD` and `DOT` unused-token notices are parser warnings rather than CSG geometry failures.

## 0.5.1 hard-speed faceted conversion

- Replaces the normal STL/FreeCAD mesh conversion path with direct `BRepBuilderAPI_MakeShapeOnMesh` component workers.
- Runs independent unique components in isolated CPU- and memory-bounded subprocesses; defaults to two active workers and a 60-slot queue.
- Adds persistent geometry-hash BREP caching and repeated-instance reuse.
- Adds NumPy vertex welding for compatibility paths.
- Adds optional same-domain face unification for editing-optimized output.
- Adds **Fast render (FastSewing)** beside Export and tessellation conversion; it enables `BRepBuilderAPI_FastSewing` and skips optional unification.
- Retains standard sewing and FreeCAD as progressively safer fallbacks.
- Adds conversion timing, throughput, worker, cache-hit, and backend reporting plus a native tetrahedron solid smoke test.

## 0.5.1 advanced modeling and upload workflow

- Retitled the upload page around making faceted B-rep solids from mesh files and mesh assemblies.
- Added Cone, Extrude, Revolve, Cross Sections, Sweep, and Loft to the Solids toolbar.
- Added a Draft toolbar with Line, B-spline, Polyline, Circle, Square/Rectangle, regular polygon, and Ellipse.
- Added exact Open CASCADE profile/path handling for the new operations.

# CascadeCAD 0.5.1

## Square capture and social-share toolbar

- Adds a separate Share toolbar with Draw square, Photo, Record 60s, Stop, Preview, Bluesky, Instagram, Download, and Clear controls.
- Captures only the selected square from the WebGL CAD canvas rather than recording browser menus or the entire page.
- Produces metadata-free 1080-square JPEGs and limits recordings to 60 seconds at a bounded bitrate.
- Adds a Quart media-normalization route and Debian FFmpeg dependency so Firefox/Chrome WebM recordings become H.264 `yuv420p` MP4 files suitable for social upload.
- Uses the native file share sheet on supported phones/tablets; desktop fallback downloads the file and opens Bluesky compose or Instagram.
- Adds a caption/preview dialog and 24-hour cleanup for temporary prepared media.

## Editor faceted-XBF conversion

- Adds **Convert to Tessellated (Faceted) Solids** beside Export.
- Converts every triangulation-only XBF component into faceted B-rep Part geometry before rewriting `master.xbf`.
- Preserves exact B-rep components, turns closed shells into solids, and retains unavoidable open shells in compounds.
- Applies and commits current working editor changes, creates a revision snapshot, rewrites XBF atomically, and regenerates the GLB preview.
- Verifies that the committed XBF contains zero triangulation-only face remnants.
- Clears stale exports after conversion so later XBF, STEP, BREP, and FCStd files are regenerated from the converted assembly.
- Adds cancellable worker progress, editor summary reporting, health capability advertising, smoke coverage, and a post-conversion STEP check.

## FreeCAD console-stdin execution fix

- Starts `FreeCADCmd` in console mode and executes the conversion helper through a `runpy` bootstrap sent over standard input.
- Fixes Debian FreeCAD 1.0 runs that printed only the startup banner, exited successfully, and never executed a helper supplied as a filename.
- Keeps manifest, output, report, progress, format, and tolerance values in environment variables rather than exposing them to FreeCAD's command-line file parser.
- Applies the same console-stdin contract to the native CSG import validator.
- Reports explicitly when the helper was sent through console stdin but did not produce its validation report.

## FreeCAD helper invocation and installer recovery fix

- Passes BREP/FCStd helper inputs through environment variables instead of ordinary trailing FreeCAD arguments.
- Prevents FreeCAD 1.x from treating manifest, output, report, progress, format, and tolerance values as additional files and exiting without a validation report.
- Includes the FreeCAD process exit value and captured log tail when a report is missing.
- Sets `FREECAD_USER_HOME` for the headless conversion process.
- Clears stale systemd `start-limit-hit` state during upgrades and prints service status plus journal diagnostics when startup genuinely fails.

## Mixed faceted component preservation fix

- Preserves open or invalid shells when another disconnected shell in the same mesh component successfully becomes a solid.
- Reports these components as `faceted-mixed-solid-shell` instead of incorrectly reporting the whole component as only a solid.
- Uses the source watertight flag only when FreeCAD cannot determine closure; it no longer overrides a known-open shell.
- Reports retained open-shell and mixed-component counts in BREP and FCStd export summaries.
- Explicitly reports when a component containing both exact and triangulated faces is wholly faceted to avoid duplicated subfaces.

## FreeCAD CSG parser compatibility fix

- Removes trailing commas after the final `points` and `faces` entries in every `polyhedron()`.
- Prevents FreeCAD's OpenSCAD CSG parser from opening an empty document when it rejects the final face-list comma.
- Adds a regression test for canonical polyhedron list termination.

## FreeCAD command-line compatibility fix

- Passes the faceted-conversion tolerance as a positional helper argument instead of `--tolerance`.
- Prevents Debian FreeCADCmd from intercepting the helper option and aborting BREP and FCStd exports before conversion starts.

## Corrected BREP export

- Replaces direct serialization of triangulation-only XBF containers with a validated headless FreeCAD Part conversion path.
- Converts closed mesh components to faceted B-rep solids and open mesh components to faceted B-rep shells.
- Reopens the completed BREP and requires actual faces before download.
- Rejects zero-byte, implausibly small, and geometry-free BREP files.
- Preserves pure exact components as exact B-rep.

## Corrected FCStd export

- Removes the old `Mesh::Feature` fallback.
- Creates one named `Part::Feature` per assembly component inside a root `App::Part`.
- Converts closed mesh components to faceted Part solids.
- Keeps unclosed components as explicitly reported faceted Part shells.
- Reopens the saved FCStd and rejects it if no Part faces are present or any mesh objects remain.

## Corrected CSG parts

- Removes the single root `group()` that could collapse the import into one root object.
- Emits one top-level OpenSCAD `polyhedron()` per component.
- Adds machine-readable `CASCADE_CAD_PART` comments carrying the original name and component ID.
- Adds a native FreeCAD CSG smoke validator that checks separate imported Part objects.

## Diagnostics and UI

- Export summaries now show BREP/FCStd solid, shell, and component counts.
- CSG summaries show separate part and triangle counts.
- BREP and FCStd share live component conversion progress, cancellation, timeout, and triangle guards.
- Installer export smoke tests now exercise a closed mesh tetrahedron through BREP and FCStd solid conversion.

# CascadeCAD 0.5.0

## Unified exports

- Replaced separate export/download controls with one Export control.
- Added XBF, STEP, CSG, BREP, and FCStd choices.
- Added automatic download when a background export completes.
- Added selected-component export scope.

## Long STEP jobs

- Added live faceted-STEP triangle progress, ETA, cancellation, and timeout.

## Responsive editor

- Added wrapping responsive tool groups and Light, Dark, and System themes.

## 0.7.2 — Native FCStd Import

- Adds `.FCStd` to first-class upload/import types.
- Routes FCStd through an isolated headless FreeCAD console worker, never through Trimesh.
- Opens and optionally recomputes the document, extracts final shape-bearing objects as exact BREP, and packs them into CascadeCAD XBF.
- Avoids duplicate Part Design history by importing the final `PartDesign::Body` result instead of every intermediate feature.
- Preserves FreeCAD object name, label, type, visible state, display color, and readable source properties in component metadata.
- Keeps the original FCStd under the project source directory.
- Adds import controls for timeout, recompute, and hidden-object inclusion.
- Raises the automated suite to 49 passing tests.

## CascadeCAD 1.0.0 Production (RX)

- Promoted the source tree package metadata to 1.0.0 for the Production (RX) baseline.
- Added a reusable engineering-unit module so project, display, and export units can be represented independently while preserving millimetre-based internal geometry.
- Added a safe formula evaluator for numeric CAD fields with arithmetic, constants, supported functions, exponentiation, and mixed unit literals such as `6' + 25 mm`.
- Extended frontend preferences with rendering quality, selectable 5M/10M/25M/50M triangle budgets, independent project/display/export units, diagnostics overlay control, and lazy mesh hiding for over-budget previews.
- Added renderer diagnostics for FPS, triangle count, GPU geometry/texture counters, browser heap availability, and draw calls.
- Added frustum-culling defaults and budget-aware model preparation as the first production rendering modernization layer.
- Added release notes and a production TODO register for intentionally deferred high-risk features.
