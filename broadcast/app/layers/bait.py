from app.fields.base import FieldPatch


def bait_summary_from_patch(patch: FieldPatch, threshold: float = 0.55) -> dict:
    channels = patch.payload.get('channels', {})
    grid = channels.get('bait_score', [])
    values = [float(value) for row in grid for value in row]
    hot = [value for value in values if value >= threshold]
    return {
        'ok': True,
        'source': 'ocean_truth.bait_score',
        'threshold': threshold,
        'sample_count': len(values),
        'hotspot_count': len(hot),
        'max_score': max(values) if values else 0,
        'mean_score': round(sum(values) / len(values), 3) if values else 0,
        'future_depth_hook': True,
        'future_chlorophyll_boost': True,
        'degraded': not bool(values),
    }
