import type { SceneGraph } from '../renderer/sceneGraph';

/**
 * Clouds are no longer a mock DOM layer.
 *
 * The active /gfs cloud path is:
 *   GFS NCSS live/last-good atmosphere frame
 *   -> cloud.features.patch
 *   -> optional PostGIS lftr.cloud_render_features read/write-through
 *   -> seeded gmp-polygon-3d cloud body particles in main.ts/cloudParticles.ts.
 *
 * This registration exists only so old layer discovery checks see a real cloud
 * contract. It intentionally does not create synthetic objects.
 */
export function registercloudsLayer(graph: SceneGraph): void {
  graph.upsert({
    id: 'live-clouds-postgis-contract',
    layer: 'clouds',
    kind: 'contract',
    data: {
      source: 'gfs_ncss_live_cloud_features_postgis_render_cache',
      stream: 'cloud.features.patch',
      renderer: 'gmp-polygon-3d seeded cloud particles',
      mock: false,
    },
  });
}
