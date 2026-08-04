export type LayerId = 'locations' | 'clouds' | 'rain' | 'bait' | 'boats' | 'shark-intel' | 'inland-water' | 'lightning';

export interface LayerPillSpec { id: LayerId; label: string; }

export const LAYERS: LayerPillSpec[] = [
  { id: 'locations', label: 'Locations' },
  { id: 'clouds', label: 'Clouds' },
  { id: 'rain', label: 'Rain' },
  { id: 'bait', label: 'Bait' },
  { id: 'boats', label: 'Boats' },
  { id: 'shark-intel', label: 'Shark Intel' },
  { id: 'inland-water', label: 'Inland Water' },
  { id: 'lightning', label: 'Lightning' },
];

export function renderLayerPills(
  enabled: Set<LayerId>,
  onToggle: (id: LayerId, enabled: boolean) => void,
): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'layer-pills';
  wrapper.setAttribute('aria-label', 'LFTR map layers');

  for (const layer of LAYERS) {
    const pill = document.createElement('button');
    pill.className = 'layer-pill';
    pill.type = 'button';
    pill.dataset.layerId = layer.id;
    pill.textContent = layer.label;

    const sync = () => {
      const isOn = enabled.has(layer.id);
      pill.classList.toggle('is-on', isOn);
      pill.classList.toggle('is-off', !isOn);
      pill.setAttribute('aria-pressed', String(isOn));
      pill.title = `${layer.label}: ${isOn ? 'on' : 'off'}`;
    };

    pill.addEventListener('click', () => {
      if (enabled.has(layer.id)) enabled.delete(layer.id);
      else enabled.add(layer.id);
      sync();
      onToggle(layer.id, enabled.has(layer.id));
    });

    sync();
    wrapper.appendChild(pill);
  }
  return wrapper;
}
