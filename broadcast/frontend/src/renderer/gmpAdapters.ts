export function projectMockLonLat(lon: number, lat: number): { x: number; y: number } { return { x: ((lon + 125) / 8) * 100, y: (1 - ((lat - 32) / 6)) * 100 }; }
