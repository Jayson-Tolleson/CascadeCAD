export interface AnimatedLayer { tick(deltaSeconds: number, now: number): void; }

export class AnimationLoop {
  private frame = 0;
  private last = performance.now();
  private running = false;
  private readonly layers: AnimatedLayer[] = [];

  add(layer: AnimatedLayer): void { this.layers.push(layer); }

  start(): void {
    if (this.running) return;
    this.running = true;
    const step = (now: number) => {
      if (!this.running) return;
      const deltaSeconds = Math.min(0.05, (now - this.last) / 1000);
      this.last = now;
      for (const layer of this.layers) layer.tick(deltaSeconds, now);
      this.frame = requestAnimationFrame(step);
    };
    this.frame = requestAnimationFrame(step);
  }

  stop(): void { this.running = false; cancelAnimationFrame(this.frame); }
}
