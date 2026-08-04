from uuid import uuid4
from app.fields.base import AtmosphereFieldFrame, FieldPatch, OceanFieldFrame
from app.fields.tiles import tile_id_for_bbox


def encode_atmosphere_json_patch(frame: AtmosphereFieldFrame, lod: int = 0) -> FieldPatch:
    # TODO: add binary Float32Array or quantized encodings once the renderer contract settles.
    return FieldPatch(
        patch_id=f"atm-{uuid4().hex}",
        field_type="atmosphere",
        tile_id=tile_id_for_bbox(frame.bbox, lod),
        bbox=frame.bbox,
        lod=lod,
        channels=list(frame.channels.keys()),
        payload={"valid_time": frame.valid_time, "grid_shape": frame.grid_shape, "levels": frame.levels, "channels": frame.channels, "metadata": frame.metadata},
    )


def encode_ocean_json_patch(frame: OceanFieldFrame, lod: int = 0) -> FieldPatch:
    # TODO: add binary Float32Array or quantized encodings once the renderer contract settles.
    return FieldPatch(
        patch_id=f"ocn-{uuid4().hex}",
        field_type="ocean",
        tile_id=tile_id_for_bbox(frame.bbox, lod),
        bbox=frame.bbox,
        lod=lod,
        channels=list(frame.channels.keys()),
        payload={"valid_time": frame.valid_time, "grid_shape": frame.grid_shape, "depth_levels": frame.depth_levels, "channels": frame.channels, "metadata": frame.metadata},
    )
