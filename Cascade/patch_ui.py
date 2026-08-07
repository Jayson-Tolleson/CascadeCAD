import os
import re

os.makedirs("webcad_xbf/static/css", exist_ok=True)
os.makedirs("webcad_xbf/templates", exist_ok=True)

css_path = "webcad_xbf/static/css/toolbar.css"
css_content = """/* CascadeCAD 6-Tier Stacked Ribbon System */
.toolbar-dock {
    width: 100%;
    background: #090d16;
    border-bottom: 2px solid #00f0ff;
    box-shadow: 0 4px 20px rgba(0, 240, 255, 0.15);
    display: flex;
    flex-direction: column;
    position: relative;
    z-index: 1000;
}

.toolbar-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px;
    background: #0f172a;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    overflow-x: auto;
    width: 100%;
    white-space: nowrap;
}

.toolbar-row:nth-child(even) {
    background: #131c31;
}

.tool-group {
    display: flex;
    align-items: center;
    gap: 5px;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 3px 6px;
}

.tool-group-label {
    font-size: 9px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #00f0ff;
    padding-right: 5px;
    margin-right: 2px;
    border-right: 1px solid rgba(255, 255, 255, 0.15);
}

.toolbar-drag-handle {
    display: none;
}

.tool-group button, 
.export-control button, 
#toolbar-dock button {
    background: #1e293b;
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.12s ease-in-out;
}

.tool-group button:hover, 
#toolbar-dock button:hover {
    background: #00f0ff;
    color: #020617;
    border-color: #00f0ff;
    box-shadow: 0 0 10px rgba(0, 240, 255, 0.5);
}

.tool-group button.active, 
.tool-group button:active {
    background: #00f0ff;
    color: #020617;
    font-weight: 700;
}

button.primary-action, #import-model-btn {
    background: linear-gradient(135deg, #00f0ff 0%, #007bff 100%) !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 700 !important;
}

button.primary-action:hover, #import-model-btn:hover {
    background: linear-gradient(135deg, #38bdf8 0%, #0056b3 100%) !important;
    box-shadow: 0 0 14px rgba(0, 240, 255, 0.8) !important;
}

button.danger {
    background: #ef4444 !important;
    color: #ffffff !important;
    border: none !important;
}

button.danger:hover {
    background: #dc2626 !important;
}

.export-control {
    display: flex;
    align-items: center;
    gap: 6px;
}

.export-control select, .unit-toggle {
    background: #0f172a;
    color: #00f0ff;
    border: 1px solid #00f0ff;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 11px;
    font-weight: 700;
}

.export-selection {
    font-size: 10px;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 3px;
}
"""

with open(css_path, "w") as f:
    f.write(css_content)
print("[+] Applied 6-tier stacked ribbon CSS.")

html_path = "webcad_xbf/templates/project.html"
with open(html_path, "r") as f:
    html_content = f.read()

new_dock = """    <div id="toolbar-dock" class="toolbar-dock" role="toolbar" aria-label="CascadeCAD editor tools">
      <!-- Bar 1: Project & File Operations -->
      <div class="toolbar-row" data-toolbar-row="bar-1">
        <div class="tool-group" data-toolbar-id="project">
          <span class="tool-group-label">Project</span>
          <button id="undo-edit" type="button" title="Undo (Ctrl+Z)">Undo</button>
          <button id="redo-edit" type="button" title="Redo (Ctrl+Y)">Redo</button>
          <button id="fit-view" type="button" title="Fit view (F)">Fit</button>
          <button id="reload-master" type="button" title="Reload committed master.xbf">Master XBF</button>
          <button id="combine-projects" type="button">Add Projects</button>
          <button id="commit-edits" type="button" class="primary-action">Commit XBF</button>
          <button id="unit-toggle" type="button" class="unit-toggle" data-unit-system="imperial">IN / FT</button>
          <button id="preferences-button" type="button">Preferences</button>
        </div>
        <div class="tool-group" data-toolbar-id="file-export">
          <span class="tool-group-label">IO</span>
          <div class="export-control">
            <select id="export-format">
              <option value="xbf">.XBF</option>
              <option value="step">.STEP</option>
              <option value="csg">.CSG</option>
              <option value="brep">.BREP</option>
              <option value="fcstd">.FCStd</option>
            </select>
            <label class="export-selection"><input id="export-selected-only" type="checkbox" disabled><span>Sel</span></label>
            <label class="export-selection fast-render-option"><input id="fast-render" type="checkbox"><span>FastSewing</span></label>
            <button id="import-model-btn" type="button" class="primary-action">Import CAD</button>
            <button id="export-button" type="button" class="primary-action">Export</button>
            <button id="convert-faceted-solids" type="button">Faceted Solids</button>
            <button id="cancel-job" type="button" class="danger" hidden>Cancel</button>
          </div>
        </div>
      </div>

      <!-- Bar 2: Navigation & Edit Transforms -->
      <div class="toolbar-row" data-toolbar-row="bar-2">
        <div class="tool-group" data-toolbar-id="edit">
          <span class="tool-group-label">Transform</span>
          <button id="tool-select" class="active" type="button" title="Select (Q)">Select</button>
          <button id="tool-move" type="button" title="Move (W)">Move</button>
          <button id="tool-rotate" type="button" title="Rotate (E)">Rotate</button>
          <button id="tool-scale" type="button" title="Scale (R)">Scale</button>
          <button id="tool-clone" type="button">Clone</button>
          <button id="tool-array" type="button">Array</button>
          <button id="tool-osnap" type="button" aria-pressed="false">OSnap</button>
          <button id="tool-mirror" type="button">Mirror</button>
          <button id="tool-facebinder" type="button">Face Binder</button>
        </div>
      </div>

      <!-- Bar 3: Solids & Primitives -->
      <div class="toolbar-row" data-toolbar-row="bar-3">
        <div class="tool-group" data-toolbar-id="solids">
          <span class="tool-group-label">Solids</span>
          <button class="primitive-tool" data-primitive="box" type="button">Box</button>
          <button class="primitive-tool" data-primitive="cylinder" type="button">Cylinder</button>
          <button class="primitive-tool" data-primitive="pipe" type="button">Pipe</button>
          <button class="primitive-tool" data-primitive="sphere" type="button">Sphere</button>
          <button class="primitive-tool" data-primitive="torus" type="button">Torus</button>
          <button class="primitive-tool" data-primitive="cone" type="button">Cone</button>
          <button class="solid-operation-tool" data-operation="extrude" type="button">Extrude</button>
          <button class="solid-operation-tool" data-operation="revolve" type="button">Revolve</button>
          <button class="solid-operation-tool" data-operation="cross_section" type="button">Cross Sections</button>
          <button class="solid-operation-tool" data-operation="sweep" type="button">Sweep</button>
          <button class="solid-operation-tool" data-operation="loft" type="button">Loft</button>
          <button id="tool-fillet" type="button">Round</button>
          <button id="tool-chamfer" type="button">Chamfer</button>
          <button id="tool-additive-helix" type="button">Add Helix</button>
          <button id="tool-subtractive-helix" type="button">Sub Helix</button>
        </div>
      </div>

      <!-- Bar 4: Draft & Sketch Tools -->
      <div class="toolbar-row" data-toolbar-row="bar-4">
        <div class="tool-group" data-toolbar-id="draft">
          <span class="tool-group-label">Draft</span>
          <button class="draft-tool" data-draft="line" type="button">Line</button>
          <button class="draft-tool" data-draft="bspline" type="button">B-spline</button>
          <button class="draft-tool" data-draft="polyline" type="button">Polyline</button>
          <button class="draft-tool" data-draft="circle" type="button">Circle</button>
          <button class="draft-tool" data-draft="rectangle" type="button">Rectangle</button>
          <button class="draft-tool" data-draft="polygon" type="button">N-side</button>
          <button class="draft-tool" data-draft="ellipse" type="button">Ellipse</button>
        </div>
      </div>

      <!-- Bar 5: Booleans & Inspection -->
      <div class="toolbar-row" data-toolbar-row="bar-5">
        <div class="tool-group" data-toolbar-id="boolean">
          <span class="tool-group-label">Boolean</span>
          <button id="tool-fuse" type="button">Fuse</button>
          <button id="tool-subtract" type="button">Subtract</button>
          <button id="split-selected" type="button">Split</button>
        </div>
        <div class="tool-group" data-toolbar-id="inspect">
          <span class="tool-group-label">Inspect</span>
          <button id="tool-measure" type="button">Measure</button>
          <button id="tool-info" type="button">Info 💡</button>
          <button id="tool-material" type="button">Material</button>
        </div>
      </div>

      <!-- Bar 6: Share & Community -->
      <div class="toolbar-row" data-toolbar-row="bar-6">
        <div class="tool-group" data-toolbar-id="share">
          <span class="tool-group-label">Share</span>
          <button id="share-draw-square" type="button">Draw square</button>
          <button id="share-photo" type="button" disabled>Photo</button>
          <button id="share-record" type="button" disabled>Record 60s</button>
          <button id="share-stop" type="button" class="danger" hidden>Stop</button>
          <button id="share-preview" type="button" disabled>Preview</button>
          <button id="share-bluesky" type="button" disabled>Bluesky</button>
          <button id="share-instagram" type="button" disabled>Instagram</button>
          <button id="share-download" type="button" disabled>Download</button>
          <button id="share-clear" type="button" disabled>Clear</button>
          <span id="share-status" class="share-status" aria-live="polite"></span>
        </div>
        <div class="tool-group" data-toolbar-id="collaboration">
          <span class="tool-group-label">Community</span>
          <button id="collaboration-users-button" type="button">Users</button>
          <button id="project-chat-button" type="button">Project Chat</button>
          <button id="community-button" type="button">Global Board</button>
          <span id="collaboration-unread" class="collaboration-unread" hidden>0</span>
        </div>
      </div>
    </div>"""

html_content = re.sub(
    r'<div id="toolbar-dock".*?</header>',
    f'<header class="topbar cascade-topbar">\n    <div class="project-identity">\n      <a href="{{ url_for(\'index\') }}" class="brand">CascadeCAD</a>\n      <strong id="project-title">{{ project.name }}</strong>\n    </div>\n{new_dock}\n  </header>',
    html_content,
    flags=re.DOTALL
)

with open(html_path, "w") as f:
    f.write(html_content)
print("[+] Successfully restructured project.html into 6 stacked toolbar bars.")
