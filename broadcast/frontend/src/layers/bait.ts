import type { SceneGraph } from '../renderer/sceneGraph';

export function registerbaitLayer(graph: SceneGraph): void {
  graph.upsert({ id: 'mock-bait', layer: 'bait', kind: 'mock', data: { todo: 'replace bait mock with live field truth rendering' } });
}
