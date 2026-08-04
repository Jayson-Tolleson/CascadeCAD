import type { SceneGraph } from '../renderer/sceneGraph';

export function registeroceanLayer(graph: SceneGraph): void {
  graph.upsert({ id: 'mock-ocean', layer: 'ocean', kind: 'mock', data: { todo: 'replace ocean mock with live field truth rendering' } });
}
