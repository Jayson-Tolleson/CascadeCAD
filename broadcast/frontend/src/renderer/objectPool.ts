export class ObjectPool<T extends HTMLElement> {
  private readonly available: T[] = [];
  private readonly active = new Map<string, T>();

  constructor(private readonly create: () => T, private readonly maxSize: number, private readonly parent: HTMLElement) {}

  acquire(id: string): T | undefined {
    const existing = this.active.get(id);
    if (existing) return existing;
    if (this.active.size >= this.maxSize) return undefined;
    const item = this.available.pop() ?? this.create();
    item.dataset.objectId = id;
    this.active.set(id, item);
    if (!item.parentElement) this.parent.appendChild(item);
    return item;
  }

  markUnused(keepIds: Set<string>, fadeClass = 'is-fading'): void {
    for (const [id, item] of this.active) {
      if (!keepIds.has(id)) item.classList.add(fadeClass);
    }
  }

  releaseFaded(): void {
    for (const [id, item] of Array.from(this.active)) {
      if (item.classList.contains('is-fading') && item.style.opacity === '0') {
        this.active.delete(id);
        item.remove();
        item.className = '';
        this.available.push(item);
      }
    }
  }
}
