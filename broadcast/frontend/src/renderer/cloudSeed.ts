export function hashStringToUint32(input: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  h ^= h >>> 16;
  h = Math.imul(h, 2246822507);
  h ^= h >>> 13;
  h = Math.imul(h, 3266489909);
  h ^= h >>> 16;
  return h >>> 0;
}

export class SeededRandom {
  private state: number;

  constructor(seed: string | number) {
    this.state = typeof seed === 'number' ? seed >>> 0 : hashStringToUint32(seed);
    if (this.state === 0) this.state = 0x9e3779b9;
  }

  next(): number {
    // Mulberry32: tiny, deterministic, and good enough for stable cloud body jitter.
    this.state = (this.state + 0x6D2B79F5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  range(min: number, max: number): number {
    return min + (max - min) * this.next();
  }

  signed(scale = 1): number {
    return (this.next() * 2 - 1) * scale;
  }

  fork(label: string): SeededRandom {
    return new SeededRandom(`${this.state}:${label}:${Math.round(this.next() * 1e9)}`);
  }
}

export function seededPhase(seed: string, salt: string): number {
  return (hashStringToUint32(`${seed}:${salt}`) % 62832) / 10000;
}
