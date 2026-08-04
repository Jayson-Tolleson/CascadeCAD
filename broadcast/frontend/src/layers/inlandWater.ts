import type { SceneGraph } from '../renderer/sceneGraph';

export function registerinlandWaterLayer(graph: SceneGraph): void {
  graph.upsert({ id: 'mock-inlandWater', layer: 'inlandWater', kind: 'mock', data: { todo: 'replace inlandWater mock with live field truth rendering' } });
}
