import * as THREE from '../vendor/three/three.module.js?v=0.7.0';
import {OrbitControls} from '../vendor/three/OrbitControls.js?v=0.7.0';
import {TransformControls} from '../vendor/three/TransformControls.js?v=0.7.0';
import {GLTFLoader} from '../vendor/three/GLTFLoader.js?v=0.7.0';
import {initShareCapture} from './share-capture.js?v=0.7.0-collaboration';
import {initCollaboration} from './collaboration.js?v=0.7.0-collaboration';

const page = document.body.dataset;
const basePath = String(page.basePath || '').replace(/\/$/, '');
const projectId = page.projectId;
const viewer = document.querySelector('#viewer');
const stateElement = document.querySelector('#project-state');
const message = document.querySelector('#project-message');
const tree = document.querySelector('#assembly-tree');
const properties = document.querySelector('#properties');
const diagnosticsOverlay = document.querySelector('#renderer-diagnostics');
const selectionEmpty = document.querySelector('#selection-empty');
const selectionEditor = document.querySelector('#selection-editor');
const dirtyState = document.querySelector('#dirty-state');
const exportFormat = document.querySelector('#export-format');
const exportSelectedOnly = document.querySelector('#export-selected-only');
const exportButton = document.querySelector('#export-button');
const fastRender = document.querySelector('#fast-render');
const convertFacetedButton = document.querySelector('#convert-faceted-solids');
const cancelJobButton = document.querySelector('#cancel-job');
const commitEdits = document.querySelector('#commit-edits');
const undoButton = document.querySelector('#undo-edit');
const redoButton = document.querySelector('#redo-edit');
const isolateButton = document.querySelector('#isolate-selected');
const reloadMasterButton = document.querySelector('#reload-master');
const combineProjectsButton = document.querySelector('#combine-projects');
const combineDialog = document.querySelector('#combine-dialog');
const combineProjectList = document.querySelector('#combine-project-list');
const confirmCombineButton = document.querySelector('#confirm-combine');
const cancelCombineButton = document.querySelector('#cancel-combine');
const combinedProjectsSummary = document.querySelector('#combined-projects-summary');
const meshCleanupSummary = document.querySelector('#mesh-cleanup-summary');
const stepExportSummary = document.querySelector('#step-export-summary');
const facetedConversionSummary = document.querySelector('#faceted-conversion-summary');
const selectionCount = document.querySelector('#selection-count');
const modelDialog = document.querySelector('#model-dialog');
const modelForm = document.querySelector('#model-form');
const modelDialogTitle = document.querySelector('#model-dialog-title');
const modelDialogCopy = document.querySelector('#model-dialog-copy');
const modelFields = document.querySelector('#model-fields');
const cancelModelButton = document.querySelector('#cancel-model');
const toast = document.querySelector('#toast');
const ACTIVE_PROJECT_JOB_KEY = `cascadecad-project-job-${projectId}`;
const THEME_KEY = 'cascadecad-editor-theme';
const PREFERENCES_KEY = 'cascadecad-editor-preferences';
const TOOLBAR_LAYOUT_KEY = 'cascadecad-toolbar-layout';
const SELECTION_PANEL_KEY = 'cascadecad-selection-panel-open';
const themeSelect = document.querySelector('#theme-select');
const preferencesDialog = document.querySelector('#preferences-dialog');
const resolutionSelect = document.querySelector('#resolution-select');
const unitToggle = document.querySelector('#unit-toggle');
const partPropertiesForm = document.querySelector('#part-properties-form');
const partPropertiesEmpty = document.querySelector('#part-properties-empty');
const partNameField = document.querySelector('#part-name');
const materialNameField = document.querySelector('#material-name');
const materialDensityField = document.querySelector('#material-density');
const materialColorField = document.querySelector('#material-color');
const materialColorTextField = document.querySelector('#material-color-text');
const materialDescriptionField = document.querySelector('#material-description');
const inspectionResults = document.querySelector('#inspection-results');
const selectionPanel = document.querySelector('#selection-panel');
const openSelectionPanelButton = document.querySelector('#open-selection-panel');
const snapIndicator = document.querySelector('#snap-indicator');

const fields = {
  position: ['x', 'y', 'z'].map(axis => document.querySelector(`#position-${axis}`)),
  rotation: ['x', 'y', 'z'].map(axis => document.querySelector(`#rotation-${axis}`)),
  scale: ['x', 'y', 'z'].map(axis => document.querySelector(`#scale-${axis}`)),
};

let scene;
let camera;
let renderer;
let controls;
let transformControls;
let model;
let selectionBox;
let gridHelper;
let axesHelper;
let originHelper;
let snapMarker;
let renderRequested = false;
let lastFrameTime = performance.now();
let currentFps = 0;
let interactionAnimation = false;
let applyingSnap = false;
let refreshTimer = null;
const selectionBoxes = new Map();
let currentProject = null;
let componentsById = new Map();
let nodeById = new Map();
let selectedId = null;
const selectedIds = new Set();
let pendingModelOperation = null;
let activeJobId = null;
let activeJobCancellable = false;
let tool = 'select';
let isolateId = null;
let unitSystem = 'imperial';
let projectUnit = 'mm';
let displayUnit = 'in';
let exportUnit = 'mm';
let osnapEnabled = false;
let preferences = {
  resolution: 'medium', grid: true, origin: true, axes: true,
  keepSelectionPanel: true,
  renderingQuality: 'medium',
  triangleBudget: 25000000,
  showDiagnostics: true,
  lazyLoadMeshes: true,
  projectUnit: 'mm',
  displayUnit: 'in',
  exportUnit: 'mm',
  osnapModes: ['endpoint', 'midpoint', 'center', 'intersection', 'perpendicular', 'tangent', 'nearest', 'grid', 'origin', 'axis'],
};
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function appPath(path) {
    if (!path) return "/CascadeCAD/";
    while (path.includes("/CascadeCAD/CascadeCAD/")) {
        path = path.replace("/CascadeCAD/CascadeCAD/", "/CascadeCAD/");
    }
    if (path.startsWith("/CascadeCAD/")) return path;
    return "/CascadeCAD" + (path.startsWith("/") ? "" : "/") + path;
}

function notify(text, timeout = 5000) {
  toast.textContent = text;
  toast.hidden = false;
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => { toast.hidden = true; }, timeout);
}

async function getJson(url, options = {}) {
  const targetUrl = (typeof appPath === 'function' && url.startsWith('/')) ? appPath(url) : url;
  const response = await fetch(targetUrl, {
    cache: 'no-store',
    credentials: 'same-origin',
    ...options,
    headers: {Accept: 'application/json', ...(options.headers || {})},
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

function radToDeg(value) { return value * 180 / Math.PI; }
function degToRad(value) { return value * Math.PI / 180; }
function rounded(value, digits = 5) { return Number(Number(value).toFixed(digits)); }

const MATERIAL_PRESETS = {
  'Unassigned': {density_kg_m3: 0, color: '#b8c0c8', description: ''},
  'Aluminum 6061-T6': {density_kg_m3: 2700, color: '#c8ced3', description: 'Aluminum 6061-T6'},
  'Marine Aluminum 5083': {density_kg_m3: 2660, color: '#bec8cf', description: 'Marine aluminum 5083'},
  'Steel': {density_kg_m3: 7850, color: '#7f8992', description: 'Carbon steel'},
  'Stainless Steel': {density_kg_m3: 8000, color: '#b6bec5', description: 'Stainless steel'},
  'ABS': {density_kg_m3: 1040, color: '#353a40', description: 'ABS plastic'},
  'Custom': {density_kg_m3: 0, color: '#b8c0c8', description: ''},
};
const LENGTH_PARAMETER_NAMES = new Set([
  'length', 'width', 'height', 'radius', 'outer_radius', 'inner_radius', 'major_radius', 'minor_radius',
  'radius1', 'radius2', 'x_radius', 'y_radius', 'distance', 'offset', 'spacing', 'pitch',
  'axis_start_x', 'axis_start_y', 'axis_start_z', 'axis_end_x', 'axis_end_y', 'axis_end_z',
  'center_x', 'center_y', 'center_z', 'position_x', 'position_y', 'position_z', 'distance2',
]);

const UNIT_FACTORS_MM = {in: 25.4, ft: 304.8, 'ft-in': 25.4, yd: 914.4, mm: 1, cm: 10, m: 1000};
function unitFactor(unit) { return UNIT_FACTORS_MM[unit] || 1; }
function fromDisplayLength(value) { return Number(value) * unitFactor(displayUnit); }
function toDisplayLength(value) { return Number(value) / unitFactor(displayUnit); }
function displayUnitLabel() { return displayUnit === 'ft-in' ? 'ft/in' : displayUnit; }
function formatLength(value) { return `${rounded(toDisplayLength(value), 5)} ${displayUnitLabel()}`; }

function requestRender() {
  if (!renderer || !scene || !camera || renderRequested) return;
  renderRequested = true;
  requestAnimationFrame(() => {
    renderRequested = false;
    controls?.update();
    renderer.info.reset();
    renderer.render(scene, camera);
    updateRendererDiagnostics();
  });
}

function startInteractionRender() {
  if (interactionAnimation) return;
  interactionAnimation = true;
  const loop = () => {
    if (!interactionAnimation) return;
    controls?.update();
    renderer?.info?.reset?.();
    renderer?.render(scene, camera);
    updateRendererDiagnostics();
    requestAnimationFrame(loop);
  };
  loop();
}

function updateRendererDiagnostics() {
  if (!diagnosticsOverlay || !renderer) return;
  diagnosticsOverlay.hidden = !preferences.showDiagnostics;
  if (diagnosticsOverlay.hidden) return;
  const now = performance.now();
  const delta = Math.max(1, now - lastFrameTime);
  currentFps = currentFps ? (currentFps * 0.8 + (1000 / delta) * 0.2) : 1000 / delta;
  lastFrameTime = now;
  const memory = renderer.info.memory || {};
  const render = renderer.info.render || {};
  const triangles = model?.userData?.totalTriangleCount || render.triangles || 0;
  const heap = performance?.memory?.usedJSHeapSize ? `${(performance.memory.usedJSHeapSize / 1048576).toFixed(0)} MB heap` : 'CPU n/a';
  diagnosticsOverlay.textContent = `FPS ${currentFps.toFixed(0)} · Triangles ${Number(triangles).toLocaleString()} · GPU geom ${memory.geometries || 0} tex ${memory.textures || 0} · ${heap} · Draw calls ${render.calls || 0}`;
}

function stopInteractionRender() {
  interactionAnimation = false;
  requestRender();
}

function loadPreferences() {
  try {
    const stored = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}');
    preferences = {...preferences, ...stored};
    if (!Array.isArray(preferences.osnapModes)) preferences.osnapModes = ['endpoint', 'midpoint', 'center', 'grid', 'origin'];
  } catch { /* use defaults */ }
  projectUnit = preferences.projectUnit || 'mm';
  displayUnit = preferences.displayUnit || (localStorage.getItem('cascadecad-unit-system') === 'metric' ? 'mm' : 'in');
  exportUnit = preferences.exportUnit || displayUnit;
  unitSystem = ['in', 'ft', 'ft-in', 'yd'].includes(displayUnit) ? 'imperial' : 'metric';
}

function savePreferences() {
  localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
}

function resolutionPixelRatio() {
  const quality = preferences.renderingQuality || preferences.resolution;
  const cap = {low: 0.75, medium: 1, good: 1.5, exceptional: 2}[quality] || 1;
  return Math.min(window.devicePixelRatio || 1, cap);
}

function normalizeName(value) {
  return String(value || '').trim().replace(/[^A-Za-z0-9._-]+/g, '_');
}

function resolveTheme(value) {
  if (value === 'system') return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  return value === 'dark' ? 'dark' : 'light';
}

function applyTheme(value, persist = true) {
  const mode = ['light', 'dark', 'system'].includes(value) ? value : 'light';
  const resolved = resolveTheme(mode);
  document.documentElement.dataset.themeMode = mode;
  document.documentElement.dataset.themeResolved = resolved;
  document.documentElement.style.colorScheme = resolved;
  if (themeSelect) themeSelect.value = mode;
  if (persist) localStorage.setItem(THEME_KEY, mode);
  if (scene) scene.background = new THREE.Color(resolved === 'dark' ? 0x101419 : 0xffffff);
  if (gridHelper && scene) {
    scene.remove(gridHelper);
    gridHelper.geometry?.dispose?.();
    const materials = Array.isArray(gridHelper.material) ? gridHelper.material : [gridHelper.material];
    materials.filter(Boolean).forEach(material => material.dispose?.());
    gridHelper = new THREE.GridHelper(1000, 50, resolved === 'dark' ? 0x45515d : 0x83909a, resolved === 'dark' ? 0x252d35 : 0xd9e0e5);
    gridHelper.visible = Boolean(preferences.grid);
    scene.add(gridHelper);
  }
  requestRender();
}

function initViewer() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(resolveTheme(localStorage.getItem(THEME_KEY) || 'light') === 'dark' ? 0x101419 : 0xffffff);
  camera = new THREE.PerspectiveCamera(45, 1, 0.001, 100000000);
  camera.position.set(4, 3, 5);
  renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: false});
  renderer.info.autoReset = false;
  renderer.setPixelRatio(resolutionPixelRatio());
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  viewer.querySelector('.viewer-message')?.remove();
  viewer.prepend(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.addEventListener('start', startInteractionRender);
  controls.addEventListener('change', requestRender);
  controls.addEventListener('end', stopInteractionRender);

  transformControls = new TransformControls(camera, renderer.domElement);
  scene.add(transformControls.getHelper());
  transformControls.addEventListener('dragging-changed', event => {
    controls.enabled = !event.value;
    if (event.value) startInteractionRender(); else stopInteractionRender();
  });
  transformControls.addEventListener('objectChange', () => {
    if (selectedId) {
      if (tool === 'move' && osnapEnabled) applyContextualSnap();
      updateTransformFieldsFromNode();
    }
    selectionBox?.update();
    requestRender();
  });

  scene.add(new THREE.HemisphereLight(0xffffff, 0x303840, 2.0));
  const light = new THREE.DirectionalLight(0xffffff, 2.5);
  light.position.set(3, 5, 4);
  scene.add(light);
  const resolvedTheme = resolveTheme(localStorage.getItem(THEME_KEY) || 'light');
  gridHelper = new THREE.GridHelper(1000, 50, resolvedTheme === 'dark' ? 0x45515d : 0x83909a, resolvedTheme === 'dark' ? 0x252d35 : 0xd9e0e5);
  gridHelper.visible = Boolean(preferences.grid);
  scene.add(gridHelper);
  axesHelper = new THREE.AxesHelper(140);
  axesHelper.visible = Boolean(preferences.axes);
  scene.add(axesHelper);
  originHelper = new THREE.Mesh(
    new THREE.SphereGeometry(3, 16, 12),
    new THREE.MeshBasicMaterial({color: 0xffcc33, depthTest: false})
  );
  originHelper.renderOrder = 999;
  originHelper.visible = Boolean(preferences.origin);
  scene.add(originHelper);
  snapMarker = new THREE.Mesh(
    new THREE.SphereGeometry(2.2, 12, 8),
    new THREE.MeshBasicMaterial({color: 0x25e7ff, depthTest: false})
  );
  snapMarker.visible = false;
  snapMarker.renderOrder = 1000;
  scene.add(snapMarker);

  const resize = () => {
    const rect = viewer.getBoundingClientRect();
    camera.aspect = rect.width / Math.max(1, rect.height);
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(resolutionPixelRatio());
    renderer.setSize(rect.width, rect.height, false);
    requestRender();
  };
  new ResizeObserver(resize).observe(viewer);
  resize();
  renderer.domElement.addEventListener('pointerdown', selectFromPointer);
  requestRender();
}

function disposeModel() {
  clearSelection();
  if (!model) return;
  scene.remove(model);
  model.traverse(object => {
    object.geometry?.dispose?.();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach(material => material.dispose?.());
  });
  model = null;
  nodeById.clear();
}

function fitView(target = model) {
  if (!target) return;
  const box = new THREE.Box3().setFromObject(target);
  if (box.isEmpty()) return;
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const max = Math.max(size.x, size.y, size.z, 1e-6);
  controls.target.copy(center);
  camera.near = Math.max(max / 100000, 0.0001);
  camera.far = Math.max(max * 1000, 1000);
  camera.position.copy(center).add(new THREE.Vector3(max * 1.2, max * 0.8, max * 1.2));
  camera.updateProjectionMatrix();
  controls.update();
  requestRender();
}

async function loadPreview() {
  disposeModel();
  const loader = new GLTFLoader();
  const revision = encodeURIComponent(currentProject?.revision_id || currentProject?.updated_at || 'current');
  const gltf = await loader.loadAsync(appPath(`/api/projects/${projectId}/preview?rev=${revision}`));
  model = gltf.scene;
  prepareRenderableModel(model);
  scene.add(model);
  indexComponentNodes();
  syncSceneFromComponents();
  fitView();
}

function meshTriangleCount(mesh) {
  const geometry = mesh?.geometry;
  if (!geometry) return 0;
  if (geometry.index) return Math.floor(geometry.index.count / 3);
  const position = geometry.getAttribute?.('position');
  return position ? Math.floor(position.count / 3) : 0;
}

function prepareRenderableModel(root) {
  let cumulative = 0;
  const budget = Number(preferences.triangleBudget || 25000000);
  root.traverse(object => {
    if (!object.isMesh) return;
    object.frustumCulled = true;
    const triangles = meshTriangleCount(object);
    object.userData.triangleCount = triangles;
    cumulative += triangles;
    if (preferences.lazyLoadMeshes && cumulative > budget) {
      object.visible = false;
      object.userData.lazyHidden = true;
    }
  });
  root.userData.totalTriangleCount = cumulative;
  if (cumulative > budget) notify(`Triangle budget ${budget.toLocaleString()} exceeded; overflow meshes are lazy-hidden until quality is raised.`, 9000);
}

function allNamedObjects() {
  const exact = new Map();
  const normalized = new Map();
  model?.traverse(object => {
    if (!object.name) return;
    if (!exact.has(object.name)) exact.set(object.name, object);
    const clean = normalizeName(object.name);
    if (!normalized.has(clean)) normalized.set(clean, object);
  });
  return {exact, normalized};
}

function findNodeForComponent(component, names) {
  const candidates = [component.id, component.name, normalizeName(component.id), normalizeName(component.name)];
  for (const candidate of candidates) {
    if (names.exact.has(candidate)) return names.exact.get(candidate);
    if (names.normalized.has(normalizeName(candidate))) return names.normalized.get(normalizeName(candidate));
  }
  return null;
}

function markNode(node, componentId) {
  node.userData.cascadeComponentId = componentId;
  node.traverse(child => { child.userData.cascadeComponentId = componentId; });
  if (!node.userData.editorBase) {
    node.userData.editorBase = {
      position: node.position.clone(),
      rotation: node.rotation.clone(),
      scale: node.scale.clone(),
    };
  }
}

function commonAncestor(nodes) {
  if (!nodes.length) return null;
  const chains = nodes.map(node => {
    const chain = [];
    let current = node;
    while (current) { chain.unshift(current); current = current.parent; }
    return chain;
  });
  let common = null;
  for (let index = 0; index < Math.min(...chains.map(chain => chain.length)); index += 1) {
    const candidate = chains[0][index];
    if (chains.every(chain => chain[index] === candidate)) common = candidate; else break;
  }
  return common;
}

function indexComponentNodes() {
  nodeById.clear();
  if (!model) return;
  const names = allNamedObjects();
  for (const component of componentsById.values()) {
    if (component.duplicate) continue;
    const node = findNodeForComponent(component, names);
    if (!node) continue;
    markNode(node, component.id);
    nodeById.set(component.id, node);
  }

  // Some GLB exporters omit a shape-less assembly wrapper node. Recover a
  // selectable tree-level project group from the common ancestor of its mapped
  // children, without overwriting the children's click-selection identifiers.
  const pending = [...componentsById.values()].filter(component => !component.duplicate && !nodeById.has(component.id));
  for (const component of pending) {
    const childNodes = [...componentsById.values()]
      .filter(child => child.parent === component.id)
      .map(child => nodeById.get(child.id))
      .filter(Boolean);
    const node = commonAncestor(childNodes);
    if (!node || node === model || childNodes.includes(node)) continue;
    if (!node.userData.editorBase) {
      node.userData.editorBase = {
        position: node.position.clone(),
        rotation: node.rotation.clone(),
        scale: node.scale.clone(),
      };
    }
    nodeById.set(component.id, node);
  }
}

function componentScale(component, node) {
  const bounds = component?.bbox;
  if (!bounds || !node) return 1;
  const cadSize = bounds.max.map((value, index) => Math.abs(Number(value) - Number(bounds.min[index])));
  const box = new THREE.Box3().setFromObject(node);
  const viewSizeVector = box.getSize(new THREE.Vector3());
  const viewSize = [viewSizeVector.x, viewSizeVector.y, viewSizeVector.z];
  const ratios = cadSize.map((value, index) => value > 1e-9 && viewSize[index] > 1e-9 ? value / viewSize[index] : null)
    .filter(value => Number.isFinite(value));
  if (!ratios.length) return 1;
  ratios.sort((a, b) => a - b);
  return ratios[Math.floor(ratios.length / 2)] || 1;
}

function applyComponentTransform(component, node) {
  const base = node.userData.editorBase;
  if (!base) return;
  node.position.copy(base.position);
  node.rotation.copy(base.rotation);
  node.scale.copy(base.scale);
  const cadScale = componentScale(component, node);
  node.userData.cadUnitsPerViewerUnit = cadScale;
  const baseCad = component.base_transform || component.transform;
  const currentCad = component.transform || baseCad;
  const deltaPosition = currentCad.position.map((value, index) => Number(value) - Number(baseCad.position[index]));
  const deltaRotation = currentCad.rotation.map((value, index) => Number(value) - Number(baseCad.rotation[index]));
  node.position.x += deltaPosition[0] / cadScale;
  node.position.y += deltaPosition[1] / cadScale;
  node.position.z += deltaPosition[2] / cadScale;
  node.rotation.x += degToRad(deltaRotation[0]);
  node.rotation.y += degToRad(deltaRotation[1]);
  node.rotation.z += degToRad(deltaRotation[2]);
  const baseScaleCad = baseCad.scale || [1, 1, 1];
  const currentScaleCad = currentCad.scale || baseScaleCad;
  node.scale.set(
    base.scale.x * Number(currentScaleCad[0] || 1) / Number(baseScaleCad[0] || 1),
    base.scale.y * Number(currentScaleCad[1] || 1) / Number(baseScaleCad[1] || 1),
    base.scale.z * Number(currentScaleCad[2] || 1) / Number(baseScaleCad[2] || 1),
  );
  node.updateMatrixWorld(true);
}

function applyComponentMaterial(component, node) {
  const color = component?.material?.color;
  if (!color || !node) return;
  node.traverse(child => {
    if (!child.isMesh || !child.material) return;
    if (!child.userData.cascadeOriginalMaterial) {
      child.userData.cascadeOriginalMaterial = child.material;
      child.material = child.material.clone();
    }
    if (child.material?.color) child.material.color.set(color);
    child.material.needsUpdate = true;
  });
}

function removeEditorDuplicates() {
  if (!model) return;
  const duplicates = [];
  model.traverse(object => {
    if (object.userData.editorDuplicate) duplicates.push(object);
  });
  duplicates.forEach(object => object.parent?.remove(object));
}

function createDuplicateNode(component) {
  const source = nodeById.get(component.source_id);
  if (!source || !source.parent) return null;
  const clone = source.clone(true);
  clone.name = component.id;
  clone.userData = {...clone.userData, editorDuplicate: true};
  clone.userData.editorBase = {
    position: source.userData.editorBase.position.clone(),
    rotation: source.userData.editorBase.rotation.clone(),
    scale: source.userData.editorBase.scale.clone(),
  };
  source.parent.add(clone);
  markNode(clone, component.id);
  return clone;
}

function syncSceneFromComponents() {
  if (!model) return;
  removeEditorDuplicates();
  indexComponentNodes();

  for (const component of componentsById.values()) {
    let node = nodeById.get(component.id);
    if (component.duplicate && !component.deleted) {
      node = createDuplicateNode(component);
      if (node) nodeById.set(component.id, node);
    }
    if (!node) continue;
    applyComponentTransform(component, node);
    applyComponentMaterial(component, node);
    const hidden = component.visible === false;
    const isolatedOut = isolateId && isolateId !== component.id;
    node.visible = !component.deleted && !hidden && !isolatedOut;
  }
  for (const id of [...selectedIds]) {
    if (!componentsById.has(id) || componentsById.get(id).deleted) selectedIds.delete(id);
  }
  if (selectedId && !selectedIds.has(selectedId)) selectedId = [...selectedIds].at(-1) || null;
  if (!selectedId) clearSelection();
  else { renderSelectionHelpers(); renderSelectionProperties(); attachTool(); }
  renderTree();
  requestRender();
}

function componentFromObject(object) {
  let current = object;
  while (current && current !== model) {
    const id = current.userData.cascadeComponentId;
    if (id && componentsById.has(id)) return id;
    current = current.parent;
  }
  return null;
}

function selectFromPointer(event) {
  if (!model || transformControls.dragging) return;
  if (event.button !== 0) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObject(model, true).find(item => item.object.visible);
  if (!hit) {
    if (tool === 'select' && !event.ctrlKey && !event.shiftKey) clearSelection();
    return;
  }
  const componentId = componentFromObject(hit.object);
  if (componentId) selectComponent(componentId, {fit: false, additive: event.ctrlKey || event.shiftKey});
}

function disposeSelectionBoxes() {
  for (const helper of selectionBoxes.values()) {
    scene.remove(helper);
    helper.geometry?.dispose?.();
    helper.material?.dispose?.();
  }
  selectionBoxes.clear();
  selectionBox = null;
}

function syncExportControls() {
  const busy = ['queued', 'processing', 'uploading'].includes(currentProject?.status) || Boolean(activeJobId);
  if (exportButton) exportButton.disabled = busy;
  if (exportFormat) exportFormat.disabled = busy;
  if (fastRender) fastRender.disabled = busy;
  if (convertFacetedButton) {
    const kind = String(currentProject?.geometry_kind || 'unknown');
    convertFacetedButton.disabled = busy || ['exact', 'faceted-brep'].includes(kind);
  }
  if (exportSelectedOnly) {
    exportSelectedOnly.disabled = busy || selectedIds.size === 0;
    if (selectedIds.size === 0) exportSelectedOnly.checked = false;
  }
  if (cancelJobButton) cancelJobButton.hidden = !(activeJobId && activeJobCancellable);
}

function clearSelection() {
  selectedId = null;
  selectedIds.clear();
  transformControls?.detach();
  disposeSelectionBoxes();
  selectionEmpty.hidden = false;
  selectionEditor.hidden = true;
  clearPartProperties();
  isolateButton.disabled = true;
  tree?.querySelectorAll('.tree-item.selected').forEach(button => button.classList.remove('selected'));
  syncExportControls();
}

function renderSelectionHelpers() {
  disposeSelectionBoxes();
  for (const id of selectedIds) {
    const node = nodeById.get(id);
    if (!node) continue;
    const helper = new THREE.BoxHelper(node, id === selectedId ? 0x39d7ff : 0xffb347);
    selectionBoxes.set(id, helper);
    scene.add(helper);
  }
  selectionBox = selectedId ? selectionBoxes.get(selectedId) : null;
}

function selectComponent(componentId, options = {}) {
  const component = componentsById.get(componentId);
  const node = nodeById.get(componentId);
  if (!component || component.deleted || !node) {
    notify('The selected component is not present in the current preview.');
    return;
  }
  const additive = Boolean(options.additive);
  if (!additive) selectedIds.clear();
  if (additive && selectedIds.has(componentId)) {
    selectedIds.delete(componentId);
    if (selectedId === componentId) selectedId = [...selectedIds].at(-1) || null;
  } else {
    selectedIds.add(componentId);
    selectedId = componentId;
  }
  if (!selectedId) { clearSelection(); return; }
  transformControls?.detach();
  renderSelectionHelpers();
  selectionEmpty.hidden = true;
  selectionEditor.hidden = false;
  isolateButton.disabled = false;
  renderSelectionProperties();
  syncExportControls();
  attachTool();
  renderTree();
  if (options.fit) fitView(nodeById.get(selectedId));
}

function attachTool() {
  if (!selectedId) return;
  const node = nodeById.get(selectedId);
  if (!node) return;
  if (tool === 'move') {
    transformControls.setMode('translate');
    transformControls.setSpace('local');
    transformControls.attach(node);
  } else if (tool === 'rotate') {
    transformControls.setMode('rotate');
    transformControls.setSpace('local');
    transformControls.attach(node);
  } else if (tool === 'scale') {
    transformControls.setMode('scale');
    transformControls.setSpace('local');
    transformControls.attach(node);
  } else {
    transformControls.detach();
  }
  requestRender();
}

function transformFromNode(component, node) {
  const baseViewer = node.userData.editorBase;
  const cadScale = Number(node.userData.cadUnitsPerViewerUnit || 1);
  const baseCad = component.base_transform || component.transform;
  const baseScaleCad = baseCad.scale || [1, 1, 1];
  return {
    position: [
      Number(baseCad.position[0]) + (node.position.x - baseViewer.position.x) * cadScale,
      Number(baseCad.position[1]) + (node.position.y - baseViewer.position.y) * cadScale,
      Number(baseCad.position[2]) + (node.position.z - baseViewer.position.z) * cadScale,
    ].map(value => rounded(value, 5)),
    rotation: [
      Number(baseCad.rotation[0]) + radToDeg(node.rotation.x - baseViewer.rotation.x),
      Number(baseCad.rotation[1]) + radToDeg(node.rotation.y - baseViewer.rotation.y),
      Number(baseCad.rotation[2]) + radToDeg(node.rotation.z - baseViewer.rotation.z),
    ].map(value => rounded(value, 5)),
    scale: [
      Number(baseScaleCad[0] || 1) * node.scale.x / Math.max(1e-12, baseViewer.scale.x),
      Number(baseScaleCad[1] || 1) * node.scale.y / Math.max(1e-12, baseViewer.scale.y),
      Number(baseScaleCad[2] || 1) * node.scale.z / Math.max(1e-12, baseViewer.scale.z),
    ].map(value => rounded(value, 5)),
  };
}

function updateTransformFields(transform) {
  fields.position.forEach((field, index) => { field.value = rounded(toDisplayLength(transform.position[index]), 5).toFixed(5); });
  fields.rotation.forEach((field, index) => { field.value = rounded(transform.rotation[index], 5).toFixed(5); });
  fields.scale.forEach((field, index) => { field.value = rounded((transform.scale || [1, 1, 1])[index], 5).toFixed(5); });
}

function updateTransformFieldsFromNode() {
  const component = componentsById.get(selectedId);
  const node = nodeById.get(selectedId);
  if (!component || !node) return;
  updateTransformFields(transformFromNode(component, node));
}

function transformFromFields() {
  return {
    position: fields.position.map(field => fromDisplayLength(field.value)),
    rotation: fields.rotation.map(field => Number(field.value)),
    scale: fields.scale.map(field => Math.max(0.000001, Number(field.value))),
  };
}

function applyFieldTransformToNode() {
  const component = componentsById.get(selectedId);
  const node = nodeById.get(selectedId);
  if (!component || !node) return;
  const draft = {...component, transform: transformFromFields()};
  applyComponentTransform(draft, node);
  selectionBox?.update();
  requestRender();
}

function populatePartProperties(component) {
  if (!partPropertiesForm || !partPropertiesEmpty) return;
  partPropertiesEmpty.hidden = true;
  partPropertiesForm.hidden = false;
  if (partNameField) partNameField.value = component.name || '';
  const material = component.material || {};
  const known = Object.hasOwn(MATERIAL_PRESETS, material.name) ? material.name : 'Custom';
  if (materialNameField) materialNameField.value = known;
  if (materialDensityField) materialDensityField.value = Number(material.density_kg_m3 || 0);
  const color = /^#[0-9a-f]{6}$/i.test(material.color || '') ? material.color : '#b8c0c8';
  if (materialColorField) materialColorField.value = color;
  if (materialColorTextField) materialColorTextField.value = color;
  if (materialDescriptionField) materialDescriptionField.value = material.description || '';
}

function clearPartProperties() {
  if (partPropertiesEmpty) partPropertiesEmpty.hidden = false;
  if (partPropertiesForm) partPropertiesForm.hidden = true;
}

function renderSelectionProperties() {
  const component = componentsById.get(selectedId);
  const node = nodeById.get(selectedId);
  if (!component || !node) return;
  if (selectionCount) selectionCount.textContent = selectedIds.size > 1 ? `${selectedIds.size} parts selected · primary: ${component.name}` : '1 part selected';
  const material = component.material || {};
  properties.innerHTML = `
    <dt>Name</dt><dd>${escapeHtml(component.name)}</dd>
    <dt>ID</dt><dd>${escapeHtml(component.id)}</dd>
    <dt>Type</dt><dd>${escapeHtml(component.kind || '')}</dd>
    <dt>Shape</dt><dd>${escapeHtml(component.shape_type || 'mesh')}</dd>
    <dt>Triangles</dt><dd>${component.triangles ?? '—'}</dd>
    <dt>Material</dt><dd>${escapeHtml(material.name || 'Unassigned')}</dd>
    <dt>Visible</dt><dd>${component.visible === false ? 'No' : 'Yes'}</dd>
    <dt>Parent</dt><dd>${escapeHtml(component.parent || 'root')}</dd>`;
  updateTransformFieldsFromNode();
  populatePartProperties(component);
  document.querySelector('#split-selected').disabled = ['mesh', 'mixed'].includes(currentProject?.geometry_kind) || selectedIds.size !== 1;
}

function componentDepth(component) {
  let depth = 0;
  let current = component;
  const seen = new Set();
  while (current?.parent && !seen.has(current.parent)) {
    seen.add(current.parent);
    depth += 1;
    current = componentsById.get(current.parent);
  }
  return depth;
}

function renderTree() {
  const components = [...componentsById.values()].filter(component => !component.deleted);
  if (!components.length) {
    tree.innerHTML = '<p>No editable components available.</p>';
    return;
  }
  tree.innerHTML = components.map(component => {
    const hidden = component.visible === false || (isolateId && isolateId !== component.id);
    return `<div class="tree-row" style="--tree-depth:${componentDepth(component)}">
      <button class="tree-visibility" data-visibility-id="${escapeHtml(component.id)}" title="Toggle visibility">${hidden ? '○' : '●'}</button>
      <button class="tree-item ${selectedIds.has(component.id) ? 'selected' : ''}" data-component-id="${escapeHtml(component.id)}">
        <span>${escapeHtml(component.name)}</span><small>${escapeHtml(component.kind || 'unknown')}</small>
      </button>
    </div>`;
  }).join('');
}

function setupTreeDelegation() {
  tree?.addEventListener('click', event => {
    const visibility = event.target.closest('.tree-visibility');
    if (visibility) {
      toggleComponentVisibility([visibility.dataset.visibilityId]).catch(error => notify(error.message));
      return;
    }
    const item = event.target.closest('.tree-item');
    if (item) selectComponent(item.dataset.componentId, {fit: false, additive: event.ctrlKey || event.shiftKey});
  });
  tree?.addEventListener('dblclick', event => {
    const item = event.target.closest('.tree-item');
    if (item) selectComponent(item.dataset.componentId, {fit: true});
  });
}

function setTool(nextTool) {
  tool = nextTool;
  for (const name of ['select', 'move', 'rotate', 'scale']) {
    document.querySelector(`#tool-${name}`)?.classList.toggle('active', name === tool);
  }
  attachTool();
}

async function openCombineDialog() {
  if (!combineDialog || !combineProjectList) return;
  combineProjectList.innerHTML = '<p>Loading projects…</p>';
  confirmCombineButton.disabled = true;
  combineDialog.showModal();
  try {
    const data = await getJson(appPath('/api/projects'));
    const available = (data.projects || []).filter(project =>
      project.id !== projectId && project.status === 'ready' && project.master_xbf
    );
    if (!available.length) {
      combineProjectList.innerHTML = '<p>No other ready projects are available.</p>';
      return;
    }
    combineProjectList.innerHTML = available.map(project => `
      <label class="combine-project-option">
        <input type="checkbox" value="${escapeHtml(project.id)}">
        <span><b>${escapeHtml(project.name)}</b><small>${escapeHtml(project.source_filename || '')}</small></span>
        <span class="state-pill ${escapeHtml(project.status)}">${escapeHtml(project.geometry_kind || 'unknown')}</span>
      </label>`).join('');
    const updateButton = () => {
      confirmCombineButton.disabled = !combineProjectList.querySelector('input:checked');
    };
    combineProjectList.querySelectorAll('input').forEach(input => input.addEventListener('change', updateButton));
  } catch (error) {
    combineProjectList.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

async function combineSelectedProjects() {
  const sourceProjectIds = [...combineProjectList.querySelectorAll('input:checked')].map(input => input.value);
  if (!sourceProjectIds.length) return;
  if (currentProject?.editor?.dirty) {
    const proceed = confirm('Combining projects will also commit the current working edits into master.xbf. Continue?');
    if (!proceed) return;
  }
  confirmCombineButton.disabled = true;
  try {
    const result = await getJson(appPath(`/api/projects/${projectId}/combine`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_project_ids: sourceProjectIds}),
    });
    combineDialog.close();
    clearSelection();
    await watchJob(result.job);
    await refreshProject({reloadPreview: true});
    notify(`Added ${sourceProjectIds.length} project${sourceProjectIds.length === 1 ? '' : 's'} to this assembly.`);
  } catch (error) {
    notify(error.message);
    confirmCombineButton.disabled = false;
  }
}


const MODEL_SCHEMAS = {
  box: {
    title: 'Create box', copy: 'Creates a centered exact B-rep box. Move it afterward with the gizmo.',
    fields: [['name', 'Name', 'Box', 'text'], ['length', 'Length', 100, 'number'], ['width', 'Width', 100, 'number'], ['height', 'Height', 100, 'number']],
  },
  cylinder: {
    title: 'Create cylinder', copy: 'Creates an exact cylinder along the Z axis.',
    fields: [['name', 'Name', 'Cylinder', 'text'], ['radius', 'Radius', 50, 'number'], ['height', 'Height', 100, 'number']],
  },
  pipe: {
    title: 'Create pipe', copy: 'Creates a hollow exact cylinder by subtracting an inner cylinder.',
    fields: [['name', 'Name', 'Pipe', 'text'], ['outer_radius', 'Outer radius', 50, 'number'], ['inner_radius', 'Inner radius', 40, 'number'], ['height', 'Height', 100, 'number']],
  },
  sphere: {
    title: 'Create sphere', copy: 'Creates an exact B-rep sphere.',
    fields: [['name', 'Name', 'Sphere', 'text'], ['radius', 'Radius', 50, 'number']],
  },
  torus: {
    title: 'Create torus', copy: 'Creates an exact torus around the Z axis.',
    fields: [['name', 'Name', 'Torus', 'text'], ['major_radius', 'Major radius', 75, 'number'], ['minor_radius', 'Tube radius', 15, 'number']],
  },
  cone: {
    title: 'Create cone', copy: 'Creates an exact cone or truncated cone along the Z axis.',
    fields: [['name', 'Name', 'Cone', 'text'], ['radius1', 'Bottom radius', 50, 'number'], ['radius2', 'Top radius', 0, 'number'], ['height', 'Height', 100, 'number']],
  },
  line: {
    title: 'Draft line', copy: 'Enter exactly two 2D or 3D points separated by a semicolon.', position: false,
    fields: [['name', 'Name', 'Line', 'text'], ['points', 'Points: X,Y,Z; X,Y,Z', '0,0,0; 100,0,0', 'textarea']],
  },
  bspline: {
    title: 'Draft B-spline', copy: 'Enter three or more interpolation points separated by semicolons.', position: false,
    fields: [['name', 'Name', 'B-spline', 'text'], ['points', 'Points', '0,0,0; 40,60,0; 100,0,0', 'textarea']],
  },
  polyline: {
    title: 'Draft polyline', copy: 'Enter two or more points. Enable Close to make a closed wire.', position: false,
    fields: [['name', 'Name', 'Polyline', 'text'], ['points', 'Points', '0,0,0; 100,0,0; 100,60,0', 'textarea'], ['close', 'Close polyline', false, 'checkbox']],
  },
  circle: {
    title: 'Draft circle', copy: 'Creates an exact planar circular profile.',
    fields: [['name', 'Name', 'Circle', 'text'], ['plane', 'Plane', 'XY', 'select', ['XY', 'XZ', 'YZ']], ['radius', 'Radius', 50, 'number']],
  },
  rectangle: {
    title: 'Draft square / rectangle', copy: 'Creates an exact centered planar rectangular profile.',
    fields: [['name', 'Name', 'Square', 'text'], ['plane', 'Plane', 'XY', 'select', ['XY', 'XZ', 'YZ']], ['width', 'Width', 100, 'number'], ['height', 'Height', 100, 'number']],
  },
  polygon: {
    title: 'Draft regular polygon', copy: 'Creates an exact regular N-sided profile using the circumscribed radius.',
    fields: [['name', 'Name', 'Polygon', 'text'], ['plane', 'Plane', 'XY', 'select', ['XY', 'XZ', 'YZ']], ['sides', 'Number of sides', 6, 'number'], ['radius', 'Radius', 50, 'number']],
  },
  ellipse: {
    title: 'Draft ellipse', copy: 'Creates an exact planar ellipse.',
    fields: [['name', 'Name', 'Ellipse', 'text'], ['plane', 'Plane', 'XY', 'select', ['XY', 'XZ', 'YZ']], ['x_radius', 'X radius', 60, 'number'], ['y_radius', 'Y radius', 35, 'number']],
  },
  extrude: {
    title: 'Extrude selected profile(s)', copy: 'Creates exact solids from one or more selected closed profiles.', position: false,
    fields: [['name', 'Name', 'Extrude', 'text'], ['distance', 'Distance', 100, 'number'], ['direction_x', 'Direction X', 0, 'number'], ['direction_y', 'Direction Y', 0, 'number'], ['direction_z', 'Direction Z', 1, 'number']],
  },
  revolve: {
    title: 'Revolve selected profile(s)', copy: 'Revolves closed profiles around the specified 3D axis.', position: false,
    fields: [['name', 'Name', 'Revolve', 'text'], ['angle', 'Angle (degrees)', 360, 'number'], ['axis_start_x', 'Axis start X', 0, 'number'], ['axis_start_y', 'Axis start Y', 0, 'number'], ['axis_start_z', 'Axis start Z', 0, 'number'], ['axis_end_x', 'Axis end X', 0, 'number'], ['axis_end_y', 'Axis end Y', 1, 'number'], ['axis_end_z', 'Axis end Z', 0, 'number']],
  },
  cross_section: {
    title: 'Create cross sections', copy: 'Creates exact section curves at one or more parallel planes through the selected solids.', position: false,
    fields: [['name', 'Name', 'Cross Sections', 'text'], ['plane', 'Plane', 'XY', 'select', ['XY', 'XZ', 'YZ']], ['offset', 'First plane offset', 0, 'number'], ['count', 'Section count', 1, 'number'], ['spacing', 'Spacing', 10, 'number']],
  },
  sweep: {
    title: 'Sweep profile along path', copy: 'The primary selected component is the closed profile; the other selected component is the path.', position: false,
    fields: [['name', 'Name', 'Sweep', 'text']],
  },
  loft: {
    title: 'Loft selected profiles', copy: 'Creates an exact solid through two or more selected closed profiles in selection order.', position: false,
    fields: [['name', 'Name', 'Loft', 'text']],
  },
  fillet: {
    title: 'Round / Fillet edges', copy: 'Rounds selected edge numbers, or every compatible edge when left blank.', position: false,
    fields: [['name', 'Name', 'Rounded', 'text'], ['radius', 'Radius', 2, 'number'], ['edge_indices', 'Edge numbers (1,2,3 or blank for all)', '', 'text']],
  },
  chamfer: {
    title: 'Chamfer edges', copy: 'Chamfers selected edge numbers, or every compatible edge when left blank.', position: false,
    fields: [['name', 'Name', 'Chamfered', 'text'], ['distance', 'Distance', 2, 'number'], ['distance2', 'Second distance (optional)', 0, 'number'], ['edge_indices', 'Edge numbers (1,2,3 or blank for all)', '', 'text']],
  },
  additive_helix: {
    title: 'Additive helix', copy: 'Select the closed profile first, then Ctrl-click the base solid. The swept helix is fused to the base.', position: false,
    fields: [['name', 'Name', 'AdditiveHelix', 'text'], ['pitch', 'Pitch', 10, 'number'], ['height', 'Height', 50, 'number'], ['radius', 'Helix radius', 20, 'number'], ['center_x', 'Center X', 0, 'number'], ['center_y', 'Center Y', 0, 'number'], ['center_z', 'Center Z', 0, 'number'], ['direction_x', 'Axis direction X', 0, 'number'], ['direction_y', 'Axis direction Y', 0, 'number'], ['direction_z', 'Axis direction Z', 1, 'number'], ['start_angle', 'Starting angle °', 0, 'number'], ['taper_angle', 'Cone semi-angle °', 0, 'number'], ['left_hand', 'Left hand', false, 'checkbox']],
  },
  subtractive_helix: {
    title: 'Subtractive helix', copy: 'Select the closed profile first, then Ctrl-click the base solid. The swept helix is cut from the base.', position: false,
    fields: [['name', 'Name', 'SubtractiveHelix', 'text'], ['pitch', 'Pitch', 10, 'number'], ['height', 'Height', 50, 'number'], ['radius', 'Helix radius', 20, 'number'], ['center_x', 'Center X', 0, 'number'], ['center_y', 'Center Y', 0, 'number'], ['center_z', 'Center Z', 0, 'number'], ['direction_x', 'Axis direction X', 0, 'number'], ['direction_y', 'Axis direction Y', 0, 'number'], ['direction_z', 'Axis direction Z', 1, 'number'], ['start_angle', 'Starting angle °', 0, 'number'], ['taper_angle', 'Cone semi-angle °', 0, 'number'], ['left_hand', 'Left hand', false, 'checkbox']],
  },
  array: {
    title: 'Array selected part', copy: 'Create lightweight linked duplicates in a linear, rectangular, or polar pattern.', position: false,
    fields: [['mode', 'Array type', 'linear', 'select', ['linear', 'rectangular', 'polar']], ['count_x', 'X / item count', 3, 'number'], ['count_y', 'Y count', 1, 'number'], ['count_z', 'Z count', 1, 'number'], ['spacing_x', 'X spacing', 100, 'number'], ['spacing_y', 'Y spacing', 100, 'number'], ['spacing_z', 'Z spacing', 100, 'number'], ['total_angle', 'Polar total angle °', 360, 'number'], ['axis', 'Polar axis', 'Z', 'select', ['X', 'Y', 'Z']]],
  },
  mirror: {
    title: 'Mirror component', copy: 'Creates a mirrored exact copy of the primary selected component.', position: false,
    fields: [['name', 'Name', 'Mirror', 'text'], ['plane', 'Mirror plane', 'YZ', 'select', ['XY', 'XZ', 'YZ']]],
  },
};

function openModelDialog(operation) {
  const schema = MODEL_SCHEMAS[operation];
  if (!schema || !modelDialog || !modelFields) return;
  pendingModelOperation = operation;
  modelDialogTitle.textContent = schema.title;
  modelDialogCopy.textContent = schema.copy;
  const rows = [...schema.fields];
  if (schema.position !== false) {
    rows.push(['position_x', 'Position X', 0, 'number'], ['position_y', 'Position Y', 0, 'number'], ['position_z', 'Position Z', 0, 'number']);
  }
  modelFields.innerHTML = rows.map(([name, label, value, type, options]) => {
    if (type === 'select') {
      return `<label>${escapeHtml(label)}<select name="${escapeHtml(name)}">${options.map(option => `<option ${option === value ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('')}</select></label>`;
    }
    if (type === 'textarea') {
      return `<label class="model-field-wide">${escapeHtml(label)}<textarea name="${escapeHtml(name)}" rows="3" required>${escapeHtml(value)}</textarea></label>`;
    }
    if (type === 'checkbox') {
      return `<label class="model-check"><input name="${escapeHtml(name)}" type="checkbox" ${value ? 'checked' : ''}><span>${escapeHtml(label)}</span></label>`;
    }
    const isLength = type === 'number' && LENGTH_PARAMETER_NAMES.has(name);
    const shownValue = isLength ? rounded(toDisplayLength(value), 5) : value;
    const shownLabel = isLength ? `${label} (${displayUnitLabel()})` : label;
    return `<label>${escapeHtml(shownLabel)}<input name="${escapeHtml(name)}" type="${type}" value="${escapeHtml(shownValue)}" ${type === 'number' ? 'step="0.00001" required' : ''}></label>`;
  }).join('');
  modelDialog.showModal();
}

function modelParametersFromForm() {
  const schema = MODEL_SCHEMAS[pendingModelOperation];
  const values = Object.fromEntries(new FormData(modelForm).entries());
  const result = {};
  for (const [name, _label, _defaultValue, type] of schema.fields) {
    if (type === 'checkbox') result[name] = Boolean(modelForm.elements[name]?.checked);
    else if (['text', 'textarea', 'select'].includes(type)) result[name] = String(values[name] ?? '');
    else result[name] = LENGTH_PARAMETER_NAMES.has(name) ? fromDisplayLength(values[name]) : Number(values[name]);
  }
  if (schema.position !== false) {
    result.position = ['x', 'y', 'z'].map(axis => fromDisplayLength(values[`position_${axis}`]));
  }
  const vectorGroups = {
    direction: ['direction_x', 'direction_y', 'direction_z'],
    axis_start: ['axis_start_x', 'axis_start_y', 'axis_start_z'],
    axis_end: ['axis_end_x', 'axis_end_y', 'axis_end_z'],
  };
  for (const [target, keys] of Object.entries(vectorGroups)) {
    if (keys.every(key => key in result)) {
      result[target] = keys.map(key => Number(result[key]));
      keys.forEach(key => delete result[key]);
    }
  }
  if (typeof result.edge_indices === 'string') {
    result.edge_indices = result.edge_indices.split(/[\s,;]+/).map(Number).filter(value => Number.isInteger(value) && value > 0);
  }
  if ('center_x' in result) {
    result.center = [result.center_x, result.center_y, result.center_z];
    delete result.center_x; delete result.center_y; delete result.center_z;
  }
  return result;
}

function orderedSelectedComponentIds() {
  return selectedId ? [selectedId, ...[...selectedIds].filter(id => id !== selectedId)] : [...selectedIds];
}

async function runModelOperation(operation, parameters = {}, componentIds = [...selectedIds]) {
  const result = await getJson(appPath(`/api/projects/${projectId}/model`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({operation, parameters, component_ids: componentIds}),
  });
  clearSelection();
  await watchJob(result.job);
  await refreshProject({reloadPreview: true});
  notify(`${operation} operation complete.`);
}

function requireExactSelection(minimum, label) {
  if (['mesh', 'mixed'].includes(currentProject?.geometry_kind)) {
    notify(`${label} requires exact B-rep components; mesh components must be reconstructed first.`);
    return false;
  }
  if (selectedIds.size < minimum) {
    notify(`Select at least ${minimum} component${minimum === 1 ? '' : 's'} for ${label}. Hold Ctrl or Shift to multi-select.`);
    return false;
  }
  return true;
}

function updateProjectState(project) {
  currentProject = project;
  componentsById = new Map((project.components || []).map(component => [component.id, component]));
  stateElement.textContent = project.status;
  stateElement.className = `state-pill ${project.status}`;
  message.textContent = project.message || '';
  const editor = project.editor || {};
  dirtyState.hidden = !editor.dirty;
  commitEdits.disabled = !editor.dirty || ['queued', 'processing'].includes(project.status);
  undoButton.disabled = !editor.can_undo;
  redoButton.disabled = !editor.can_redo;
  syncExportControls();
  if (stepExportSummary) {
    const report = project.last_export_report || project.step_export_report;
    if (report) {
      const sizeMb = Number(report.file_size || 0) / (1024 * 1024);
      const reportFormat = String(report.format || project.last_export_format || '').toLowerCase();
      const detail = report.writer_mode === 'faceted-brep-fallback'
        ? `${Number(report.faceted_mesh_triangle_count || 0).toLocaleString()} planar facets`
        : ['brep', 'fcstd'].includes(reportFormat)
          ? `${Number(report.solid_count || 0).toLocaleString()} solids · ${Number(report.faceted_open_shell_count || report.faceted_shell_component_count || 0).toLocaleString()} retained open shells · ${Number(report.faceted_mixed_component_count || 0).toLocaleString()} mixed components · ${Number(report.component_count || report.source_component_count || 0).toLocaleString()} parts`
          : reportFormat === 'csg'
            ? `${Number(report.polyhedron_count || report.part_count || 0).toLocaleString()} closed solid shells · ${Number(report.triangle_count || 0).toLocaleString()} triangles · ${Number(report.topology_validation?.reoriented_triangle_count || 0).toLocaleString()} winding fixes`
            : report.triangle_count
              ? `${Number(report.triangle_count).toLocaleString()} triangles`
              : report.geometry_kind || 'assembly';
      stepExportSummary.textContent = `Latest export: .${String(report.format || project.last_export_format || '').toUpperCase()} · ${report.scope || 'project'} · ${report.output_unit || report.internal_unit || 'MM'} · ${detail} · ${sizeMb.toFixed(1)} MB.`;
    } else {
      stepExportSummary.textContent = 'Choose XBF, STEP, CSG, BREP, or FCStd and press Export. The completed file downloads automatically.';
    }
  }
  if (facetedConversionSummary) {
    const conversion = project.faceted_conversion_report;
    if (conversion) {
      const changed = Boolean(conversion.changed);
      const hardSpeedDetails = changed
        ? ` · ${escapeHtml(String(conversion.backend || 'faceted conversion'))} · ${Number(conversion.workers_used || 1).toLocaleString()} worker${Number(conversion.workers_used || 1) === 1 ? '' : 's'} · ${Number(conversion.cache_hit_component_count || 0).toLocaleString()} cache hits · ${Number(conversion.triangles_per_second || 0).toLocaleString()} triangles/s${conversion.fast_sewing_requested ? ' · FastSewing requested' : ''}`
        : '';
      facetedConversionSummary.innerHTML = `<h3>Faceted XBF conversion</h3><p class="small-copy">${changed
        ? `${Number(conversion.source_mesh_triangle_count || 0).toLocaleString()} mesh triangles converted · ${Number(conversion.solid_count || 0).toLocaleString()} faceted solids · ${Number(conversion.faceted_open_shell_count || 0).toLocaleString()} retained open shells · 0 triangulation-only remnants${hardSpeedDetails}.`
        : 'No triangulation-only remnants were found; the XBF was already BREP-based.'}</p>`;
    } else {
      facetedConversionSummary.innerHTML = '';
    }
  }
  const busy = ['queued', 'processing', 'uploading'].includes(project.status);
  if (combineProjectsButton) combineProjectsButton.disabled = busy;
  document.querySelectorAll('.primitive-tool, .draft-tool').forEach(button => { button.disabled = busy; });
  const exactUnavailable = ['mesh', 'mixed'].includes(project.geometry_kind);
  document.querySelectorAll('.solid-operation-tool').forEach(button => { button.disabled = busy || exactUnavailable; });
  for (const id of ['tool-fuse', 'tool-subtract', 'tool-mirror', 'tool-facebinder', 'tool-fillet', 'tool-chamfer', 'tool-additive-helix', 'tool-subtractive-helix', 'split-selected']) {
    const button = document.querySelector(`#${id}`);
    if (button) button.disabled = busy || exactUnavailable;
  }
  if (meshCleanupSummary) {
    const cleanup = project.mesh_cleanup;
    meshCleanupSummary.innerHTML = cleanup?.enabled
      ? `<h3>Mesh cleanup</h3><p class="small-copy">Removed ${Number(cleanup.removed_coincident_objects || 0).toLocaleString()} coincident objects and ${Number(cleanup.removed_duplicate_faces || 0).toLocaleString()} duplicate faces. File reduction: ${cleanup.reduction_percent ?? 0}%.</p>`
      : '';
  }
  if (combinedProjectsSummary) {
    const combined = project.combined_projects || [];
    combinedProjectsSummary.innerHTML = combined.length
      ? `<h3>Combined projects</h3><ul>${combined.map(item => `<li>${escapeHtml(item.name)} <small>${escapeHtml(item.assembly_node || '')}</small></li>`).join('')}</ul>`
      : '';
  }
}

function scheduleProjectRefresh(delay = 2000, options = {}) {
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(() => refreshProject(options).catch(() => {}), delay);
}

async function refreshProject(options = {}) {
  try {
    const project = await getJson(appPath(`/api/projects/${projectId}`));
    updateProjectState(project);
    if (project.status === 'ready' && project.preview_glb) {
      if (!model || options.reloadPreview) await loadPreview();
      else syncSceneFromComponents();
    }
    renderTree();
    if (['queued', 'processing', 'uploading'].includes(project.status) && !activeJobId) scheduleProjectRefresh(2000);
    return project;
  } catch (error) {
    notify(`Server connection interrupted; retrying… ${error.message || error}`, 4000);
    scheduleProjectRefresh(3000, options);
    throw error;
  }
}

function rememberProjectJob(job) {
  localStorage.setItem(ACTIVE_PROJECT_JOB_KEY, JSON.stringify({id: job.id, saved_at: Date.now()}));
}

function forgetProjectJob() {
  localStorage.removeItem(ACTIVE_PROJECT_JOB_KEY);
}

async function watchJob(job, options = {}) {
  rememberProjectJob(job);
  activeJobId = job.id;
  activeJobCancellable = Boolean(options.cancellable);
  syncExportControls();
  let delay = 700;
  let failures = 0;
  let lastProgress = 0;
  try {
    while (true) {
      try {
        const update = await getJson(appPath(`/api/jobs/${job.id}`));
        failures = 0;
        if (['export_file', 'export_step', 'convert_faceted_solids'].includes(update.operation)) {
          activeJobCancellable = true;
          syncExportControls();
        }
        lastProgress = Number(update.progress || lastProgress || 0);
        notify(`${lastProgress}% · ${update.message || update.status}`, 2500);
        if (update.status === 'complete') {
          forgetProjectJob();
          const completedFormat = options.autoDownloadFormat || update.result?.format;
          if (completedFormat) {
            const link = document.createElement('a');
            link.href = appPath(`/api/projects/${projectId}/download/${completedFormat}`);
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            setTimeout(() => link.remove(), 2000);
          }
          return update;
        }
        if (update.status === 'failed' || update.status === 'cancelled') {
          forgetProjectJob();
          const error = new Error(update.message || update.error || `Job ${update.status}`);
          error.terminal = true;
          throw error;
        }
        await new Promise(resolve => setTimeout(resolve, delay));
        delay = Math.min(2500, Math.round(delay * 1.15));
      } catch (error) {
        if (error.terminal || error.status === 404) throw error;
        failures += 1;
        if (failures > 360) { forgetProjectJob(); throw new Error(`Unable to reconnect: ${error.message || error}`); }
        const seconds = Math.min(10, Math.max(2, failures));
        notify(`${lastProgress}% · Server connection interrupted; retrying in ${seconds}s…`, 3000);
        await new Promise(resolve => setTimeout(resolve, seconds * 1000));
        delay = 700;
      }
    }
  } finally {
    activeJobId = null;
    activeJobCancellable = false;
    syncExportControls();
  }
}

async function sendEditorOperation(operation, extra = {}, componentId = selectedId) {
  const componentIds = Array.isArray(extra.component_ids) ? extra.component_ids : null;
  if (!componentId && !componentIds?.length) throw new Error('Select a component first');
  const result = await getJson(appPath(`/api/projects/${projectId}/editor`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({operation, component_id: componentId, ...extra}),
  });
  const previousIds = new Set(componentsById.keys());
  currentProject.editor = result.editor;
  currentProject.components = result.components;
  updateProjectState(currentProject);
  syncSceneFromComponents();
  return result.components.find(component => !previousIds.has(component.id));
}

async function toggleComponentVisibility(ids = [...selectedIds]) {
  const selected = ids.filter(id => componentsById.has(id));
  if (!selected.length) throw new Error('Select one or more parts first');
  const shouldShow = selected.some(id => componentsById.get(id)?.visible === false);
  await sendEditorOperation('visibility', {component_ids: selected, visible: shouldShow}, selected[0]);
  notify(`${selected.length} part${selected.length === 1 ? '' : 's'} ${shouldShow ? 'shown' : 'hidden'}.`);
}

async function showAllComponents() {
  const ids = [...componentsById.values()].filter(component => !component.deleted && component.visible === false).map(component => component.id);
  isolateId = null;
  if (ids.length) await sendEditorOperation('visibility', {component_ids: ids, visible: true}, ids[0]);
  else syncSceneFromComponents();
}

async function applyMaterialToSelection() {
  const ids = [...selectedIds];
  if (!ids.length) throw new Error('Select one or more parts first');
  const material = {
    name: materialNameField?.value || 'Unassigned',
    density_kg_m3: Number(materialDensityField?.value || 0),
    color: materialColorField?.value || '#b8c0c8',
    description: materialDescriptionField?.value || '',
  };
  await sendEditorOperation('material', {component_ids: ids, material}, ids[0]);
  notify(`Material assigned to ${ids.length} part${ids.length === 1 ? '' : 's'}.`);
}

async function applyWrittenPartProperties() {
  if (!selectedId) throw new Error('Select a part first');
  const transform = transformFromFields();
  await sendEditorOperation('transform', {transform});
  const component = componentsById.get(selectedId);
  const newName = partNameField?.value?.trim();
  if (newName && component && newName !== component.name) await sendEditorOperation('rename', {name: newName});
  notify('Written position, orientation, and scale saved to the working edit layer.');
}

async function createArray(parameters) {
  if (!selectedId || selectedIds.size !== 1) throw new Error('Select exactly one source part for Array');
  const sourceId = selectedId;
  const source = componentsById.get(sourceId);
  const base = structuredClone(source.transform || source.base_transform);
  const mode = String(parameters.mode || 'linear');
  const countX = Math.max(1, Math.min(200, Math.round(parameters.count_x || 1)));
  const countY = mode === 'rectangular' ? Math.max(1, Math.min(50, Math.round(parameters.count_y || 1))) : 1;
  const countZ = mode === 'rectangular' ? Math.max(1, Math.min(50, Math.round(parameters.count_z || 1))) : 1;
  const total = mode === 'polar' ? countX : countX * countY * countZ;
  if (total > 200) throw new Error('Array is limited to 200 total parts');
  const placements = [];
  if (mode === 'polar') {
    for (let index = 1; index < total; index += 1) placements.push({sequence: index});
  } else {
    for (let z = 0; z < countZ; z += 1) {
      for (let y = 0; y < countY; y += 1) {
        for (let x = 0; x < countX; x += 1) {
          // The selected source part occupies the array origin; do not create a
          // duplicate directly on top of it.
          if (x === 0 && y === 0 && z === 0) continue;
          placements.push({x, y, z});
        }
      }
    }
  }
  const created = [];
  for (const placement of placements) {
    const duplicate = await sendEditorOperation('duplicate', {offset: 0}, sourceId);
    if (!duplicate) continue;
    const transform = structuredClone(base);
    if (mode === 'polar') {
      const angle = (Number(parameters.total_angle || 360) / total) * placement.sequence;
      const axis = String(parameters.axis || 'Z').toUpperCase();
      transform.rotation[{X: 0, Y: 1, Z: 2}[axis]] += angle;
      const radius = Number(parameters.spacing_x || 0);
      const radians = degToRad(angle);
      if (axis === 'Z') { transform.position[0] += Math.cos(radians) * radius; transform.position[1] += Math.sin(radians) * radius; }
      if (axis === 'Y') { transform.position[0] += Math.cos(radians) * radius; transform.position[2] += Math.sin(radians) * radius; }
      if (axis === 'X') { transform.position[1] += Math.cos(radians) * radius; transform.position[2] += Math.sin(radians) * radius; }
    } else {
      transform.position[0] += placement.x * Number(parameters.spacing_x || 0);
      transform.position[1] += placement.y * Number(parameters.spacing_y || 0);
      transform.position[2] += placement.z * Number(parameters.spacing_z || 0);
    }
    await sendEditorOperation('transform', {transform}, duplicate.id);
    created.push(duplicate.id);
  }
  notify(`Created ${created.length} linked array part${created.length === 1 ? '' : 's'}.`);
}

async function inspectSelection(mode = 'info') {
  const ids = orderedSelectedComponentIds();
  if (!ids.length) throw new Error('Select one or more parts first');
  inspectionResults.innerHTML = '<p class="small-copy">Calculating exact properties…</p>';
  const result = await getJson(appPath(`/api/projects/${projectId}/inspect`), {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({component_ids: ids}),
  });
  const parts = result.items || result.components || result.parts || [];
  const summary = result.totals || result.summary || result.total || {};
  const rows = [];
  const add = (label, value) => { if (value !== undefined && value !== null && value !== '') rows.push(`<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`); };
  add('Selected parts', parts.length || ids.length);
  add('X length', parts.length === 1 ? formatLength(parts[0].bbox?.x_length || 0) : null);
  add('Y length', parts.length === 1 ? formatLength(parts[0].bbox?.y_length || 0) : null);
  add('Z length', parts.length === 1 ? formatLength(parts[0].bbox?.z_length || 0) : null);
  add('Diagonal', parts.length === 1 ? formatLength(parts[0].bbox?.diagonal || 0) : null);
  add('Volume', summary.volume_mm3 != null ? `${Number(summary.volume_mm3).toLocaleString()} mm³` : null);
  add('Area', summary.area_mm2 != null ? `${Number(summary.area_mm2).toLocaleString()} mm²` : null);
  add('Edge length / perimeter', summary.edge_length_mm != null ? formatLength(summary.edge_length_mm) : null);
  add('Mass', summary.mass_kg != null ? `${rounded(summary.mass_kg, 5)} kg / ${rounded(summary.mass_kg * 2.2046226218, 5)} lb` : null);
  add('Minimum distance', result.minimum_distance_mm != null ? formatLength(result.minimum_distance_mm) : summary.minimum_distance_mm != null ? formatLength(summary.minimum_distance_mm) : null);
  if (parts.length === 1) {
    const part = parts[0];
    add('Faces / edges / vertices', `${part.counts?.faces ?? '—'} / ${part.counts?.edges ?? '—'} / ${part.counts?.vertices ?? '—'}`);
    add('Material', part.material?.name);
    add('Radius values', (part.radii_mm || []).map(formatLength).join(', '));
    add('Diameter values', (part.diameters_mm || []).map(formatLength).join(', '));
  }
  inspectionResults.innerHTML = `<dl class="inspection-table">${rows.join('')}</dl>${mode === 'measure' ? '<p class="small-copy">Measurement values use exact B-rep properties where available; mesh-only values are approximate.</p>' : ''}`;
}

async function runHistory(action) {
  const result = await getJson(appPath(`/api/projects/${projectId}/editor/${action}`), {method: 'POST'});
  currentProject.editor = result.editor;
  currentProject.components = result.components;
  updateProjectState(currentProject);
  syncSceneFromComponents();
}

async function commitWorkingEdits() {
  const result = await getJson(appPath(`/api/projects/${projectId}/editor/commit`), {method: 'POST'});
  await watchJob(result.job);
  await refreshProject({reloadPreview: true});
  notify('Editor changes committed to XBF.');
}

async function splitSelected() {
  if (!selectedId) return;
  const result = await getJson(appPath(`/api/projects/${projectId}/editor/split`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({component_id: selectedId}),
  });
  clearSelection();
  await watchJob(result.job);
  await refreshProject({reloadPreview: true});
  notify('Component split into separate solids.');
}


function applyContextualSnap() {
  if (applyingSnap || !selectedId || !osnapEnabled || !transformControls?.dragging) return;
  const node = nodeById.get(selectedId);
  if (!node || !node.parent) return;
  applyingSnap = true;
  try {
    const selectedBox = new THREE.Box3().setFromObject(node);
    const selectedCenter = selectedBox.getCenter(new THREE.Vector3());
    const candidates = [];
    const modes = new Set(preferences.osnapModes || []);
    if (modes.has('origin')) candidates.push({point: new THREE.Vector3(0, 0, 0), label: 'Origin', priority: 0});
    for (const [id, other] of nodeById) {
      if (id === selectedId || !other.visible) continue;
      const box = new THREE.Box3().setFromObject(other);
      if (box.isEmpty()) continue;
      const min = box.min, max = box.max, center = box.getCenter(new THREE.Vector3());
      if (modes.has('center')) candidates.push({point: center, label: 'Center', priority: 1});
      if (modes.has('endpoint')) {
        for (const x of [min.x, max.x]) for (const y of [min.y, max.y]) for (const z of [min.z, max.z]) {
          candidates.push({point: new THREE.Vector3(x, y, z), label: 'Endpoint', priority: 1});
        }
      }
      if (modes.has('midpoint')) {
        candidates.push(
          {point: new THREE.Vector3(center.x, min.y, min.z), label: 'Midpoint', priority: 2},
          {point: new THREE.Vector3(center.x, max.y, max.z), label: 'Midpoint', priority: 2},
          {point: new THREE.Vector3(min.x, center.y, center.z), label: 'Midpoint', priority: 2},
          {point: new THREE.Vector3(max.x, center.y, center.z), label: 'Midpoint', priority: 2},
        );
      }
    }
    if (modes.has('grid')) {
      const gridViewerStep = 10;
      candidates.push({
        point: new THREE.Vector3(
          Math.round(selectedCenter.x / gridViewerStep) * gridViewerStep,
          Math.round(selectedCenter.y / gridViewerStep) * gridViewerStep,
          Math.round(selectedCenter.z / gridViewerStep) * gridViewerStep,
        ), label: 'Grid', priority: 5,
      });
    }
    const rect = renderer.domElement.getBoundingClientRect();
    const projectScreen = point => {
      const projected = point.clone().project(camera);
      return new THREE.Vector2((projected.x + 1) * rect.width / 2, (-projected.y + 1) * rect.height / 2);
    };
    const selectedScreen = projectScreen(selectedCenter);
    let best = null;
    for (const candidate of candidates) {
      const distance = projectScreen(candidate.point).distanceTo(selectedScreen);
      if (distance > 14) continue;
      if (!best || candidate.priority < best.priority || (candidate.priority === best.priority && distance < best.distance)) best = {...candidate, distance};
    }
    if (!best) {
      if (snapMarker) snapMarker.visible = false;
      if (snapIndicator) snapIndicator.hidden = true;
      return;
    }
    const currentLocal = node.parent.worldToLocal(selectedCenter.clone());
    const targetLocal = node.parent.worldToLocal(best.point.clone());
    node.position.add(targetLocal.sub(currentLocal));
    node.updateMatrixWorld(true);
    if (snapMarker) { snapMarker.position.copy(best.point); snapMarker.visible = true; }
    if (snapIndicator) { snapIndicator.textContent = best.label; snapIndicator.hidden = false; }
  } finally {
    applyingSnap = false;
  }
}

function updateUnitUI() {
  if (unitToggle) {
    unitToggle.dataset.unitSystem = unitSystem;
    unitToggle.textContent = `${displayUnit.toUpperCase()} → ${exportUnit.toUpperCase()}`;
    unitToggle.classList.toggle('metric', unitSystem === 'metric');
  }
  document.querySelectorAll('.length-unit-label').forEach(element => { element.textContent = displayUnitLabel(); });
  if (selectedId) updateTransformFieldsFromNode();
}

function applyPreferencesToViewer() {
  if (resolutionSelect) resolutionSelect.value = preferences.resolution;
  document.querySelector('#rendering-quality-select') && (document.querySelector('#rendering-quality-select').value = preferences.renderingQuality || preferences.resolution);
  document.querySelector('#triangle-budget-select') && (document.querySelector('#triangle-budget-select').value = String(preferences.triangleBudget || 25000000));
  document.querySelector('#project-unit-select') && (document.querySelector('#project-unit-select').value = projectUnit);
  document.querySelector('#display-unit-select') && (document.querySelector('#display-unit-select').value = displayUnit);
  document.querySelector('#export-unit-select') && (document.querySelector('#export-unit-select').value = exportUnit);
  const checks = {
    '#preference-grid': preferences.grid,
    '#preference-origin': preferences.origin,
    '#preference-axes': preferences.axes,
    '#preference-keep-selection': preferences.keepSelectionPanel,
    '#preference-diagnostics': preferences.showDiagnostics,
    '#preference-lazy-loading': preferences.lazyLoadMeshes,
  };
  for (const [selector, value] of Object.entries(checks)) {
    const input = document.querySelector(selector); if (input) input.checked = Boolean(value);
  }
  document.querySelectorAll('[data-osnap-mode]').forEach(input => { input.checked = preferences.osnapModes.includes(input.dataset.osnapMode); });
  if (renderer) renderer.setPixelRatio(resolutionPixelRatio());
  if (gridHelper) gridHelper.visible = Boolean(preferences.grid);
  if (originHelper) originHelper.visible = Boolean(preferences.origin);
  if (axesHelper) axesHelper.visible = Boolean(preferences.axes);
  setSelectionPanelOpen(preferences.keepSelectionPanel || localStorage.getItem(SELECTION_PANEL_KEY) !== 'false', false);
  requestRender();
}

function collectPreferencesFromDialog() {
  preferences.resolution = resolutionSelect?.value || 'medium';
  preferences.grid = Boolean(document.querySelector('#preference-grid')?.checked);
  preferences.origin = Boolean(document.querySelector('#preference-origin')?.checked);
  preferences.axes = Boolean(document.querySelector('#preference-axes')?.checked);
  preferences.keepSelectionPanel = Boolean(document.querySelector('#preference-keep-selection')?.checked);
  preferences.renderingQuality = document.querySelector('#rendering-quality-select')?.value || preferences.resolution;
  preferences.triangleBudget = Number(document.querySelector('#triangle-budget-select')?.value || 25000000);
  preferences.projectUnit = projectUnit = document.querySelector('#project-unit-select')?.value || 'mm';
  preferences.displayUnit = displayUnit = document.querySelector('#display-unit-select')?.value || 'in';
  preferences.exportUnit = exportUnit = document.querySelector('#export-unit-select')?.value || displayUnit;
  preferences.showDiagnostics = Boolean(document.querySelector('#preference-diagnostics')?.checked);
  preferences.lazyLoadMeshes = Boolean(document.querySelector('#preference-lazy-loading')?.checked);
  unitSystem = ['in', 'ft', 'ft-in', 'yd'].includes(displayUnit) ? 'imperial' : 'metric';
  preferences.osnapModes = [...document.querySelectorAll('[data-osnap-mode]:checked')].map(input => input.dataset.osnapMode);
  savePreferences();
  applyPreferencesToViewer();
}

function setSelectionPanelOpen(open, persist = true) {
  selectionPanel?.classList.toggle('panel-closed', !open);
  if (openSelectionPanelButton) openSelectionPanelButton.hidden = open;
  if (persist) localStorage.setItem(SELECTION_PANEL_KEY, String(open));
}

function saveToolbarLayout() {
  const layout = [...document.querySelectorAll('.toolbar-row')].map(row => ({
    row: row.dataset.toolbarRow,
    tools: [...row.querySelectorAll('.draggable-toolbar')].map(toolElement => toolElement.dataset.toolbarId),
  }));
  localStorage.setItem(TOOLBAR_LAYOUT_KEY, JSON.stringify(layout));
}

function restoreToolbarLayout() {
  try {
    const layout = JSON.parse(localStorage.getItem(TOOLBAR_LAYOUT_KEY) || 'null');
    if (!Array.isArray(layout)) return;
    for (const rowLayout of layout) {
      const row = document.querySelector(`[data-toolbar-row="${CSS.escape(rowLayout.row)}"]`);
      if (!row) continue;
      for (const id of rowLayout.tools || []) {
        const toolbar = document.querySelector(`[data-toolbar-id="${CSS.escape(id)}"]`);
        if (toolbar) row.appendChild(toolbar);
      }
    }
  } catch { /* use authored layout */ }
}

function setupDraggableToolbars() {
  let dragged = null;
  document.querySelectorAll('.draggable-toolbar').forEach(toolbar => {
    toolbar.draggable = false;
    toolbar.querySelector('.toolbar-drag-handle')?.addEventListener('pointerdown', () => { toolbar.draggable = true; });
    toolbar.addEventListener('dragstart', event => { dragged = toolbar; event.dataTransfer.effectAllowed = 'move'; toolbar.classList.add('dragging'); });
    toolbar.addEventListener('dragend', () => { toolbar.draggable = false; toolbar.classList.remove('dragging'); dragged = null; saveToolbarLayout(); });
  });
  document.querySelectorAll('.toolbar-drop-zone').forEach(row => {
    row.addEventListener('dragover', event => {
      event.preventDefault();
      if (!dragged) return;
      const siblings = [...row.querySelectorAll('.draggable-toolbar:not(.dragging)')];
      const after = siblings.find(sibling => event.clientX < sibling.getBoundingClientRect().left + sibling.getBoundingClientRect().width / 2);
      row.insertBefore(dragged, after || null);
    });
  });
}

function resetToolbarLayout() {
  localStorage.removeItem(TOOLBAR_LAYOUT_KEY);
  location.reload();
}

for (const field of [...fields.position, ...fields.rotation, ...fields.scale]) {
  field.addEventListener('input', applyFieldTransformToNode);
}

partPropertiesForm?.addEventListener('submit', event => {
  event.preventDefault();
  applyWrittenPartProperties().catch(error => notify(error.message));
});

document.querySelector('#apply-material')?.addEventListener('click', () => applyMaterialToSelection().catch(error => notify(error.message)));
materialNameField?.addEventListener('change', () => {
  const preset = MATERIAL_PRESETS[materialNameField.value] || MATERIAL_PRESETS.Custom;
  materialDensityField.value = preset.density_kg_m3;
  materialColorField.value = preset.color;
  materialColorTextField.value = preset.color;
  materialDescriptionField.value = preset.description;
});
materialColorField?.addEventListener('input', () => { materialColorTextField.value = materialColorField.value; });
materialColorTextField?.addEventListener('change', () => {
  if (/^#[0-9a-f]{6}$/i.test(materialColorTextField.value)) materialColorField.value = materialColorTextField.value;
});

document.querySelector('#delete-selected')?.addEventListener('click', async () => {
  const ids = [...selectedIds];
  if (!ids.length || !confirm(`Delete ${ids.length} selected part${ids.length === 1 ? '' : 's'} from the working assembly?`)) return;
  try {
    await sendEditorOperation('delete', {component_ids: ids}, ids[0]);
    clearSelection();
    notify('Selected parts deleted. Undo is available.');
  } catch (error) { notify(error.message); }
});

document.querySelector('#duplicate-selected')?.addEventListener('click', async () => {
  try {
    if (selectedIds.size !== 1) throw new Error('Select exactly one part to duplicate');
    const duplicate = await sendEditorOperation('duplicate', {offset: fromDisplayLength(4)});
    if (duplicate) selectComponent(duplicate.id, {fit: false});
    notify(`Part duplicated with a 4 ${displayUnitLabel()} X offset.`);
  } catch (error) { notify(error.message); }
});

document.querySelector('#hide-selected')?.addEventListener('click', () => toggleComponentVisibility().catch(error => notify(error.message)));
document.querySelector('#show-all')?.addEventListener('click', () => showAllComponents().catch(error => notify(error.message)));

isolateButton?.addEventListener('click', () => {
  isolateId = isolateId === selectedId ? null : selectedId;
  syncSceneFromComponents();
});

document.querySelector('#clear-selection')?.addEventListener('click', clearSelection);
document.querySelector('#split-selected')?.addEventListener('click', () => splitSelected().catch(error => notify(error.message)));
document.querySelector('#fit-view')?.addEventListener('click', () => fitView(selectedId ? nodeById.get(selectedId) : model));
reloadMasterButton?.addEventListener('click', async () => {
  try {
    isolateId = null;
    clearSelection();
    await loadPreview();
    syncSceneFromComponents();
    notify('Reloaded the preview generated from master.xbf. Working edits remain overlaid until committed or undone.');
  } catch (error) { notify(error.message); }
});
combineProjectsButton?.addEventListener('click', () => openCombineDialog().catch(error => notify(error.message)));
cancelCombineButton?.addEventListener('click', () => combineDialog?.close());
confirmCombineButton?.addEventListener('click', () => combineSelectedProjects().catch(error => notify(error.message)));
combineDialog?.addEventListener('click', event => { if (event.target === combineDialog) combineDialog.close(); });

document.querySelectorAll('.primitive-tool').forEach(button => {
  button.addEventListener('click', () => openModelDialog(button.dataset.primitive));
});
document.querySelectorAll('.draft-tool').forEach(button => {
  button.addEventListener('click', () => openModelDialog(button.dataset.draft));
});
document.querySelectorAll('.solid-operation-tool').forEach(button => {
  button.addEventListener('click', () => {
    const operation = button.dataset.operation;
    if (operation === 'sweep') {
      if (!requireExactSelection(2, 'Sweep') || selectedIds.size !== 2) {
        if (selectedIds.size !== 2) notify('Sweep requires exactly two components: select the path, then Ctrl-click the profile you want as primary.');
        return;
      }
    } else if (operation === 'loft') {
      if (!requireExactSelection(2, 'Loft')) return;
    } else if (!requireExactSelection(1, operation === 'cross_section' ? 'Cross Sections' : operation[0].toUpperCase() + operation.slice(1))) {
      return;
    }
    openModelDialog(operation);
  });
});
document.querySelector('#tool-clone')?.addEventListener('click', () => document.querySelector('#duplicate-selected')?.click());
document.querySelector('#tool-mirror')?.addEventListener('click', () => {
  if (requireExactSelection(1, 'Mirror') && selectedIds.size === 1) openModelDialog('mirror');
  else if (selectedIds.size > 1) notify('Mirror uses exactly one primary selected component.');
});
document.querySelector('#tool-fuse')?.addEventListener('click', () => {
  if (!requireExactSelection(2, 'Fuse')) return;
  runModelOperation('fuse', {name: 'Fusion'}).catch(error => notify(error.message));
});
document.querySelector('#tool-subtract')?.addEventListener('click', () => {
  if (!requireExactSelection(2, 'Subtract')) return;
  const ordered = [selectedId, ...[...selectedIds].filter(id => id !== selectedId)];
  runModelOperation('subtract', {name: 'Cut'}, ordered).catch(error => notify(error.message));
});
document.querySelector('#tool-facebinder')?.addEventListener('click', () => {
  if (!requireExactSelection(1, 'Face Binder')) return;
  runModelOperation('facebinder', {name: 'FaceBinder'}).catch(error => notify(error.message));
});
document.querySelector('#tool-array')?.addEventListener('click', () => {
  if (selectedIds.size !== 1) { notify('Array requires exactly one selected source part.'); return; }
  openModelDialog('array');
});
for (const [buttonId, operation, label] of [
  ['tool-fillet', 'fillet', 'Round / Fillet'],
  ['tool-chamfer', 'chamfer', 'Chamfer'],
]) {
  document.querySelector(`#${buttonId}`)?.addEventListener('click', () => {
    if (requireExactSelection(1, label)) openModelDialog(operation);
  });
}
for (const [buttonId, operation, label] of [
  ['tool-additive-helix', 'additive_helix', 'Additive Helix'],
  ['tool-subtractive-helix', 'subtractive_helix', 'Subtractive Helix'],
]) {
  document.querySelector(`#${buttonId}`)?.addEventListener('click', () => {
    if (!requireExactSelection(2, label) || selectedIds.size !== 2) { notify(`${label} requires exactly two parts: select the profile first, then Ctrl-click the base solid.`); return; }
    openModelDialog(operation);
  });
}
document.querySelector('#tool-material')?.addEventListener('click', () => {
  if (!selectedId) { notify('Select one or more parts first.'); return; }
  document.querySelector('#part-properties-pane')?.scrollIntoView({block: 'nearest'});
  materialNameField?.focus();
});
document.querySelector('#tool-measure')?.addEventListener('click', () => inspectSelection('measure').catch(error => notify(error.message)));
document.querySelector('#tool-info')?.addEventListener('click', () => inspectSelection('info').catch(error => notify(error.message)));
document.querySelector('#tool-osnap')?.addEventListener('click', event => {
  osnapEnabled = !osnapEnabled;
  event.currentTarget.classList.toggle('active', osnapEnabled);
  event.currentTarget.setAttribute('aria-pressed', String(osnapEnabled));
  if (!osnapEnabled) { if (snapMarker) snapMarker.visible = false; if (snapIndicator) snapIndicator.hidden = true; requestRender(); }
  notify(`OSnap ${osnapEnabled ? 'on' : 'off'}.`);
});
cancelModelButton?.addEventListener('click', () => modelDialog?.close());
modelForm?.addEventListener('submit', event => {
  event.preventDefault();
  if (!pendingModelOperation) return;
  const operation = pendingModelOperation;
  const parameters = modelParametersFromForm();
  const selectedOperations = new Set(['mirror', 'extrude', 'revolve', 'cross_section', 'sweep', 'loft', 'fillet', 'chamfer', 'additive_helix', 'subtractive_helix']);
  if (operation === 'mirror' && !requireExactSelection(1, 'Mirror')) return;
  // Loft and helix depend on the user's click order. For helix the first
  // selected part is the profile and the second selected part is the base.
  const orderedBySelection = new Set(['loft', 'additive_helix', 'subtractive_helix']);
  const componentIds = orderedBySelection.has(operation) ? [...selectedIds] : selectedOperations.has(operation) ? orderedSelectedComponentIds() : [];
  modelDialog.close();
  if (operation === 'array') createArray(parameters).catch(error => notify(error.message));
  else runModelOperation(operation, parameters, componentIds).catch(error => notify(error.message));
});
modelDialog?.addEventListener('close', () => { pendingModelOperation = null; });

document.querySelector('#tool-select').addEventListener('click', () => setTool('select'));
document.querySelector('#tool-move').addEventListener('click', () => setTool('move'));
document.querySelector('#tool-rotate').addEventListener('click', () => setTool('rotate'));
document.querySelector('#tool-scale')?.addEventListener('click', () => setTool('scale'));
undoButton.addEventListener('click', () => runHistory('undo').catch(error => notify(error.message)));
redoButton.addEventListener('click', () => runHistory('redo').catch(error => notify(error.message)));
commitEdits.addEventListener('click', () => commitWorkingEdits().catch(error => notify(error.message)));

async function runFacetedConversion() {
  const dirtyCopy = currentProject?.editor?.dirty
    ? ' Your current working editor changes will be included and committed.'
    : '';
  const fastMode = Boolean(fastRender?.checked);
  const confirmed = confirm(
    'Convert every triangulation-only XBF component into faceted BREP solids or retained open shells? '
    + 'Exact BREP parts stay exact, duplicate parts reuse one cached conversion, and up to 60 jobs are queued with a safe bounded worker count. '
    + (fastMode ? 'FastSewing is enabled and optional same-domain unification is skipped. ' : '')
    + 'A revision snapshot is created, and master.xbf plus the GLB preview are replaced.'
    + dirtyCopy
  );
  if (!confirmed) return;
  convertFacetedButton.disabled = true;
  try {
    const result = await getJson(appPath(`/api/projects/${projectId}/convert/faceted-solids`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({fast_render: fastMode}),
    });
    await watchJob(result.job, {cancellable: true});
    const project = await refreshProject({reloadPreview: true});
    const report = project.faceted_conversion_report || {};
    notify(report.changed
      ? `Faceted solid conversion complete: ${Number(report.solid_count || 0).toLocaleString()} solids, ${Number(report.faceted_open_shell_count || 0).toLocaleString()} retained open shells, ${Number(report.cache_hit_component_count || 0).toLocaleString()} cache hits, ${Number(report.triangles_per_second || 0).toLocaleString()} triangles/s, and no mesh remnants.`
      : 'No triangulation-only XBF remnants were found; no geometry rewrite was needed.', 9000);
  } catch (error) {
    notify(error.message, 12000);
  } finally {
    syncExportControls();
  }
}

async function runExport() {
  const format = String(exportFormat?.value || 'xbf').toLowerCase();
  const componentIds = exportSelectedOnly?.checked ? [...selectedIds] : [];
  if (exportSelectedOnly?.checked && componentIds.length === 0) {
    notify('Select one or more components first.');
    return;
  }
  if (['brep', 'fcstd'].includes(format) && ['mesh', 'mixed'].includes(currentProject?.geometry_kind)) {
    notify('Closed mesh shells become faceted Part solids; open shells are preserved, including mixed solid/shell components. Exact+mesh components are fully faceted. No Mesh::Feature objects are written.', 7000);
  } else if (format === 'csg') {
    notify('CSG exports one top-level polyhedron per closed connected solid shell. Disconnected solids are split and triangle winding is repaired; open or non-manifold shells stop the export instead of creating strip-like geometry.', 9000);
  }
  exportButton.disabled = true;
  try {
    const result = await getJson(appPath(`/api/projects/${projectId}/export`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({format, component_ids: componentIds, fast_render: Boolean(fastRender?.checked), unit_system: unitSystem, export_unit: exportUnit}),
    });
    await watchJob(result.job, {autoDownloadFormat: format, cancellable: true});
    await refreshProject();
    notify(`${format.toUpperCase()} export completed and download started.`);
  } catch (error) {
    notify(error.message, 9000);
  } finally {
    syncExportControls();
  }
}

exportButton?.addEventListener('click', () => runExport().catch(error => notify(error.message)));
convertFacetedButton?.addEventListener('click', () => runFacetedConversion().catch(error => notify(error.message)));
cancelJobButton?.addEventListener('click', async () => {
  if (!activeJobId) return;
  try {
    await getJson(appPath(`/api/jobs/${activeJobId}/cancel`), {method: 'POST'});
    notify('Cancellation requested; CascadeCAD will stop after the current geometry chunk.');
  } catch (error) { notify(error.message); }
});

unitToggle?.addEventListener('click', () => {
  displayUnit = displayUnit === 'in' ? 'mm' : 'in';
  exportUnit = displayUnit;
  preferences.displayUnit = displayUnit;
  preferences.exportUnit = exportUnit;
  unitSystem = displayUnit === 'in' ? 'imperial' : 'metric';
  localStorage.setItem('cascadecad-unit-system', unitSystem);
  savePreferences();
  updateUnitUI();
  notify(`Display/export units changed to ${displayUnit}. Internal geometry remains in high-precision millimeters.`);
});
document.querySelector('#preferences-button')?.addEventListener('click', () => { applyPreferencesToViewer(); preferencesDialog?.showModal(); });
document.querySelector('#preferences-form')?.addEventListener('submit', () => collectPreferencesFromDialog());
resolutionSelect?.addEventListener('change', () => { collectPreferencesFromDialog(); });
document.querySelector('#reset-layout')?.addEventListener('click', resetToolbarLayout);
document.querySelector('#close-selection-panel')?.addEventListener('click', () => setSelectionPanelOpen(false));
openSelectionPanelButton?.addEventListener('click', () => setSelectionPanelOpen(true));
document.querySelector('#collapse-part-properties')?.addEventListener('click', event => {
  const pane = document.querySelector('#part-properties-pane');
  pane?.classList.toggle('collapsed');
  event.currentTarget.textContent = pane?.classList.contains('collapsed') ? '+' : '−';
});
const systemThemeQuery = matchMedia('(prefers-color-scheme: dark)');
themeSelect?.addEventListener('change', () => applyTheme(themeSelect.value));
systemThemeQuery.addEventListener?.('change', () => {
  if ((localStorage.getItem(THEME_KEY) || 'light') === 'system') applyTheme('system', false);
});

window.addEventListener('keydown', event => {
  const editingInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
  if (editingInput && event.key !== 'Escape') return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault();
    runHistory(event.shiftKey ? 'redo' : 'undo').catch(error => notify(error.message));
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
    event.preventDefault();
    runHistory('redo').catch(error => notify(error.message));
    return;
  }
  if (event.key.toLowerCase() === 'q') setTool('select');
  if (event.key.toLowerCase() === 'w') setTool('move');
  if (event.key.toLowerCase() === 'e') setTool('rotate');
  if (event.key.toLowerCase() === 'r') setTool('scale');
  if (event.key.toLowerCase() === 'f') fitView(selectedId ? nodeById.get(selectedId) : model);
  if (event.code === 'Space' && selectedIds.size) { event.preventDefault(); toggleComponentVisibility().catch(error => notify(error.message)); }
  if (event.key === 'Escape') clearSelection();
  if (event.key === 'Delete' && selectedId) document.querySelector('#delete-selected').click();
});

loadPreferences();
restoreToolbarLayout();
setupDraggableToolbars();
setupTreeDelegation();
applyTheme(localStorage.getItem(THEME_KEY) || 'light', false);
initViewer();
applyPreferencesToViewer();
updateUnitUI();
initShareCapture({
  viewer,
  getSourceCanvas: () => {
    if (!renderer) return null;
    renderer.render(scene, camera);
    return renderer.domElement;
  },
  getProjectName: () => currentProject?.name || document.querySelector('#project-title')?.textContent?.trim() || 'CascadeCAD project',
  appPath,
  notify,
});
initCollaboration({
  projectId,
  appPath,
  notify,
  getProjectName: () => currentProject?.name || document.querySelector('#project-title')?.textContent?.trim() || 'CascadeCAD project',
  getSelectedComponentIds: () => [...selectedIds],
  focusComponentIds: ids => {
    clearSelection();
    for (const [index, id] of ids.entries()) {
      if (componentsById.has(id)) selectComponent(id, {fit: index === ids.length - 1, additive: index > 0});
    }
  },
  openSidePanel: () => setSelectionPanelOpen(true),
});
applyTheme(localStorage.getItem(THEME_KEY) || 'light', false);
refreshProject({reloadPreview: true}).catch(() => {});
try {
  const remembered = JSON.parse(localStorage.getItem(ACTIVE_PROJECT_JOB_KEY) || 'null');
  if (remembered?.id) {
    watchJob({id: remembered.id})
      .then(() => refreshProject({reloadPreview: true}))
      .catch(error => notify(error.message));
  }
} catch {
  forgetProjectJob();
}
