declare global { namespace JSX { interface IntrinsicElements { 'gmp-map-3d': Record<string, unknown>; } } }

export function createMap3DPlaceholder(): HTMLElement {
  const map = document.createElement('gmp-map-3d');
  map.setAttribute('center', '26.1224,-80.1373,850000');
  map.setAttribute('heading', '0');
  map.setAttribute('tilt', '45');
  map.className = 'globe-map';
  map.innerHTML = '<div class="map-fallback">Google 3D Map placeholder — add API key when ready.</div>';
  return map;
}
