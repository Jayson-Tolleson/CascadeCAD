import type { FieldPatch } from '../types/field';

export interface FieldSample { id: string; x: number; y: number; lat: number; lon: number; values: Record<string, number>; }

export function samplePatchGrid(patch: FieldPatch | undefined, limit: number): FieldSample[] {
  if (!patch) return [];
  const channels = patch.payload.channels as Record<string, number[][]> | undefined;
  const shape = patch.payload.grid_shape as [number, number] | undefined;
  if (!channels || !shape) return [];
  const [rows, cols] = shape;
  const samples: FieldSample[] = [];
  const stride = Math.max(1, Math.ceil(Math.sqrt((rows * cols) / Math.max(1, limit))));
  for (let row = 0; row < rows; row += stride) {
    for (let col = 0; col < cols; col += stride) {
      if (samples.length >= limit) return samples;
      const x = cols <= 1 ? 0 : col / (cols - 1);
      const y = rows <= 1 ? 0 : row / (rows - 1);
      const values: Record<string, number> = {};
      for (const [name, grid] of Object.entries(channels)) values[name] = grid[row]?.[col] ?? 0;
      samples.push({ id: `${patch.tile_id}:${row}:${col}`, x, y, lon: patch.bbox.west + (patch.bbox.east - patch.bbox.west) * x, lat: patch.bbox.south + (patch.bbox.north - patch.bbox.south) * y, values });
    }
  }
  return samples;
}
