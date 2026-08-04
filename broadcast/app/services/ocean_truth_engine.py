from app.fields.base import FieldPatch
from app.fields.encoders import encode_ocean_json_patch
from app.providers.provider_status import ProviderStatus
from app.providers.rtofs_ncep import get_rtofs_provider
from app.schemas.scene import BBox


class OceanTruthEngine:
    def ocean_frame(self, bbox: BBox):
        return get_rtofs_provider().fetch_ocean(bbox)

    def ocean_patch(self, bbox: BBox, lod: int = 0) -> tuple[FieldPatch, ProviderStatus]:
        frame, status = self.ocean_frame(bbox)
        patch = encode_ocean_json_patch(frame, lod=lod)
        patch.payload["provider"] = status.model_dump(mode="json")
        patch.payload["metadata"] = frame.metadata
        return patch, status

    def sample(self, lon: float, lat: float, depth_m: float = 0, time: str | None = None):
        return get_rtofs_provider().sample(lon, lat, depth_m, time)


def get_ocean_truth_engine() -> OceanTruthEngine:
    return OceanTruthEngine()
