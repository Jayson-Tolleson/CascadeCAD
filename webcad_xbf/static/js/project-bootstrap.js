(() => {
  const viewer = document.querySelector('#viewer');
  const message = viewer?.querySelector('.viewer-message');
  const moduleUrl = document.body.dataset.projectModule;
  const basePath = String(document.body.dataset.basePath || '').replace(/\/$/, '');
  const version = '0.7.0';
  const themeKey = 'cascade-cad-editor-theme';

  function resolveTheme(value) {
    if (value === 'system') return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    return value === 'dark' ? 'dark' : 'light';
  }

  const savedTheme = localStorage.getItem(themeKey) || 'light';
  document.documentElement.dataset.themeMode = savedTheme;
  document.documentElement.dataset.themeResolved = resolveTheme(savedTheme);

  function showFailure(error) {
    const detail = error instanceof Error ? error.message : String(error || 'unknown error');
    if (message) {
      message.textContent = `Editor failed to start: ${detail}`;
      message.classList.add('viewer-error');
    }
    console.error('CascadeCAD editor startup failed', error);
  }

  async function verifyModule(label, relativeUrl) {
    const url = `${basePath}/static/${relativeUrl}?v=${version}`;
    let response;
    try {
      response = await fetch(url, {cache: 'reload', credentials: 'same-origin'});
    } catch (error) {
      throw new Error(`${label} could not be fetched: ${error.message}`);
    }
    const contentType = response.headers.get('content-type') || 'missing content type';
    if (!response.ok) {
      throw new Error(`${label} returned HTTP ${response.status} at ${url}`);
    }
    if (!/(javascript|ecmascript)/i.test(contentType)) {
      throw new Error(`${label} has invalid MIME type ${contentType} at ${url}`);
    }
    try {
      await import(url);
    } catch (error) {
      throw new Error(`${label} import failed at ${url}: ${error.message}`);
    }
  }

  async function start() {
    if (!moduleUrl) throw new Error('project module URL is missing');
    const dependencies = [
      ['Three.js core', 'vendor/three/three.core.js'],
      ['Three.js WebGL module', 'vendor/three/three.module.js'],
      ['OrbitControls', 'vendor/three/OrbitControls.js'],
      ['TransformControls', 'vendor/three/TransformControls.js'],
      ['BufferGeometryUtils', 'vendor/three/BufferGeometryUtils.js'],
      ['GLTFLoader', 'vendor/three/GLTFLoader.js'],
    ];
    for (const [label, url] of dependencies) await verifyModule(label, url);
    await import(moduleUrl);
  }

  start().catch(showFailure);
})();
