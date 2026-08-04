from app.layers.bait import bait_summary_from_patch
from app.services.field_truth_engine import get_field_truth_engine
from app.schemas.scene import BBox


def bait_field_summary(bbox: BBox, threshold: float = 0.55) -> dict:
    patch, status = get_field_truth_engine().ocean_patch(bbox)
    summary = bait_summary_from_patch(patch, threshold=threshold)
    summary['provider'] = status.model_dump(mode='json')
    return summary
