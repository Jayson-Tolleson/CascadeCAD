file_path = "webcad_xbf/static/js/share-capture.js"

clean_code = """const MAX_RECORDING_SECONDS = 60;
const CAPTURE_SIZE = 1080;
const RECORDING_FPS = 30;
const RECORDING_BITRATE = 1_500_000;

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function extensionForMime(mimeType) {
  if (mimeType.includes('mp4')) return 'mp4';
  if (mimeType.includes('webm')) return 'webm';
  if (mimeType.includes('jpeg')) return 'jpg';
  if (mimeType.includes('png')) return 'png';
  return 'bin';
}

function safeBaseName(value) {
  const clean = String(value || 'cascade-cad')
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return clean || 'cascade-cad';
}

function timestampName() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function recorderMimeType() {
  const candidates = [
    'video/mp4;codecs=avc1.42E01E',
    'video/mp4',
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
  ];
  return candidates.find(value => window.MediaRecorder?.isTypeSupported?.(value)) || '';
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

function mediaFile(media) {
  return new File([media.blob], media.filename, {
    type: media.mimeType,
    lastModified: Date.now(),
  });
}

export function initShareCapture({viewer, getSourceCanvas, getProjectName, appPath, notify}) {
  const drawButton = document.querySelector('#share-draw-square');
  const photoButton = document.querySelector('#share-photo');
  const recordButton = document.querySelector('#share-record');
  const stopButton = document.querySelector('#share-stop');
  const previewButton = document.querySelector('#share-preview');
  const blueskyButton = document.querySelector('#share-bluesky');
  const instagramButton = document.querySelector('#share-instagram');
  const downloadButton = document.querySelector('#share-download');
  const clearButton = document.querySelector('#share-clear');
  const status = document.querySelector('#share-status');
  const dialog = document.querySelector('#share-dialog');
  const dialogClose = document.querySelector('#share-dialog-close');
  const dialogPreview = document.querySelector('#share-dialog-preview');
  const captionInput = document.querySelector('#share-caption');
  const dialogBluesky = document.querySelector('#share-dialog-bluesky');
  const dialogInstagram = document.querySelector('#share-dialog-instagram');
  const dialogDownload = document.querySelector('#share-dialog-download');

  if (!viewer || !drawButton || !photoButton || !recordButton) return null;

  const layer = document.createElement('div');
  layer.className = 'capture-selection-layer';
  layer.setAttribute('aria-hidden', 'true');
  const selectionElement = document.createElement('div');
  selectionElement.className = 'capture-selection-square';
  layer.append(selectionElement);
  viewer.append(layer);

  let selection = null;
  let drawing = false;
  let drawStart = null;
  let activeMedia = null;
  let previewUrl = null;
  let mediaRecorder = null;
  let recordingAnimation = 0;
  let recordingTimer = 0;
  let recordingStartedAt = 0;
  let recordingCanvas = null;
  let recordingContext = null;
  let recordingCrop = null;
  let recordingChunks = [];

  function defaultCaption() {
    return `${getProjectName()} · CascadeCAD`;
  }

  function setStatus(text) {
    if (status) status.textContent = text;
  }

  function setButtons() {
    const hasSelection = Boolean(selection);
    const hasMedia = Boolean(activeMedia);
    const recording = Boolean(mediaRecorder && mediaRecorder.state !== 'inactive');
    photoButton.disabled = !hasSelection || recording;
    recordButton.disabled = !hasSelection || recording || !window.MediaRecorder;
    drawButton.disabled = recording;
    stopButton.hidden = !recording;
    previewButton.disabled = !hasMedia || recording;
    blueskyButton.disabled = !hasMedia || recording;
    instagramButton.disabled = !hasMedia || recording;
    downloadButton.disabled = !hasMedia || recording;
    clearButton.disabled = (!hasMedia && !hasSelection) || recording;
  }

  function renderSelection() {
    if (!selection) {
      selectionElement.hidden = true;
      return;
    }
    selectionElement.hidden = false;
    selectionElement.style.left = `${selection.left}px`;
    selectionElement.style.top = `${selection.top}px`;
    selectionElement.style.width = `${selection.size}px`;
    selectionElement.style.height = `${selection.size}px`;
  }

  function beginDrawing() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') return;
    drawing = false;
    drawStart = null;
    layer.classList.add('active');
    layer.setAttribute('aria-hidden', 'false');
    drawButton.classList.add('active');
    setStatus('Drag a square over the 3D view.');
  }

  function endDrawingMode() {
    layer.classList.remove('active');
    layer.setAttribute('aria-hidden', 'true');
    drawButton.classList.remove('active');
  }

  function squareFromPointer(start, current, bounds) {
    const dx = current.x - start.x;
    const dy = current.y - start.y;
    const maximum = Math.max(32, Math.min(bounds.width, bounds.height));
    const size = clamp(Math.max(Math.abs(dx), Math.abs(dy)), 32, maximum);
    let left = dx < 0 ? start.x - size : start.x;
    let top = dy < 0 ? start.y - size : start.y;
    left = clamp(left, 0, Math.max(0, bounds.width - size));
    top = clamp(top, 0, Math.max(0, bounds.height - size));
    return {left, top, size};
  }

  layer.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const bounds = viewer.getBoundingClientRect();
    drawing = true;
    layer.setPointerCapture(event.pointerId);
    drawStart = {
      x: clamp(event.clientX - bounds.left, 0, bounds.width),
      y: clamp(event.clientY - bounds.top, 0, bounds.height),
    };
    selection = {left: drawStart.x, top: drawStart.y, size: 32};
    renderSelection();
    event.preventDefault();
  });

  layer.addEventListener('pointermove', event => {
    if (!drawing || !drawStart) return;
    const bounds = viewer.getBoundingClientRect();
    selection = squareFromPointer(drawStart, {
      x: clamp(event.clientX - bounds.left, 0, bounds.width),
      y: clamp(event.clientY - bounds.top, 0, bounds.height),
    }, bounds);
    renderSelection();
  });

  function finishSquare(event) {
    if (!drawing) return;
    drawing = false;
    try { layer.releasePointerCapture(event.pointerId); } catch {}
    endDrawingMode();
    renderSelection();
    setStatus(`Square selected: ${Math.round(selection.size)} × ${Math.round(selection.size)} screen pixels.`);
    setButtons();
  }

  layer.addEventListener('pointerup', finishSquare);
  layer.addEventListener('pointercancel', finishSquare);

  function cropForCanvas(sourceCanvas) {
    if (!selection) throw new Error('Draw a capture square first.');
    const sourceBounds = sourceCanvas.getBoundingClientRect();
    const viewerBounds = viewer.getBoundingClientRect();
    const offsetX = viewerBounds.left - sourceBounds.left;
    const offsetY = viewerBounds.top - sourceBounds.top;
    const scaleX = sourceCanvas.width / Math.max(1, sourceBounds.width);
    const scaleY = sourceCanvas.height / Math.max(1, sourceBounds.height);
    const sx = clamp((selection.left + offsetX) * scaleX, 0, sourceCanvas.width - 1);
    const sy = clamp((selection.top + offsetY) * scaleY, 0, sourceCanvas.height - 1);
    const availableWidth = sourceCanvas.width - sx;
    const availableHeight = sourceCanvas.height - sy;
    const side = Math.max(2, Math.min(selection.size * scaleX, selection.size * scaleY, availableWidth, availableHeight));
    return {sx, sy, sw: side, sh: side};
  }

  function makeCaptureCanvas(sourceCanvas) {
    const crop = cropForCanvas(sourceCanvas);
    const side = Math.max(2, Math.min(CAPTURE_SIZE, Math.floor(crop.sw / 2) * 2));
    const canvas = document.createElement('canvas');
    canvas.width = side;
    canvas.height = side;
    const context = canvas.getContext('2d', {alpha: false});
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = 'high';
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, side, side);
    context.drawImage(sourceCanvas, crop.sx, crop.sy, crop.sw, crop.sh, 0, 0, side, side);
    return {canvas, context, crop};
  }

  async function normalizeMedia(blob, kind, sourceName) {
    const form = new FormData();
    form.append('kind', kind);
    form.append('media', blob, sourceName);
    const response = await fetch(appPath(`/api/projects/${encodeURIComponent(document.body.dataset.projectId)}/share-media/normalize`), {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      cache: 'no-store',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `${response.status} ${response.statusText}`);
    const mediaResponse = await fetch(result.url, {cache: 'no-store', credentials: 'same-origin'});
    if (!mediaResponse.ok) throw new Error(`Normalized media download failed: ${mediaResponse.status}`);
    return {
      blob: await mediaResponse.blob(),
      filename: result.filename,
      mimeType: result.mime_type,
      url: result.url,
      kind,
    };
  }

  function revokePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }

  function showPreview() {
    if (!activeMedia || !dialog || !dialogPreview) return;
    revokePreview();
    previewUrl = URL.createObjectURL(activeMedia.blob);
    dialogPreview.replaceChildren();
    const element = activeMedia.kind === 'video' ? document.createElement('video') : document.createElement('img');
    element.src = previewUrl;
    element.alt = activeMedia.kind === 'image' ? `Captured square from ${getProjectName()}` : '';
    if (element instanceof HTMLVideoElement) {
      element.controls = true;
      element.autoplay = true;
      element.loop = true;
      element.muted = true;
      element.playsInline = true;
    }
    dialogPreview.append(element);
    if (captionInput && !captionInput.value.trim()) captionInput.value = defaultCaption();
    dialog.showModal();
  }

  async function capturePhoto() {
    const sourceCanvas = getSourceCanvas();
    if (!sourceCanvas) throw new Error('The 3D renderer is not ready.');
    setStatus('Preparing photo…');
    const {canvas} = makeCaptureCanvas(sourceCanvas);
    const rawBlob = await new Promise((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Photo encoding failed.')), 'image/jpeg', 0.90);
    });
    const sourceName = `${safeBaseName(getProjectName())}-${timestampName()}.jpg`;
    try {
      activeMedia = await normalizeMedia(rawBlob, 'image', sourceName);
    } catch (error) {
      activeMedia = {blob: rawBlob, filename: sourceName, mimeType: 'image/jpeg', kind: 'image'};
      notify(`Server photo normalization was unavailable; using the browser JPEG. ${error.message}`, 9000);
    }
    setStatus(`Photo ready · ${(activeMedia.blob.size / 1024).toFixed(0)} KB · 1080 × 1080 maximum.`);
    setButtons();
    showPreview();
  }

  function drawRecordingFrame() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
    const sourceCanvas = getSourceCanvas();
    if (sourceCanvas && recordingContext && recordingCanvas && recordingCrop) {
      recordingContext.fillStyle = '#ffffff';
      recordingContext.fillRect(0, 0, recordingCanvas.width, recordingCanvas.height);
      recordingContext.drawImage(
        sourceCanvas,
        recordingCrop.sx,
        recordingCrop.sy,
        recordingCrop.sw,
        recordingCrop.sh,
        0,
        0,
        recordingCanvas.width,
        recordingCanvas.height,
      );
    }
    recordingAnimation = requestAnimationFrame(drawRecordingFrame);
  }

  function updateRecordingClock() {
    const seconds = Math.min(MAX_RECORDING_SECONDS, Math.floor((performance.now() - recordingStartedAt) / 1000));
    stopButton.textContent = `Stop ${seconds}s / ${MAX_RECORDING_SECONDS}s`;
    setStatus(`Recording selected square… ${seconds}s / ${MAX_RECORDING_SECONDS}s`);
    if (seconds >= MAX_RECORDING_SECONDS) stopRecording();
  }

  async function finishRecording(blob, mimeType) {
    setStatus('Converting recording to an Instagram-compatible MP4…');
    const extension = extensionForMime(mimeType || blob.type || 'video/webm');
    const sourceName = `${safeBaseName(getProjectName())}-${timestampName()}.${extension}`;
    try {
      activeMedia = await normalizeMedia(blob, 'video', sourceName);
    } catch (error) {
      activeMedia = {blob, filename: sourceName, mimeType: mimeType || blob.type || 'video/webm', kind: 'video'};
      notify(`MP4 conversion failed; the original browser recording is still available. ${error.message}`, 12000);
    }
    setStatus(`Recording ready · ${(activeMedia.blob.size / 1024 / 1024).toFixed(1)} MB · ${activeMedia.mimeType}.`);
    setButtons();
    showPreview();
  }

  async function startRecording() {
    if (!window.MediaRecorder) throw new Error('This browser does not support canvas recording.');
    const sourceCanvas = getSourceCanvas();
    if (!sourceCanvas) throw new Error('The 3D renderer is not ready.');
    const prepared = makeCaptureCanvas(sourceCanvas);
    recordingCanvas = prepared.canvas;
    recordingContext = prepared.context;
    recordingCrop = prepared.crop;
    recordingChunks = [];
    const stream = recordingCanvas.captureStream(RECORDING_FPS);
    const mimeType = recorderMimeType();
    const options = {videoBitsPerSecond: RECORDING_BITRATE};
    if (mimeType) options.mimeType = mimeType;
    mediaRecorder = new MediaRecorder(stream, options);
    mediaRecorder.addEventListener('dataavailable', event => {
      if (event.data?.size) recordingChunks.push(event.data);
    });
    mediaRecorder.addEventListener('stop', () => {
      cancelAnimationFrame(recordingAnimation);
      clearInterval(recordingTimer);
      stream.getTracks().forEach(track => track.stop());
      const recordedType = mediaRecorder.mimeType || mimeType || 'video/webm';
      const blob = new Blob(recordingChunks, {type: recordedType});
      mediaRecorder = null;
      recordingChunks = [];
      stopButton.textContent = `Stop 0s / ${MAX_RECORDING_SECONDS}s`;
      setButtons();
      finishRecording(blob, recordedType).catch(error => notify(error.message, 12000));
    }, {once: true});
    mediaRecorder.start(1000);
    recordingStartedAt = performance.now();
    recordingTimer = window.setInterval(updateRecordingClock, 250);
    drawRecordingFrame();
    updateRecordingClock();
    setButtons();
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  }

  function currentCaption() {
    return captionInput?.value.trim() || defaultCaption();
  }

  async function shareTo(target) {
    if (!activeMedia) throw new Error('Take a photo or recording first.');
    const file = mediaFile(activeMedia);
    const shareData = {
      title: getProjectName(),
      text: currentCaption(),
      files: [file],
    };
    const canUseNativeShare = Boolean(navigator.share && navigator.canShare?.(shareData));
    if (canUseNativeShare) {
      try {
        await navigator.share(shareData);
        notify(`Share sheet opened. Choose ${target === 'bluesky' ? 'Bluesky' : 'Instagram'}.`);
        return;
      } catch (error) {
        if (error?.name === 'AbortError') return;
        notify(`Native sharing was unavailable: ${error.message}`, 7000);
      }
    }

    downloadBlob(activeMedia.blob, activeMedia.filename);
    if (target === 'bluesky') {
      const intent = `https://bsky.app/intent/compose?text=${encodeURIComponent(currentCaption())}`;
      window.open(intent, '_blank', 'noopener,noreferrer');
      notify('The media was downloaded and Bluesky compose was opened. Attach the downloaded file to finish the post.', 10000);
    } else {
      window.open('https://www.instagram.com/', '_blank', 'noopener,noreferrer');
      notify('The media was downloaded and Instagram was opened. Use Create to upload the downloaded JPG or MP4.', 10000);
    }
  }

  function clearCapture() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') return;
    selection = null;
    activeMedia = null;
    revokePreview();
    renderSelection();
    if (dialog?.open) dialog.close();
    setStatus('Draw a square to capture the CAD view.');
    setButtons();
  }

  drawButton.addEventListener('click', beginDrawing);
  photoButton.addEventListener('click', () => capturePhoto().catch(error => notify(error.message, 9000)));
  recordButton.addEventListener('click', () => startRecording().catch(error => notify(error.message, 9000)));
  stopButton.addEventListener('click', stopRecording);
  previewButton.addEventListener('click', showPreview);
  blueskyButton.addEventListener('click', () => shareTo('bluesky').catch(error => notify(error.message, 9000)));
  instagramButton.addEventListener('click', () => shareTo('instagram').catch(error => notify(error.message, 9000)));
  downloadButton.addEventListener('click', () => activeMedia && downloadBlob(activeMedia.blob, activeMedia.filename));
  clearButton.addEventListener('click', clearCapture);
  dialogClose?.addEventListener('click', () => dialog?.close());
  dialog?.addEventListener('close', revokePreview);
  dialogBluesky?.addEventListener('click', () => shareTo('bluesky').catch(error => notify(error.message, 9000)));
  dialogInstagram?.addEventListener('click', () => shareTo('instagram').catch(error => notify(error.message, 9000)));
  dialogDownload?.addEventListener('click', () => activeMedia && downloadBlob(activeMedia.blob, activeMedia.filename));

  setStatus('Draw a square to capture the CAD view.');
  setButtons();

  return {
    clear: clearCapture,
    stop: stopRecording,
  };
}
"""

with open(file_path, "w", encoding="utf-8") as f:
    f.write(clean_code)

print("[+] share-capture.js successfully rewritten with valid ES module syntax.")
