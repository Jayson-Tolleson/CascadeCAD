import type { FieldPatch } from '../types/field';

export class FieldStore {
  private atmosphere = new Map<string, FieldPatch>();
  private ocean = new Map<string, FieldPatch>();

  applyPatch(patch: FieldPatch): void {
    const store = patch.field_type === 'atmosphere' ? this.atmosphere : this.ocean;
    store.set(patch.tile_id, patch);
  }

  latest(fieldType: 'atmosphere' | 'ocean'): FieldPatch[] {
    return Array.from((fieldType === 'atmosphere' ? this.atmosphere : this.ocean).values());
  }

  latestPatch(fieldType: 'atmosphere' | 'ocean'): FieldPatch | undefined {
    const patches = this.latest(fieldType);
    return patches[patches.length - 1];
  }
}
