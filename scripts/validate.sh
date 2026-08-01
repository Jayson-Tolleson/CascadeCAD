#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m compileall -q "$ROOT/webcad_xbf" "$ROOT/tests"
for file in "$ROOT"/*.sh "$ROOT"/scripts/*.sh; do bash -n "$file"; done
if command -v node >/dev/null 2>&1; then
  node --check "$ROOT/webcad_xbf/static/js/index.js"
  node --check "$ROOT/webcad_xbf/static/js/project.js"
  node --check "$ROOT/webcad_xbf/static/js/share-capture.js"
  node --check "$ROOT/webcad_xbf/static/js/collaboration.js"
fi
python3 - <<'PY' "$ROOT"
from pathlib import Path
import sys
root = Path(sys.argv[1])
required = [
    'pyproject.toml',
    'install.sh',
    'webcad_xbf/app.py',
    'webcad_xbf/geometry.py',
    'webcad_xbf/mesh_cleanup.py',
    'webcad_xbf/templates/index.html',
    'webcad_xbf/static/js/share-capture.js',
    'webcad_xbf/share_media.py',
    'webcad_xbf/collaboration.py',
    'webcad_xbf/static/js/collaboration.js',
    'deploy/systemd/cascade-cad.service',
    'deploy/systemd/cascade-cad-worker.service',
    'deploy/nginx/cascade-cad-location.conf',
    'scripts/check_runtime.py',
    'scripts/check_combine.py',
    'scripts/check_modeling.py',
    'scripts/check_step_export.py',
    'scripts/check_export_suite.py',
    'scripts/freecad_faceted_export.py',
    'scripts/freecad_import_fcstd.py',
    'webcad_xbf/faceted_worker.py',
    'scripts/check_hard_speed.py',
    'scripts/freecad_validate_csg.py',
    'webcad_xbf/maintenance.py',
    'scripts/diagnose_server.sh',
]
missing = [name for name in required if not (root / name).exists()]
if missing:
    raise SystemExit(f'Missing: {missing}')
nginx = (root / 'deploy/nginx/cascade-cad-location.conf').read_text()
if 'proxy_pass http://127.0.0.1:8790;' not in nginx:
    raise SystemExit('nginx proxy_pass must preserve the /cascade-cad prefix')
if 'proxy_pass http://127.0.0.1:8790/;' in nginx:
    raise SystemExit('nginx proxy_pass must not have a trailing slash')

pyproject = (root / 'pyproject.toml').read_text()
if 'networkx>=3.4,<4' not in pyproject:
    raise SystemExit('networkx must be an explicit runtime dependency')
if 'version = "1.0.0"' not in pyproject:
    raise SystemExit('package version must be 1.0.0')
geometry = (root / 'webcad_xbf/geometry.py').read_text()
for token in ('toCAF(assembly, True, False)', '_faceted_step_fallback', 'planar-triangle-brep', 'CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES'):
    if token not in geometry and token not in (root / 'env.example').read_text():
        raise SystemExit(f'missing robust STEP export feature: {token}')
if 'toCAF(assembly, True, True' in geometry:
    raise SystemExit('STEP exporter must not remesh triangulation-only XBF faces')
if 'freecad-python3' not in (root / 'install.sh').read_text():
    raise SystemExit('installer must provide headless FreeCAD for FCStd export')
fcstd_helper = (root / 'scripts/freecad_import_fcstd.py').read_text()
for token in ('App.openDocument', 'PartDesign::Feature', 'exportBrep'):
    if token not in fcstd_helper:
        raise SystemExit(f'missing native FCStd import feature: {token}')
if '.fcstd' not in (root / 'webcad_xbf/store.py').read_text().lower():
    raise SystemExit('FCStd must be accepted by the upload store')
if 'ffmpeg' not in (root / 'install.sh').read_text():
    raise SystemExit('installer must provide FFmpeg for social MP4 normalization')
worker_unit = (root / 'deploy/systemd/cascade-cad-worker.service').read_text()
if 'scripts/check_runtime.py --quiet' not in worker_unit:
    raise SystemExit('worker service must run geometry runtime preflight')
for token in ('MemoryMax=12G', 'OOMPolicy=continue', 'Restart=always'):
    if token not in worker_unit:
        raise SystemExit(f'worker resilience setting missing: {token}')

vendor = (root / 'scripts/vendor_frontend.sh').read_text()
for dependency in ('three.core.js', 'three.module.js', 'TransformControls.js', 'GLTFLoader.js', 'BufferGeometryUtils.js'):
    if dependency not in vendor:
        raise SystemExit(f'frontend vendor script must install {dependency}')
project_js = (root / 'webcad_xbf/static/js/project.js').read_text()
for token in ('TransformControls', 'Raycaster', 'initShareCapture', 'preserveDrawingBuffer: false', '/editor/commit', '/combine', 'combine-dialog', '/model', 'primitive-tool', 'solid-operation-tool', 'draft-tool', 'MODEL_SCHEMAS', 'cross_section', 'sweep', 'loft', 'tool-fuse', 'tool-subtract', 'tool-facebinder', '/api/projects/${projectId}/export', 'export-format', 'export-button', 'cancel-job', 'component_ids', 'theme-select', 'THEME_KEY'):
    if token not in project_js:
        raise SystemExit(f'missing editor browser feature: {token}')

for js_name in ('webcad_xbf/static/js/index.js', 'webcad_xbf/static/js/project.js', 'webcad_xbf/static/js/share-capture.js', 'webcad_xbf/static/js/collaboration.js'):
    js = (root / js_name).read_text()
    forbidden = ["fetch('/api", 'fetch("/api', 'location.href = `/project', '${location.host}/ws/']
    found = [token for token in forbidden if token in js]
    if found:
        raise SystemExit(f'Unprefixed browser routes in {js_name}: {found}')
index_js = (root / 'webcad_xbf/static/js/index.js').read_text()
for token in ('delete-project', "method: 'DELETE'", 'project-row.selected', 'ACTIVE_JOB_KEY', 'Server connection interrupted', 'mesh_cleanup', 'mesh-cleanup'):
    if token not in index_js:
        raise SystemExit(f'missing project deletion feature: {token}')
cleanup = (root / 'webcad_xbf/mesh_cleanup.py').read_text()
for token in ('removed_coincident_objects', 'clean_3mf', 'clean_generic_mesh'):
    if token not in cleanup:
        raise SystemExit(f'missing mesh cleanup feature: {token}')
app = (root / 'webcad_xbf/app.py').read_text()
for token in ('mesh_cleanup', '/model', 'solid_toolbars', 'square_capture_share', '/share-media/normalize', 'step_ap242_export', 'export_formats', 'cancellable_exports', 'faceted_xbf_conversion', '/convert/faceted-solids', 'register_collaboration_routes', 'global_broadcast_board'):
    if token not in app:
        raise SystemExit(f'missing app feature: {token}')
geometry = (root / 'webcad_xbf/geometry.py').read_text()
for token in ('write.step.tessellated', 'AP242DIS', '_validate_step_output', '_step_report_preserves_mesh_source', 'TRIANGULATED_FACE', '_faceted_step_fallback', 'planar-triangle-brep', 'faceted-solid-brep', 'export_project_file', 'export_csg', 'export_brep', 'export_fcstd', 'convert_to_faceted_solids', '_prepare_freecad_conversion_manifest'):
    if token not in geometry:
        raise SystemExit(f'missing STEP AP242 export feature: {token}')
for token in ('_run_hard_speed_parts_conversion', '_mesh_cache_key', 'geometry-cache', 'faceted_worker', 'OMP_NUM_THREADS'):
    if token not in geometry:
        raise SystemExit(f'missing hard-speed faceted conversion feature: {token}')
faceted_worker = (root / 'webcad_xbf/faceted_worker.py').read_text()
for token in ('BRepBuilderAPI_MakeShapeOnMesh', 'BRepBuilderAPI_FastSewing', 'BRepBuilderAPI_Sewing', 'ShapeUpgrade_UnifySameDomain', 'cq.Solid.makeSolid'):
    if token not in faceted_worker:
        raise SystemExit(f'missing direct OCP faceted converter feature: {token}')
for token in ('CASCADE_CAD_FACETED_WORKERS', 'CASCADE_CAD_FACETED_QUEUE_DEPTH', 'CASCADE_CAD_FACETED_CACHE_ENABLED', 'CASCADE_CAD_FACETED_DIRECT_OCP'):
    if token not in (root / 'webcad_xbf/config.py').read_text():
        raise SystemExit(f'missing hard-speed configuration: {token}')
if 'id="fast-render"' not in (root / 'webcad_xbf/templates/project.html').read_text() or 'fast_render' not in (root / 'webcad_xbf/static/js/project.js').read_text():
    raise SystemExit('Fast render / FastSewing checkbox is not wired')

for token in ('freecad_faceted_export.py', '_run_freecad_part_export', 'separate closed manifold OpenSCAD polyhedron solids', 'mesh_object_count'):
    if token not in geometry and token not in (root / 'scripts/freecad_faceted_export.py').read_text():
        raise SystemExit(f'missing corrected solid export feature: {token}')
freecad_builder = (root / 'scripts/freecad_faceted_export.py').read_text()
if 'doc.addObject("Mesh::Feature"' in freecad_builder:
    raise SystemExit('FCStd solid exporter must not create Mesh::Feature objects')
if 'Part::Feature' not in freecad_builder or 'faceted-solid' not in freecad_builder:
    raise SystemExit('FCStd solid exporter must create validated Part geometry')
for token in ('faceted-mixed-solid-shell', 'retained_shells', 'faceted_open_shell_count'):
    if token not in freecad_builder:
        raise SystemExit(f'FCStd mixed solid/shell preservation contract is missing: {token}')
for token in ('CASCADE_CAD_FREECAD_MANIFEST', 'CASCADE_CAD_FREECAD_REPORT'):
    if token not in freecad_builder or token not in geometry:
        raise SystemExit(f'FreeCAD environment invocation contract is missing: {token}')
if '_invocation_from_environment' not in freecad_builder:
    raise SystemExit('FreeCAD helper environment parser is missing')
if 'command = [_freecad_command(), "--console"]' not in geometry or 'runpy.run_path' not in geometry:
    raise SystemExit('FreeCAD launcher must execute the helper through console stdin')
if 'mixed_source_geometry' not in geometry:
    raise SystemExit('Part export must report components whose exact and mesh faces are wholly faceted')
csg_section = geometry.split('def export_csg(', 1)[1].split('def _freecad_command', 1)[0]
if 'handle.write("group()' in csg_section:
    raise SystemExit('CSG exporter must not wrap all parts in one root group')
template = (root / 'webcad_xbf/templates/project.html').read_text()
for token in ('export-format', 'export-button', 'export-selected-only', 'solid-operation-tool', 'draft-tool', 'data-operation="extrude"', 'data-draft="bspline"', 'share-draw-square', 'share-photo', 'share-record', 'share-bluesky', 'share-instagram', 'convert-faceted-solids', '.FCStd', '.CSG', '.BREP'):
    if token not in template:
        raise SystemExit(f'missing unified export UI: {token}')

index_template = (root / 'webcad_xbf/templates/index.html').read_text()
for token in ('Make Solid(s) from Mesh', 'Even in Assemblies', 'Convert to Tessellated (Faceted) Solids'):
    if token not in index_template:
        raise SystemExit(f'missing mesh-to-solids upload-page message: {token}')
for token in ('_make_draft_shape', '_extrude_selected', '_revolve_selected', '_cross_section_selected', '_sweep_selected', '_loft_selected', 'BRepPrimAPI_MakeCone'):
    if token not in geometry:
        raise SystemExit(f'missing advanced modeling backend: {token}')

share_media = (root / 'webcad_xbf/share_media.py').read_text()
for token in ('ffmpeg', 'libx264', 'yuv420p', 'normalize_share_image', 'normalize_share_video'):
    if token not in share_media:
        raise SystemExit(f'missing social media normalization feature: {token}')

share_js = (root / 'webcad_xbf/static/js/share-capture.js').read_text()
for token in ('captureStream', 'MAX_RECORDING_SECONDS = 60', 'navigator.canShare', 'bsky.app/intent/compose', 'www.instagram.com', '/share-media/normalize'):
    if token not in share_js:
        raise SystemExit(f'missing square capture/share feature: {token}')

css = (root / 'webcad_xbf/static/css/app.css').read_text()
for token in ('theme-select', 'data-theme-resolved="light"'):
    if token not in template:
        raise SystemExit(f'missing editor theme UI: {token}')
for token in ('data-theme-resolved="light"', 'data-theme-resolved="dark"'):
    if token not in css:
        raise SystemExit(f'missing editor theme CSS: {token}')
for token in ('export-control', 'grid-template-rows:auto minmax(0,1fr)', 'clamp('):
    if token not in css:
        raise SystemExit(f'missing responsive toolbar CSS: {token}')
print('CascadeCAD package structure OK')
PY
