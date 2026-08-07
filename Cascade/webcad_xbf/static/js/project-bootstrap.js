(() => {
  var viewer = document.querySelector('#viewer');
  var message = viewer ? viewer.querySelector('.viewer-message') : null;
  var moduleUrl = document.body.dataset.projectModule;
  var basePath = String(document.body.dataset.basePath || '').replace(/\$/, '');
  var version = '0.7.5';
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
    if (!relativeUrl) return '';
    var cleanPath = relativeUrl.split('?')[0];
    var url = basePath + '/static/' + cleanPath + "?v=" + version;
    
    try {
      var response = await fetch(url, { method: 'GET', headers: { 'Accept': 'application/javascript, */*' } });
      if (!response.ok) {
        throw new Error('HTTP ' + response.status + ' (' + response.statusText + ')');
      }
      return url;
    } catch (err) {
      throw new Error('Failed to load ' + label + ' (' + url + '): ' + err.message);
    }
  }

  async function start() {
    try {
      if (message) {
        message.textContent = 'Initializing CascadeCAD editor...';
      }

      await verifyModule('Viewport Module', 'js/viewport.js');
      await verifyModule('UI Core Module', 'js/ui_core.js');
      await verifyModule('Collaboration Module', 'js/collaboration.js');
      await verifyModule('Share Capture Module', 'js/share-capture.js');

      if (!moduleUrl) {
        throw new Error('No project module specified.');
      }
      var rawModule = moduleUrl || 'js/project.js';
      // Strip any query strings, encoded characters, and leading static/slash prefixes
      var cleanModulePath = decodeURIComponent(rawModule).split('?')[0].replace(/^(\/static\/|static\/|\/+)/, '');
      var resolvedModuleUrl = basePath + '/static/' + cleanModulePath + "?v=" + version;

      if (message) {
        message.textContent = 'Loading project module...';
      }

      await import(resolvedModuleUrl);
      if (message) {
        message.style.display = 'none';
      }
    } catch (error) {
      showFailure(error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
