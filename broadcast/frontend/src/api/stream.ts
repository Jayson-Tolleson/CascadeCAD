import type { FieldStreamEvent } from '../types/stream';

import type { BBox } from '../types/field';

export interface FieldStreamOptions { bbox?: BBox; tier?: string; }

function streamUrl(options: FieldStreamOptions = {}): string {
  const params = new URLSearchParams();
  if (options.bbox) params.set('bbox', [options.bbox.west, options.bbox.south, options.bbox.east, options.bbox.north].join(','));
  if (options.tier) params.set('tier', options.tier);
  const qs = params.toString();
  return qs ? `/gfs/api/stream?${qs}` : '/gfs/api/stream';
}

export function openFieldStream(onEvent: (event: FieldStreamEvent) => void, options: FieldStreamOptions = {}): EventSource {
  const source = new EventSource(streamUrl(options));
  for (const type of ['scene.heartbeat', 'atmosphere.field.patch', 'cloud.features.patch', 'ocean.field.patch', 'ocean.features.patch', 'locations.patch', 'reports.patch', 'lightning.flash', 'boats.patch'] as const) {
    source.addEventListener(type, (event) => {
      const message = event as MessageEvent<string>;
      onEvent({ type, id: message.lastEventId, payload: JSON.parse(message.data), receivedAt: new Date().toISOString() });
    });
  }
  source.onerror = () => onEvent({ type: 'stream.error', payload: { message: 'SSE connection interrupted' }, receivedAt: new Date().toISOString() });
  return source;
}
