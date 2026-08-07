import os

# 1. Write high-impact, vibrant CAD Ribbon CSS
css_path = "webcad_xbf/static/css/toolbar.css"
css_content = """/* CascadeCAD Professional Command Ribbon */
.cascade-top-ribbon {
    position: absolute;
    top: 14px;
    left: 16px;
    right: 16px;
    height: 52px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(56, 189, 248, 0.4);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7), 0 0 20px rgba(56, 189, 248, 0.15);
    z-index: 9999;
}

.ribbon-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.ribbon-section-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #38bdf8;
    margin-right: 4px;
    padding-right: 8px;
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.ribbon-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: #cbd5e1;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
}

.ribbon-btn svg {
    stroke: #38bdf8;
    transition: transform 0.2s ease;
}

.ribbon-btn:hover {
    background: rgba(56, 189, 248, 0.18);
    border-color: rgba(56, 189, 248, 0.6);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.3);
}

.ribbon-btn:hover svg {
    transform: scale(1.1);
}

.ribbon-btn.active {
    background: rgba(56, 189, 248, 0.28);
    border-color: #38bdf8;
    color: #38bdf8;
    box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
}

.ribbon-divider {
    width: 1px;
    height: 28px;
    background: rgba(255, 255, 255, 0.12);
    margin: 0 6px;
}
"""

with open(css_path, "w") as f:
    f.write(css_content)
print("[+] Updated toolbar.css with professional ribbon style.")

# 2. Update project.html template with the complete feature set (Import, Cross Sections, Info, etc.)
template_path = "webcad_xbf/templates/project.html"
with open(template_path, "r") as f:
    html = f.read()

ribbon_html = """
    <!-- Professional Top Command Ribbon -->
    <div class="cascade-top-ribbon">
        <!-- Group 1: File & Data -->
        <div class="ribbon-group">
            <span class="ribbon-section-title">Data</span>
            <button class="ribbon-btn" title="Import Geometry / CAD Files" data-action="import">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"></path></svg>
                Import
            </button>
            <button class="ribbon-btn" title="Inspect Assembly Info & Matrix" data-action="info">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4M12 8h.01"></path></svg>
                Info
            </button>
        </div>

        <div class="ribbon-divider"></div>

        <!-- Group 2: Navigation & View -->
        <div class="ribbon-group">
            <span class="ribbon-section-title">View</span>
            <button class="ribbon-btn active" title="Select & Transform" data-action="select">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"></path></svg>
                Select
            </button>
            <button class="ribbon-btn" title="Orbit View" data-action="orbit">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"></path></svg>
                Orbit
            </button>
            <button class="ribbon-btn" title="Pan View" data-action="pan">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l3 3 3-3M19 9l3 3-3 3M2 12h20M12 2v20"></path></svg>
                Pan
            </button>
        </div>

        <div class="ribbon-divider"></div>

        <!-- Group 3: Modeling & Analysis -->
        <div class="ribbon-group">
            <span class="ribbon-section-title">Operations</span>
            <button class="ribbon-btn" title="Generate Cross Sections" data-action="cross-section">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H4a2 2 0 00-2 2v16a2 2 0 002 2zM2 12h20M12 2v20"></path></svg>
                Cross Section
            </button>
            <button class="ribbon-btn" title="Extrude Geometry" data-action="extrude">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M12 2l10 5.5v11L12 22 2 18.5v-11L12 2z"></path></svg>
                Extrude
            </button>
            <button class="ribbon-btn" title="Boolean Cut" data-action="boolean">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="9" cy="12" r="6"></circle><circle cx="15" cy="12" r="6"></circle></svg>
                Boolean
            </button>
        </div>
    </div>
"""

# Clean up any old toolbars from HTML
import re
html = re.sub(r'<div id="canvas-toolbar"[^>]*>.*?</div>\s*</div>', '', html, flags=re.DOTALL)
html = re.sub(r'<div class="cascade-toolbar-container".*?</div>\s*</div>\s*</div>', '', html, flags=re.DOTALL)

if "[ RENDER CANVAS ]" in html and "cascade-top-ribbon" not in html:
    html = html.replace("[ RENDER CANVAS ]", f"{ribbon_html}\n[ RENDER CANVAS ]")
    with open(template_path, "w") as f:
        f.write(html)
    print("[+] Successfully embedded the professional command ribbon into project.html")
