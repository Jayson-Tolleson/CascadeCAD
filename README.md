# CascadeCAD 0.6.0

## Square capture and social sharing

The editor includes a separate **Share** toolbar:

- **Draw square** places a square crop directly over the Three.js CAD viewer.
- **Photo** creates a metadata-free, social-ready JPEG at up to 1080 × 1080.
- **Record 60s** records only that square for up to one minute, without microphone audio.
- Browser WebM recordings are normalized by the server to H.264/AAC-free MP4 (`yuv420p`, fast-start) with FFmpeg for broad Instagram and Bluesky compatibility.
- **Bluesky** and **Instagram** attach the captured file through the browser/operating-system share sheet when file sharing is supported.
- On desktop browsers without file sharing, CascadeCAD downloads the media and opens the selected platform. Bluesky compose receives the caption; the user attaches the downloaded file before posting.
- Temporary normalized JPG/MP4 captures expire from project storage after 24 hours.

The browser cannot force the operating-system share sheet to choose a particular installed app. Direct unattended Instagram publishing also requires Meta professional-account OAuth and app review, so this toolbar keeps the user in control of the final post.

CascadeCAD is a Python 3 Quart browser CAD editor built on CadQuery and Open CASCADE. XBF is the native project format; Three.js renders GLB previews locally in the browser.

## CascadeCAD 0.6 editor additions

- Draggable two-row toolbars with Project, Share, Edit, Solids, Draft, Boolean, and Inspect groups.
- Imperial/metric display and STEP export units.
- Resolution profiles plus Grid, Origin, and XYZ-axis preferences.
- Written Part Properties for name, position, rotation, five-decimal scale, material, density, and color.
- Spacebar hide/show, linked arrays, scale, OSnap foundation, Measure, and FCInfo-style Info.
- Exact Round/Fillet, Chamfer, Additive Helix, and Subtractive Helix operations.
- Render-on-demand and hard-linked revision snapshots to reduce large-project overhead.

See `IMPROVEMENT_PLAN.md` for implemented details, native-server acceptance tests, and the remaining chunked-preview/topology-picking architecture.

## Faceted-solid conversion

Beside **Export**, the editor now has **Convert to Tessellated (Faceted) Solids**. It rewrites the working XBF assembly itself rather than only changing one downloaded export:

- exact B-rep components remain exact;
- closed triangulated shells become faceted B-rep solids;
- unavoidable open or invalid shells remain faceted B-rep shells instead of being discarded;
- mixed exact-and-mesh components are converted wholly to faceted B-rep so subfaces are not duplicated;
- a revision snapshot is created before `master.xbf` is replaced;
- unsaved working transforms and visibility changes are included and committed;
- the GLB preview is regenerated and the rewritten XBF is validated to contain zero triangulation-only face remnants.

After conversion, XBF stores Part/B-rep geometry and STEP, BREP, and FCStd exports use that converted geometry without repeating the mesh-remnant fallback. This is faceted solid/shell geometry, not recovered sketches or analytic feature history.

## Hard-speed faceted conversion

Mesh-backed components now use a direct Open CASCADE conversion path before the FreeCAD compatibility fallback:

- indexed XBF triangles are sent directly to `BRepBuilderAPI_MakeShapeOnMesh`;
- independent unique components run in isolated subprocesses with a CPU- and memory-bounded worker count;
- the default 2-vCPU deployment runs two active conversion workers and uses a bounded 60-slot scheduler;
- repeated components share one geometry conversion;
- converted component BREPs are cached persistently by geometry, tolerance, and conversion mode;
- NumPy performs fallback vertex welding without per-vertex Python dictionaries;
- closed shells become solids, while open shells remain present;
- conservative same-domain unification reduces coplanar facet counts in normal mode;
- **Fast render (FastSewing)** uses `BRepBuilderAPI_FastSewing` and skips the optional unification pass for the quickest conversion.

The checkbox applies both to **Convert to Tessellated (Faceted) Solids** and to STEP, BREP, and FCStd exports that still contain mesh-backed components. A failed direct component conversion automatically falls back to the existing isolated FreeCAD path when enabled.

## Export control

The editor has one Export control with these formats:

- **XBF** — native CascadeCAD/Open CASCADE assembly storage.
- **STEP** — exact B-rep when available; guarded planar-facet fallback for mesh-only XBF components.
- **CSG** — OpenSCAD-compatible solid text with one validated top-level `polyhedron()` per closed connected shell. Disconnected solids are split; open or non-manifold shells are rejected rather than rendered as misleading strips.
- **BREP** — validated Open CASCADE Part geometry. Closed mesh shells become faceted solids, open shells remain faceted shells, and components containing both preserve both.
- **FCStd** — a headless FreeCAD document containing named `Part::Feature` objects. Closed mesh shells become faceted solids, open shells remain faceted shells, mixed solid/shell components preserve both, and no `Mesh::Feature` objects are written.

Check **Selected** to export only highlighted components. The finished file downloads automatically; there is no separate download button.

### Important geometry distinction

The BREP and FCStd corrections create **faceted B-rep Part geometry** from triangles. They do not infer analytic cylinders, planes, fillets, sketches, or original parametric feature history. A component containing both exact B-rep faces and triangulation-only faces is exported entirely as faceted geometry so its subfaces are not duplicated. Analytic mechanical reconstruction remains a later feature.

## Corrected BREP, FCStd, and CSG behavior

- BREP and STEP use the direct cached OCP faceted conversion path when mesh-backed components remain; FCStd receives those converted Part shapes through the headless FreeCAD document writer.
- The launcher starts FreeCAD in console mode, sends a tiny `runpy` bootstrap through standard input, and passes conversion paths and tolerance through environment variables. This avoids FreeCAD 1.x both treating helper values as input files and silently ignoring the helper script.
- A zero-byte or geometry-free BREP is rejected.
- FCStd output is rejected if validation finds any `Mesh::Feature` objects.
- FCStd keeps each assembly component as a separately named `Part::Feature` inside a root `App::Part` assembly. A single component may contain a compound of closed solids and retained open shells.
- CSG no longer wraps every component in one root `group()`. Each disconnected closed shell is emitted as its own top-level polyhedron so FreeCAD creates one valid Part solid per shell.
- The CSG topology pass welds identical vertices, removes degenerate/duplicate facets, splits disconnected shells, makes neighboring triangle winding consistent, verifies every edge is shared by exactly two faces, and writes OpenSCAD's clockwise-from-outside winding.
- Open, non-manifold, non-orientable, or zero-volume shells stop the export with component-specific diagnostics instead of producing belt/strip-shaped geometry.
- CSG omits trailing commas after the final point and face so FreeCAD's stricter OpenSCAD parser does not create an empty document.
- CSG includes `CASCADE_CAD_PART` metadata comments with the original component name, ID, and shell number. FreeCAD may still assign generic internal object names during CSG import.
- FreeCAD 1.0 may display lexer notices that `WORD` and `DOT` are unused tokens; those notices come from FreeCAD's OpenSCAD parser and are not geometry errors.

## Export limits and cancellation

The same guarded faceted-geometry limit used by STEP is applied to BREP and FCStd mesh-to-Part conversion:

```ini
CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES=750000
CASCADE_CAD_STEP_EXPORT_TIMEOUT_SECONDS=3600
CASCADE_CAD_FACETED_STEP_CHUNK_TRIANGLES=1000
CASCADE_CAD_MAX_CSG_TRIANGLES=10000000
CASCADE_CAD_FACETED_WORKERS=2
CASCADE_CAD_FACETED_QUEUE_DEPTH=60
CASCADE_CAD_FACETED_MEMORY_BUDGET_GB=10
CASCADE_CAD_FACETED_CACHE_ENABLED=1
CASCADE_CAD_FACETED_CACHE_MAX_BYTES=21474836480
CASCADE_CAD_FACETED_DIRECT_OCP=1
CASCADE_CAD_FACETED_FREECAD_FALLBACK=1
CASCADE_CAD_FACETED_UNIFY_SAME_DOMAIN=1
```

Do not raise the faceted solid limit to several million triangles on a 16 GB server. Prefer selected-component export.

## Install or upgrade

```bash
cd ~
rm -rf CascadeCAD
unzip CascadeCAD.zip
cd CascadeCAD
sudo bash install.sh
```

Existing projects under `/var/lib/cascade-cad` are preserved. The installer installs Debian `freecad-python3` and `ffmpeg`, then runs native BREP, FCStd, CSG, STEP, XBF, combine, and modeling smoke checks.

```bash
sudo systemctl restart cascade-cad cascade-cad-worker
sudo nginx -t && sudo systemctl reload nginx
```

Open `https://lftr.biz/cascade-cad/` and force-refresh once after upgrade.

## Health check

```bash
curl -sS https://lftr.biz/cascade-cad/healthz | python3 -m json.tool
```

The response advertises `validated_brep_export`, `part_based_fcstd_export`, `csg_separate_parts`, `faceted_xbf_conversion`, `hard_speed_faceted_conversion`, `fast_sewing`, `square_capture_share`, `automatic_downloads`, and `cancellable_exports`.

## Mesh-to-solids assembly workflow

The upload page is centered on one job: **make solid(s) from mesh—even in assemblies**. Mesh files and mesh assemblies are first preserved without decimation inside XBF. In the editor, **Convert to Tessellated (Faceted) Solids** replaces closed triangulated shells with genuine faceted Open CASCADE B-rep solids while retaining unavoidable open shells and preserving exact assembly parts.

The editor also includes:

- Solid tools: Cone, Extrude, Revolve, Cross Sections, Sweep, and Loft.
- Draft tools: Line, B-spline, Polyline, Circle, Square/Rectangle, regular N-side polygon, and Ellipse.

Closed draft profiles are stored as exact planar faces so they remain visible in the browser preview and can be consumed by Extrude, Revolve, Sweep, and Loft. Open lines, B-splines, and polylines are stored as exact edges/wires.
