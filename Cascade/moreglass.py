import os
import shutil

# Define base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_ROOT = os.path.join(BASE_DIR, "webcad_xbf")
STATIC_DIR = os.path.join(WEB_ROOT, "static")
JS_DIR = os.path.join(STATIC_DIR, "js")
CSS_DIR = os.path.join(STATIC_DIR, "css")
TEMPLATE_DIR = os.path.join(WEB_ROOT, "templates")

def ensure_dirs():
    os.makedirs(JS_DIR, exist_ok=True)
    os.makedirs(CSS_DIR, exist_ok=True)
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    print("[+] Verified directory structures.")

def apply_patches():
    ensure_dirs()

    # 1. Patch CSS (Glass Toolbar Styles)
    css_path = os.path.join(CSS_DIR, "toolbar.css")
    css_content = """/* CascadeCAD Glass Toolbar Styles */
.glass-toolbar {
    position: absolute;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 6px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    z-index: 100;
    transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.glass-toolbar.auto-hide {
    transform: translateX(-50%) translateY(-38px);
    opacity: 0.35;
}

.glass-toolbar.auto-hide:hover,
.glass-toolbar.pinned,
.glass-toolbar.active-selection {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
}

.toolbar-handle {
    width: 36px;
    height: 3px;
    background: rgba(255, 255, 255, 0.25);
    border-radius: 2px;
    margin-top: 4px;
}

.toolbar-content {
    display: flex;
    gap: 8px;
    align-items: center;
}

.glass-icon-btn {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    color: #94a3b8;
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
}

.glass-icon-btn:hover {
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.4);
    color: #38bdf8;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
}

.glass-icon-btn.active {
    background: rgba(56, 189, 248, 0.25);
    border-color: #38bdf8;
    color: #38bdf8;
}

.pin-toggle.active {
    background: rgba(34, 197, 94, 0.2);
    border-color: rgba(34, 197, 94, 0.5);
    color: #4ade80;
}

.toolbar-divider {
    width: 1px;
    height: 22px;
    background: rgba(255, 255, 255, 0.1);
    margin: 0 4px;
}
"""
    with open(css_path, "w") as f:
        f.write(css_content)
    print(f"[+] Updated style patch: {css_path}")

    # 2. Patch JS (Toolbar Interactivity)
    js_patch_snippet = """
// Toolbar Pin & Active States Logic
document.addEventListener('DOMContentLoaded', () => {
    const toolbar = document.getElementById('canvas-toolbar');
    const pinBtn = toolbar?.querySelector('.pin-toggle');
    const toolButtons = toolbar?.querySelectorAll('.glass-icon-btn:not(.pin-toggle)');

    if (pinBtn) {
        pinBtn.addEventListener('click', () => {
            toolbar.classList.toggle('pinned');
            pinBtn.classList.toggle('active');
        });
    }

    toolButtons?.forEach(btn => {
        btn.addEventListener('click', () => {
            toolButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            toolbar.classList.add('active-selection');
        });
    });

    document.addEventListener('click', (e) => {
        if (!toolbar?.contains(e.target) && !toolbar?.classList.contains('pinned')) {
            toolbar?.classList.remove('active-selection');
        }
    });
});
"""
    project_js_path = os.path.join(JS_DIR, "project.js")
    if os.path.exists(project_js_path):
        with open(project_js_path, "r") as f:
            content = f.read()
        if "canvas-toolbar" not in content:
            with open(project_js_path, "a") as f:
                f.write(js_patch_snippet)
            print("[+] Injected toolbar script logic into project.js")
        else:
            print("[*] Toolbar logic already present in project.js")

    print("[+] All patches applied successfully!")

if __name__ == "__main__":
    apply_patches()
