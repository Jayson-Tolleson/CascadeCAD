from app.fields.atmosphere import build_mock_atmosphere_frame
from app.fields.base import FieldPatch
from app.fields.encoders import encode_atmosphere_json_patch
from app.schemas.scene import BBox


def next_atmosphere_patch(bbox: BBox, lod: int = 0) -> FieldPatch:
    return encode_atmosphere_json_patch(build_mock_atmosphere_frame(bbox), lod=lod)
