import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator
from app.core.config import get_settings
from app.fields.tiles import default_field_bbox
from app.schemas.scene import BBox
from app.services.field_truth_engine import get_field_truth_engine
from app.services.boat_generator import generate_viewport_boats
from app.services.lightning_service import lightning_flashes
from app.spatial.viewport_query import build_viewport_spatial

FIELD_TRUTH_EVENTS = [
    "scene.heartbeat",
    "atmosphere.field.patch",
    "cloud.features.patch",
    "ocean.field.patch",
    "ocean.features.patch",
    "locations.patch",
    "lightning.flash",
    "boats.patch",
]


def sse_message(event: str, event_id: int, payload: dict) -> str:
    return f"event: {event}\nid: {event_id}\ndata: {json.dumps(payload)}\n\n"


async def field_truth_sse_events(
    bbox: BBox | None = None,
    tier: str = "regional",
    debug_raw: bool = False,
) -> AsyncIterator[str]:
    settings = get_settings()
    delay = 1 / max(settings.stream_tick_hz, 0.1)
    bbox = bbox or default_field_bbox()
    counter = 0
    engine = get_field_truth_engine()
    while True:
        event = FIELD_TRUTH_EVENTS[counter % len(FIELD_TRUTH_EVENTS)]
        if event == "atmosphere.field.patch":
            patch, _ = engine.atmosphere_stream_patch(bbox, debug_raw=debug_raw)
            payload = patch.model_dump(mode="json")
        elif event == "cloud.features.patch":
            payload, _ = engine.cloud_features_patch(bbox, tier=tier, debug_raw=debug_raw)
        elif event == "ocean.field.patch":
            patch, _ = engine.ocean_stream_patch(bbox, debug_raw=debug_raw)
            payload = patch.model_dump(mode="json")
        elif event == "ocean.features.patch":
            payload, _ = engine.ocean_features_patch(bbox, tier=tier, debug_raw=debug_raw)
        elif event == "locations.patch":
            spatial = build_viewport_spatial(bbox, tier=tier)
            reports = spatial.get("locations", spatial.get("reports", []))
            payload = {
                "ok": True,
                "bbox": bbox.model_dump(mode="json"),
                "tier": tier,
                "locations": reports,
                "reports": reports,
                "source": spatial.get("diagnostics", {}).get("source", spatial.get("spatial_mode", "viewport-spatial")),
                "postgis": spatial.get("postgis", {}),
            }
        elif event == "lightning.flash":
            payload = lightning_flashes(bbox)
        elif event == "boats.patch":
            payload = generate_viewport_boats(bbox, count=6)
        else:
            payload = {
                "ok": True,
                "sequence": counter,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider_mode": settings.provider_mode,
                "stream_tick_seconds": round(delay, 3),
                "future_target_fps": settings.target_stream_fps,
                "debug_raw": bool(debug_raw),
                "message": "heartbeat: field stream alive; providers emit live/last-good data or honest no-data patches",
            }
        yield sse_message(event, counter, payload)
        counter += 1
        await asyncio.sleep(delay)
