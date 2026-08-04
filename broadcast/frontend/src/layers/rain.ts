import type { SceneGraph } from '../renderer/sceneGraph';

export function registerrainLayer(graph: SceneGraph): void {
  graph.upsert({
    id: 'live-rain-colored-spheres',
    layer: 'rain',
    kind: 'field',
    data: {
      source: 'gfs_ncss_atmosphere.rain_rate',
      renderer: 'Google3DRainColoredSphereColumns',
      behavior: 'colored precipitation spheres fall from derived cloud top to near-ground floor by precip rate',
    },
  });
}
