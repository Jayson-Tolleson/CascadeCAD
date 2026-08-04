import type { SceneSnapshot } from '../types/scene';
import type { BBox } from '../types/field';
import type { ViewportSpatialResponse } from '../types/spatial';

export async function fetchSceneFrame(): Promise<SceneSnapshot> {
  const response = await fetch('/gfs/api/scene-frame');
  if (!response.ok) throw new Error(`Scene frame failed: ${response.status}`);
  return response.json();
}


export async function fetchViewportSpatial(bbox: BBox, tier = 'regional'): Promise<ViewportSpatialResponse> {
  const value = [bbox.west, bbox.south, bbox.east, bbox.north].join(',');
  const response = await fetch(`/gfs/api/viewport-spatial?bbox=${encodeURIComponent(value)}&tier=${encodeURIComponent(tier)}`);
  if (!response.ok) throw new Error(`Viewport spatial failed: ${response.status}`);
  return response.json();
}
