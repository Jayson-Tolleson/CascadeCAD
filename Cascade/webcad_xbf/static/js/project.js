function togglePanel(panelId) {
  const panel = document.getElementById(panelId);
  panel.classList.toggle('minimized');
  logDebug(`[UI] Matrix shift: ${panelId} toggled.`, 'math');
}

function logDebug(msg, type = 'normal') {
  const term = document.getElementById('debug-terminal');
    if (!term) {
        console.log(`[Debug] ${msg}`);
        return;
    }
  const div = document.createElement('div');
  div.className = `debug-line ${type === 'math' ? 'debug-math' : ''} ${type === 'warn' ? 'debug-warn' : ''} ${type === 'err' ? 'debug-err' : ''}`;
  div.innerText = msg;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function initDebugTelemetry() {
  const token = localStorage.getItem('cascade_cad_token') || 'default_token';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const debugWsUrl = `${proto}//${window.location.host}/cascade-cad/api/v1/collaboration/debug?token=${token}&channel=debug`;

  let debugSocket = null;
try {
    // Safely attempt WebSocket connection with error handling to prevent console spam
    debugSocket = new WebSocket(debugWsUrl);
    debugSocket.onerror = () => { /* Suppress noisy connection refusal logs */ };
} catch (e) {
    console.warn("WebSocket connection skipped.");
}

  debugSocket.onopen = () => {
    logDebug("[SYS] Telemetry stream online. Listening to backend matrices...", "math");
  };

  debugSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "debug") {
        logDebug(data.text, data.level);
      }
    } catch (err) {
      console.error("Failed to parse telemetry frame:", err);
    }
  };

  debugSocket.onclose = () => {
    logDebug("[WARN] Telemetry stream disconnected. Reconnecting in 3s...", "warn");
    setTimeout(initDebugTelemetry, 3000);
  };

  debugSocket.onerror = (err) => {
    logDebug("[ERR] Telemetry socket failure.", "err");
  };
}

window.addEventListener('DOMContentLoaded', () => {
  initDebugTelemetry();
});

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


// ---------------------------------------------------------
// ENTRY DIALOG & COLLABORATION PROFILE INITIALIZATION
// ---------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    const profileDialog = document.getElementById('collaboration-profile-dialog');
    const profileForm = document.getElementById('collaboration-profile-form');
    const usernameInput = document.getElementById('collaboration-username');
    const editProfileBtn = document.getElementById('edit-collaboration-profile');

    if (!profileDialog) return;

    // Check if user has an active session stored locally
    const savedUsername = localStorage.getItem('cascade_username');
    
    // If no username exists, pop open the entry dialog automatically
    if (!savedUsername && typeof profileDialog.showModal === 'function') {
        console.log("👤 No session found. Opening entry dialog...");
        profileDialog.showModal();
    } else if (savedUsername && usernameInput) {
        usernameInput.value = savedUsername;
    }

    // Save profile state on submission
    if (profileForm) {
        profileForm.addEventListener('submit', (e) => {
            const username = usernameInput ? usernameInput.value.trim() : '';
            if (username) {
                localStorage.setItem('cascade_username', username);
                console.log(`✅ Welcome to CascadeCAD, ${username}!`);
                
                // Optional: Sync user presence to Quart backend here
                fetch('/cascade-cad/api/v1/user/profile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username })
                }).catch(err => console.warn("⚠️ Profile sync skipped:", err));
            }
        });
    }

    // Manual re-opening via the sidebar settings button
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', () => {
            const currentName = localStorage.getItem('cascade_username');
            if (usernameInput && currentName) {
                usernameInput.value = currentName;
            }
            profileDialog.showModal();
        });
    }
});


// ---------------------------------------------------------
// INITIALIZING CASCADE-CAD 3D VIEWPORT WORKSPACE
// ---------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    const viewerContainer = document.getElementById('viewer');
    const viewerMessage = viewerContainer ? viewerContainer.querySelector('.viewer-message') : null;
    const projectTitle = document.getElementById('project-title');

    if (!viewerContainer) return;

    console.log("🖥️ Initializing CascadeCAD 3D viewport workspace...");

    if (viewerMessage) {
        viewerMessage.textContent = "Loading blank project canvas...";
    }

    setTimeout(() => {
        if (window.CascadeViewport && typeof window.CascadeViewport.init === 'function') {
            window.CascadeViewport.init(viewerContainer);
            console.log("✅ Viewport controller attached successfully.");
        } else if (window.initViewport && typeof window.initViewport === 'function') {
            window.initViewport();
            console.log("✅ Legacy viewport initializer triggered.");
        } else {
            if (viewerMessage) {
                viewerMessage.style.display = 'none';
            }
            console.log("ℹ️ Viewport script loaded in standalone mode.");
        }
    }, 100);

    const savedUsername = localStorage.getItem('cascade_username');
    if (projectTitle && savedUsername && projectTitle.textContent.includes("Untitled")) {
        projectTitle.textContent = `${savedUsername}'s Workspace`;
    }
});