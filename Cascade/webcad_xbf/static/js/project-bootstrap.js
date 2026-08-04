(() => {
  var viewer = document.querySelector('#viewer');
  var message = viewer ? viewer.querySelector('.viewer-message') : null;
  var moduleUrl = document.body.dataset.projectModule;
  var basePath = String(document.body.dataset.basePath || '').replace(/\/$/, '');
  var version = '0.7.0';
  var themeKey = 'cascade-cad-editor-theme';

  function resolveTheme(value) {
    if (value === 'system') return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    return value === 'dark' ? 'dark' : 'light';
  }

  var savedTheme = localStorage.getItem(themeKey) || 'light';
  document.documentElement.dataset.themeMode = savedTheme;
  document.documentElement.dataset.themeResolved = resolveTheme(savedTheme);

  function showFailure(error) {
    var detail = error instanceof Error ? error.message : String(error || 'unknown error');
    if (message) {
      message.textContent = 'Editor failed to start: ' + detail;
      message.classList.add('viewer-error');
    }
    console.error('CascadeCAD editor startup failed', error);
  }

  async function verifyModule(label, relativeUrl) {
    var url = basePath + '/static/' + relativeUrl + '?v=' + version;
    var response;
    try {
      response = await fetch(url, {cache: 'reload', credentials: 'same-origin'});
    } catch (error) {
      throw new Error(label + ' could not be fetched: ' + error.message);
    }
    var contentType = response.headers.get('content-type') || 'missing content type';
    if (!response.ok) {
      throw new Error(label + ' returned HTTP ' + response.status + ' at ' + url);
    }
    if (!/(javascript|ecmascript)/i.test(contentType)) {
      throw new Error(label + ' has invalid MIME type ' + contentType + ' at ' + url);
    }
    try {
      await import(url);
    } catch (error) {
      throw new Error(label + ' (' + relativeUrl + ') syntax error: ' + error.message);
    }
  }

  async function start() {
    if (!moduleUrl) throw new Error('project module URL is missing');
    var dependencies = [
      ['Three.js core', './vendor/three/three.core.js'],
      ['Three.js WebGL module', './vendor/three/three.module.js'],
      ['OrbitControls', './vendor/three/OrbitControls.js'],
      ['TransformControls', './vendor/three/TransformControls.js'],
      ['BufferGeometryUtils', './vendor/three/BufferGeometryUtils.js'],
      ['GLTFLoader', './vendor/three/GLTFLoader.js']
    ];
    for (var i = 0; i < dependencies.length; i++) {
      await verifyModule(dependencies[i][0], dependencies[i][1]);
    }
    try {
      await import(moduleUrl);
    } catch (error) {
      throw new Error('Main project module syntax error: ' + error.message);
    }
  }

  start().catch(showFailure);
})();
