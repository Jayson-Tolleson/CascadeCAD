import type { SceneGraph } from '../renderer/sceneGraph';

export function registerboatsLayer(graph: SceneGraph): void {
  graph.upsert({ id: 'mock-boats', layer: 'boats', kind: 'mock', data: { todo: 'replace boats mock with live field truth rendering' } });
}
