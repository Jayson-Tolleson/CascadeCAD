export function lerp(current: number, target: number, alpha: number): number {
  return current + (target - current) * alpha;
}

export function damp(current: number, target: number, deltaSeconds: number, speed = 8): number {
  const alpha = 1 - Math.exp(-speed * deltaSeconds);
  return lerp(current, target, alpha);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
