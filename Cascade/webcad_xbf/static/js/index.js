const page = document.body.dataset;
const basePath = String(page.basePath || '').replace(/\/$/, '');
const maxUploadBytes = Number(page.maxUploadBytes || 0);
const ACTIVE_JOB_KEY = 'cascade-cad-active-job-v1';

function appPath(path = '/') {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${basePath}${normalized}`;
}

function sleep(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return 'unknown size';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

async function parseResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return {error: text.slice(0, 500)};
  }
}

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, {
    cache: 'no-store',
    credentials: 'same-origin',
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {})
    }
  });
  const payload = await parseResponse(response);
  if (!response.ok) {
    const error = new Error(payload.error || `${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function uploadChunk(url, chunk, onProgress, timeoutMilliseconds = 180000) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const timeout = setTimeout(() => {
      xhr.abort();
      reject(new Error('Chunk upload timed out'));
    }, timeoutMilliseconds);

    xhr.open('PUT', url, true);
    xhr.responseType = 'text';
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('Accept', 'application/json');

    xhr.upload.onprogress = event => {
      if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
    };

    xhr.onerror = () => {
      clearTimeout(timeout);
      reject(new Error('Network error while sending chunk'));
    };
    xhr.onabort = () => {
      clearTimeout(timeout);
      reject(new Error('Chunk upload was aborted'));
    };
    xhr.onload = () => {
      clearTimeout(timeout);
      let payload = {};
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch {
        payload = {error: xhr.responseText?.slice(0, 500)};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload);
      } else {
        const error = new Error(payload.error || `${xhr.status} ${xhr.statusText}`);
        error.status = xhr.status;
        reject(error);
      }
    };
    xhr.send(chunk);
  });
}

function rememberActiveJob(job, projectId) {
  localStorage.setItem(ACTIVE_JOB_KEY, JSON.stringify({
    job_id: job.id,
    project_id: projectId,
    saved_at: Date.now()
  }));
}

function forgetActiveJob() {
  localStorage.removeItem(ACTIVE_JOB_KEY);
}

function recalledActiveJob() {
  try {
    const value = JSON.parse(localStorage.getItem(ACTIVE_JOB_KEY) || 'null');
    if (!value?.job_id || !value?.project_id) return null;
    return value;
  } catch {
    return null;
  }
}

async function pollJob(job, onUpdate) {
  let delay = 700;
  let networkFailures = 0;
  let lastProgress = 0;
  while (true) {
    try {
      const update = await jsonFetch(appPath(`/api/jobs/${job.id}`));
      networkFailures = 0;
      lastProgress = Number(update.progress || lastProgress || 0);
      onUpdate(update);
      if (update.status === 'complete') return update;
      if (update.status === 'failed') {
        const error = new Error(update.message || update.error || 'Geometry conversion failed');
        error.terminal = true;
        throw error;
      }
      await sleep(delay);
      delay = Math.min(2500, Math.round(delay * 1.15));
    } catch (error) {
      // A geometry import can temporarily pressure the VM enough that nginx or
      // Hypercorn misses a poll. Do not abandon a valid server-side job after
      // one lost request. The job id is also persisted for page reload recovery.
      if (error.terminal || error.status === 404) {
        throw error;
      }
      networkFailures += 1;
      if (networkFailures > 360) {
        throw new Error(`Unable to reconnect to CascadeCAD: ${error.message || error}`);
      }
      const retrySeconds = Math.min(10, Math.max(2, networkFailures));
      onUpdate({
        status: 'reconnecting',
        progress: lastProgress,
        message: `Server connection interrupted; retrying in ${retrySeconds}s…`
      });
      await sleep(retrySeconds * 1000);
      delay = 700;
    }
  }
}

function initialize() {
  const fileInput = document.querySelector('#file-input');
  const button = document.querySelector('#upload-button');
  const projectName = document.querySelector('#project-name');
  const statusBox = document.querySelector('#upload-status');
  const statusMessage = document.querySelector('#status-message');
  const progressBar = document.querySelector('#progress-bar');
  const projects = document.querySelector('#projects');
  const refreshProjects = document.querySelector('#refresh-projects');
  const deleteProjectButton = document.querySelector('#delete-project');
  const dropZone = document.querySelector('#drop-zone');
  const meshCleanup = document.querySelector('#mesh-cleanup');
  const chosenFile = document.querySelector('#chosen-file');
  let selectedFile = null;
  let selectedProject = null;

  if (!fileInput || !button || !projectName || !statusBox || !statusMessage || !progressBar || !projects) {
    console.error('CascadeCAD upload controls are missing from the page.');
    return;
  }

  function setStatus(message, percent = 0) {
    statusBox.hidden = false;
    statusMessage.textContent = message;
    progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  }

  function setSelectedFile(file) {
    selectedFile = file || null;
    if (!selectedFile) {
      button.disabled = true;
      if (chosenFile) chosenFile.textContent = 'No file selected';
      return;
    }
    button.disabled = false;
    if (chosenFile) chosenFile.textContent = `${selectedFile.name} · ${formatBytes(selectedFile.size)}`;
    if (!projectName.value.trim()) projectName.value = selectedFile.name.replace(/\.[^.]+$/, '');
  }

  fileInput.addEventListener('change', () => setSelectedFile(fileInput.files?.[0]));

  if (dropZone) {
    for (const eventName of ['dragenter', 'dragover']) {
      dropZone.addEventListener(eventName, event => {
        event.preventDefault();
        dropZone.classList.add('drag-active');
      });
    }
    for (const eventName of ['dragleave', 'drop']) {
      dropZone.addEventListener(eventName, event => {
        event.preventDefault();
        dropZone.classList.remove('drag-active');
      });
    }
    dropZone.addEventListener('drop', event => {
      const files = event.dataTransfer?.files;
      if (!files?.length) return;
      setSelectedFile(files[0]);
    });
  }

  function selectProject(project, row) {
    selectedProject = project;
    projects.querySelectorAll('.project-row.selected').forEach(item => item.classList.remove('selected'));
    row?.classList.add('selected');
    if (deleteProjectButton) deleteProjectButton.disabled = !selectedProject;
  }

  async function loadProjects() {
    selectedProject = null;
    if (deleteProjectButton) deleteProjectButton.disabled = true;
    projects.innerHTML = '<p>Loading…</p>';
    try {
      const data = await jsonFetch(appPath('/api/projects'));
      if (!data.projects.length) {
        projects.innerHTML = '<p>No projects yet.</p>';
        return;
      }
      projects.innerHTML = data.projects.map(project => `
        <div class="project-row" data-project-id="${escapeHtml(project.id)}" tabindex="0" role="button" aria-label="Select ${escapeHtml(project.name)}">
          <span><b>${escapeHtml(project.name)}</b><small>${escapeHtml(project.source_filename || '')}</small></span>
          <span class="project-row-tools">
            <span class="state-pill ${escapeHtml(project.status)}">${escapeHtml(project.status)}</span>
            <a class="button project-open" href="${appPath(`/project/${project.id}`)}">Open</a>
          </span>
        </div>`).join('');
      for (const row of projects.querySelectorAll('.project-row')) {
        const project = data.projects.find(item => item.id === row.dataset.projectId);
        row.addEventListener('click', event => {
          if (event.target.closest('a')) return;
          selectProject(project, row);
        });
        row.addEventListener('dblclick', event => {
          if (event.target.closest('a')) return;
          location.assign(appPath(`/project/${project.id}`));
        });
        row.addEventListener('keydown', event => {
          if (event.key === 'Enter') location.assign(appPath(`/project/${project.id}`));
          if (event.key === ' ') { event.preventDefault(); selectProject(project, row); }
        });
      }
    } catch (error) {
      projects.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    }
  }


  refreshProjects?.addEventListener('click', loadProjects);
  deleteProjectButton?.addEventListener('click', async () => {
    if (!selectedProject) return;
    const confirmed = confirm(`Delete project "${selectedProject.name}" and its XBF, previews, exports, and revisions? This cannot be undone.`);
    if (!confirmed) return;
    deleteProjectButton.disabled = true;
    try {
      await jsonFetch(appPath(`/api/projects/${selectedProject.id}`), {method: 'DELETE'});
      selectedProject = null;
      await loadProjects();
    } catch (error) {
      alert(error.message || 'Project deletion failed');
      deleteProjectButton.disabled = false;
    }
  });

  button.addEventListener('click', async () => {
    const file = selectedFile;
    if (!file) return;
    if (maxUploadBytes > 0 && file.size > maxUploadBytes) {
      setStatus(`File exceeds the ${formatBytes(maxUploadBytes)} server upload limit.`, 0);
      return;
    }

    button.disabled = true;
    try {
      setStatus('Checking CascadeCAD server…', 1);
      await jsonFetch(appPath('/healthz'));

      setStatus('Creating project…', 2);
      const started = await jsonFetch(appPath('/api/uploads/start'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          filename: file.name,
          size: file.size,
          project_name: projectName.value,
          mesh_cleanup: Boolean(meshCleanup?.checked)
        })
      });

      const chunkSize = Number(started.chunk_bytes);
      if (!Number.isFinite(chunkSize) || chunkSize <= 0) {
        throw new Error('Server returned an invalid upload chunk size');
      }

      let offset = Number(started.upload.received || 0);
      while (offset < file.size) {
        const chunkEnd = Math.min(file.size, offset + chunkSize);
        const chunk = file.slice(offset, chunkEnd);
        let result = null;
        let lastError = null;

        for (let attempt = 1; attempt <= 20; attempt += 1) {
          try {
            result = await uploadChunk(
              appPath(`/api/uploads/${started.upload.id}/chunk?offset=${offset}`),
              chunk,
              loaded => {
                const sent = offset + loaded;
                setStatus(
                  `Uploading ${file.name} · ${formatBytes(sent)} of ${formatBytes(file.size)}`,
                  Math.floor((sent / file.size) * 65)
                );
              }
            );
            break;
          } catch (error) {
            lastError = error;

            // The server may have saved the chunk even if the response was lost.
            try {
              const serverUpload = await jsonFetch(appPath(`/api/uploads/${started.upload.id}`));
              if (Number(serverUpload.received) >= chunkEnd) {
                result = serverUpload;
                break;
              }
              if (Number(serverUpload.received) !== offset) {
                offset = Number(serverUpload.received);
                result = serverUpload;
                break;
              }
            } catch {
              // Preserve the original network error and retry.
            }

            if (attempt < 20) {
              const retrySeconds = Math.min(30, Math.max(2, attempt * 2));
              setStatus(`Upload interrupted; retrying chunk (${attempt}/20) in ${retrySeconds}s…`, Math.floor((offset / file.size) * 65));
              await sleep(retrySeconds * 1000);
            }
          }
        }

        if (!result) throw lastError || new Error('Chunk upload failed');
        offset = Number(result.received);
        if (!Number.isFinite(offset) || offset < 0 || offset > file.size) {
          throw new Error('Server returned an invalid upload offset');
        }
      }

      setStatus('Upload complete. Queuing geometry import…', 67);
      const finished = await jsonFetch(appPath(`/api/uploads/${started.upload.id}/finish`), {
        method: 'POST'
      });

      rememberActiveJob(finished.job, finished.project_id);
      await pollJob(finished.job, update => {
        const workerProgress = Number(update.progress || 0);
        setStatus(update.message || update.status, 67 + workerProgress * 0.33);
      });

      forgetActiveJob();
      setStatus('Project ready.', 100);
      location.assign(appPath(`/project/${finished.project_id}`));
    } catch (error) {
      console.error(error);
      setStatus(error.message || 'Upload failed', 0);
      button.disabled = false;
    }
  });

  async function resumeActiveJob() {
    const active = recalledActiveJob();
    if (!active) return;
    button.disabled = true;
    try {
      setStatus('Reconnecting to the active geometry job…', 67);
      await pollJob({id: active.job_id}, update => {
        const workerProgress = Number(update.progress || 0);
        setStatus(update.message || update.status, 67 + workerProgress * 0.33);
      });
      forgetActiveJob();
      setStatus('Project ready.', 100);
      location.assign(appPath(`/project/${active.project_id}`));
    } catch (error) {
      forgetActiveJob();
      setStatus(error.message || 'Recovered job failed', 0);
      button.disabled = !selectedFile;
    }
  }

  loadProjects();
  resumeActiveJob();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize, {once: true});


document.addEventListener('DOMContentLoaded', () => {
    const projectId = document.body.dataset.projectId;
    if (!projectId) return;

    // ---------------------------------------------------------
    // 1. EXPORT PIPELINE (.XBF, .STEP, .CSG, .BREP, .FCStd)
    // ---------------------------------------------------------
    const exportBtn = document.getElementById('export-button');
    const exportFormatSelect = document.getElementById('export-format');
    const exportSelectedOnly = document.getElementById('export-selected-only');

    if (exportBtn) {
        exportBtn.addEventListener('click', async () => {
            const format = exportFormatSelect ? exportFormatSelect.value : 'xbf';
            const selectedOnly = exportSelectedOnly ? exportSelectedOnly.checked : false;
            
            console.log(`📤 Requesting export: format=.${format}, selectionOnly=${selectedOnly}`);
            
            try {
                const response = await fetch(`/${projectId}/export?format=${format}&selected=${selectedOnly}`, {
                    method: 'GET'
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    link.download = `project_${projectId}.${format}`;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    console.log("✅ Export file downloaded successfully.");
                } else {
                    console.error("❌ Server returned export error status:", response.status);
                }
            } catch (err) {
                console.error("❌ Export request failed:", err);
            }
        });
    }

    // ---------------------------------------------------------
    // 2. COMMIT EDITS (Save working state to master.xbf)
    // ---------------------------------------------------------
    const commitBtn = document.getElementById('commit-edits');
    if (commitBtn) {
        commitBtn.addEventListener('click', async () => {
            console.log("💾 Committing current edits to master XBF...");
            try {
                const res = await fetch(`/${projectId}/commit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                console.log("✅ Commit successful:", data);
            } catch (err) {
                console.error("❌ Commit failed:", err);
            }
        });
    }

    // ---------------------------------------------------------
    // 3. RELOAD MASTER XBF (Revert uncommitted workspace changes)
    // ---------------------------------------------------------
    const reloadMasterBtn = document.getElementById('reload-master');
    if (reloadMasterBtn) {
        reloadMasterBtn.addEventListener('click', async () => {
            if (!confirm("Are you sure you want to reload master.xbf? Uncommitted changes will be lost.")) return;
            
            console.log("🔄 Reverting workspace to committed master XBF...");
            try {
                const res = await fetch(`/${projectId}/reload`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                console.log("✅ Workspace reloaded:", data);
                // Refresh the page or viewport data
                window.location.reload();
            } catch (err) {
                console.error("❌ Failed to reload master XBF:", err);
            }
        });
    }
});




document.addEventListener('DOMContentLoaded', () => {
    const projectId = document.body.dataset.projectId;
    if (!projectId) return;

    // 1. Undo Button
    const undoBtn = document.getElementById('undo-edit');
    if (undoBtn) {
        undoBtn.addEventListener('click', async () => {
            console.log("⏪ Dispatching Undo command...");
            try {
                const res = await fetch('/api/v1/commands/undo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_id: projectId })
                });
                const data = await res.json();
                console.log("✅ Undo response:", data);
            } catch (err) {
                console.error("❌ Undo failed:", err);
            }
        });
    }

    // 2. Redo Button
    const redoBtn = document.getElementById('redo-edit');
    if (redoBtn) {
        redoBtn.addEventListener('click', async () => {
            console.log("⏩ Dispatching Redo command...");
            try {
                const res = await fetch('/api/v1/commands/redo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_id: projectId })
                });
                const data = await res.json();
                console.log("✅ Redo response:", data);
            } catch (err) {
                console.error("❌ Redo failed:", err);
            }
        });
    }

    // 3. Commit XBF Button
    const commitBtn = document.getElementById('commit-edits');
    if (commitBtn) {
        commitBtn.addEventListener('click', async () => {
            console.log("💾 Committing master XBF...");
            try {
                const res = await fetch(`/${projectId}/commit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                console.log("✅ Commit successful:", data);
            } catch (err) {
                console.error("❌ Commit failed:", err);
            }
        });
    }

    // 4. Combine Projects / Assembly Dialog Trigger
    const combineBtn = document.getElementById('combine-projects');
    const combineDialog = document.getElementById('combine-dialog');
    if (combineBtn && combineDialog) {
        combineBtn.addEventListener('click', async () => {
            console.log("🧩 Fetching project list for assembly...");
            try {
                const res = await fetch('/api/projects');
                const projects = await res.json();
                
                // Populate your combine dialog list container here
                const listContainer = document.getElementById('combine-project-list');
                if (listContainer) {
                    listContainer.innerHTML = projects.map(p => 
                        `<label><input type="checkbox" value="${p.id}"> ${p.name}</label>`
                    ).join('');
                }
                
                combineDialog.showModal();
            } catch (err) {
                console.error("❌ Failed to load projects list:", err);
            }
        });
    }
});



} else {
  initialize();
}
