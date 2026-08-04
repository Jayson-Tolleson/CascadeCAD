export interface LayerContract { id: string; label: string; kind: string; enabled: boolean; source: string; status: string; depends_on: string[]; stream_events: string[]; renderer: string; budget: Record<string, number>; degraded: boolean; todo: string[]; }
export interface BoatEntity { id: string; lat: number; lon: number; heading_deg: number; current_u: number; current_v: number; safety: string; model: 'fallback' | 'glb'; }
export interface LightningFlash { id: string; lat: number; lon: number; energy: number; created_at: string; ttl_seconds: number; }
