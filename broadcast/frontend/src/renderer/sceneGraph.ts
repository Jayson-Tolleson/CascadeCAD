export interface SceneObject { id: string; layer: string; kind: string; data: Record<string, unknown>; }

export class SceneGraph {
  private objects = new Map<string, SceneObject>();

  upsert(object: SceneObject): void { this.objects.set(object.id, object); }
  remove(id: string): void { this.objects.delete(id); }
  get(id: string): SceneObject | undefined { return this.objects.get(id); }
  all(): SceneObject[] { return Array.from(this.objects.values()); }
}
