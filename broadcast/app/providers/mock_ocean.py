from app.fields.base import FieldPatch
from app.fields.encoders import encode_ocean_json_patch
from app.fields.ocean import build_mock_ocean_frame
from app.schemas.scene import BBox


def next_ocean_patch(bbox: BBox, lod: int = 0) -> FieldPatch:
    return encode_ocean_json_patch(build_mock_ocean_frame(bbox), lod=lod)
