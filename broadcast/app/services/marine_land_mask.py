from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.schemas.scene import BBox


@dataclass(frozen=True)
class Box:
    name: str
    west: float
    south: float
    east: float
    north: float
    kind: str = "land_core"

    def contains_point(self, lon: float, lat: float) -> bool:
        lon = normalize_lon(lon)
        if self.west <= self.east:
            lon_ok = self.west <= lon <= self.east
        else:
            lon_ok = lon >= self.west or lon <= self.east
        return lon_ok and self.south <= lat <= self.north

    def intersects_bbox(self, bbox: BBox) -> bool:
        for part in split_dateline_bbox(bbox):
            if _boxes_intersect(self.west, self.south, self.east, self.north, part.west, part.south, part.east, part.north):
                return True
        return False


def normalize_lon(lon: float) -> float:
    value = ((float(lon) + 180.0) % 360.0) - 180.0
    # Keep exact 180-ish values stable for user-facing metadata.
    return 180.0 if value == -180.0 and lon > 0 else value


def split_dateline_bbox(bbox: BBox) -> list[BBox]:
    west = normalize_lon(bbox.west)
    east = normalize_lon(bbox.east)
    south = max(-90.0, min(float(bbox.south), float(bbox.north)))
    north = min(90.0, max(float(bbox.south), float(bbox.north)))
    if west <= east:
        return [BBox(west=west, south=south, east=east, north=north)]
    return [BBox(west=west, south=south, east=180.0, north=north), BBox(west=-180.0, south=south, east=east, north=north)]


def pad_bbox(bbox: BBox, pad_deg: float) -> BBox:
    return BBox(
        west=normalize_lon(bbox.west - pad_deg),
        south=max(-90.0, bbox.south - pad_deg),
        east=normalize_lon(bbox.east + pad_deg),
        north=min(90.0, bbox.north + pad_deg),
    )


def _boxes_intersect(w1: float, s1: float, e1: float, n1: float, w2: float, s2: float, e2: float, n2: float) -> bool:
    return not (e1 < w2 or e2 < w1 or n1 < s2 or n2 < s1)


# Conservative interior land cores.  These are intentionally trimmed away from
# coastlines so harbors, bays, estuaries, sounds, deltas, and nearshore tiles are
# allowed through to the marine provider path.  The mask blocks only obvious
# landlocked tiles, which is what saves SST/current/chlorophyll calls safely.
LAND_CORE_BOXES: tuple[Box, ...] = (
    Box("conus_interior_rockies_plains", -113.5, 31.2, -82.5, 48.8),
    Box("canada_interior", -120.0, 50.0, -75.0, 69.5),
    Box("alaska_interior", -160.0, 61.5, -141.5, 68.5),
    Box("mexico_interior", -106.5, 18.0, -96.0, 28.2),
    Box("central_america_interior", -91.5, 13.5, -84.0, 16.8),
    Box("south_america_interior_north", -73.0, -8.0, -50.0, 5.5),
    Box("south_america_interior_south", -70.0, -39.0, -52.0, -9.0),
    Box("europe_central_interior", 5.0, 45.0, 30.0, 59.0),
    Box("iberia_interior", -7.5, 39.0, -2.0, 42.8),
    Box("africa_sahara_interior", -8.0, 18.0, 31.0, 29.0),
    Box("africa_central_interior", 10.0, -9.0, 29.5, 9.0),
    Box("africa_southern_interior", 16.0, -29.0, 31.0, -12.0),
    Box("middle_east_interior", 38.0, 24.0, 52.0, 35.0),
    Box("central_asia_interior", 52.0, 36.0, 86.0, 55.0),
    Box("siberia_interior", 60.0, 56.0, 135.0, 70.0),
    Box("china_mongolia_interior", 83.0, 30.0, 111.0, 48.5),
    Box("india_interior", 74.0, 18.0, 82.0, 26.5),
    Box("australia_interior", 119.0, -33.5, 144.0, -18.0),
)




# Stricter visual-placement land exclusions for entities that should visibly sit
# on water, especially boats.  The provider-level mask above intentionally keeps
# unknown coastal tiles alive so harbors, bays and islands do not lose ocean
# data.  That is too permissive for random boat spawn points: a SoCal viewport
# can include Los Angeles/San Diego land and the old generator may place a boat
# there.  These boxes reject obvious coastal mainland/island land for rendering
# while the explicit MARINE_HARBOR_BAY_BOXES are checked first and remain allowed.
BOAT_RENDER_LAND_EXCLUSION_BOXES: tuple[Box, ...] = (
    # Southern California / Channel Islands operating area.  Harbor/bay boxes
    # above punch holes back into these exclusions before rejection.
    Box("los_angeles_orange_county_mainland_boat_exclusion", -118.72, 33.48, -117.50, 34.42, "boat_land_exclusion"),
    Box("san_diego_county_mainland_boat_exclusion", -117.36, 32.45, -116.65, 33.60, "boat_land_exclusion"),
    Box("ventura_santa_barbara_mainland_boat_exclusion", -120.18, 34.22, -118.55, 35.08, "boat_land_exclusion"),
    Box("socal_inland_mountains_boat_exclusion", -119.75, 34.05, -116.65, 36.45, "boat_land_exclusion"),
    Box("san_clemente_island_land", -118.68, 32.75, -118.25, 33.10, "boat_land_exclusion"),
    Box("santa_catalina_island_land", -118.65, 33.25, -118.25, 33.55, "boat_land_exclusion"),
    Box("san_nicolas_island_land", -119.62, 33.12, -119.35, 33.34, "boat_land_exclusion"),
    Box("santa_cruz_santa_rosa_islands_land", -120.32, 33.85, -119.45, 34.12, "boat_land_exclusion"),
    Box("anacapa_santa_barbara_islands_land", -119.52, 33.43, -119.15, 34.05, "boat_land_exclusion"),
    # California central/north coast major mainland slabs with named bays
    # allowed first by MARINE_HARBOR_BAY_BOXES.
    Box("central_california_mainland_boat_exclusion", -122.55, 34.55, -120.05, 37.35, "boat_land_exclusion"),
    Box("bay_area_mainland_boat_exclusion", -122.75, 37.05, -121.55, 38.45, "boat_land_exclusion"),
    # Pacific Northwest / common U.S. coastal land blocks.
    Box("oregon_washington_coastal_mainland_boat_exclusion", -124.35, 42.0, -122.0, 47.05, "boat_land_exclusion"),
    Box("puget_lowlands_boat_exclusion", -123.35, 47.0, -121.6, 48.7, "boat_land_exclusion"),
    # Gulf / East Coast metro land around common harbors; named bays remain open.
    Box("florida_peninsula_boat_exclusion", -82.85, 25.1, -80.05, 30.35, "boat_land_exclusion"),
    Box("texas_louisiana_coastal_land_boat_exclusion", -97.8, 28.0, -90.0, 31.0, "boat_land_exclusion"),
    Box("mid_atlantic_coastal_land_boat_exclusion", -78.2, 35.5, -73.4, 41.2, "boat_land_exclusion"),
    Box("new_england_coastal_land_boat_exclusion", -72.2, 41.2, -69.5, 44.8, "boat_land_exclusion"),
)


# Explicit marine inclusions.  These let protected waters stay in the ocean path
# even when they are embedded inside a coastline or city bbox.  They are also
# useful diagnostics because the mask can explain why a harbor/bay tile was kept.
MARINE_HARBOR_BAY_BOXES: tuple[Box, ...] = (
    Box("san_diego_bay", -117.28, 32.58, -117.08, 32.76, "harbor_bay"),
    Box("mission_bay", -117.27, 32.75, -117.18, 32.82, "harbor_bay"),
    Box("los_angeles_long_beach_harbor", -118.32, 33.68, -118.05, 33.83, "harbor_bay"),
    Box("newport_bay", -117.94, 33.58, -117.84, 33.64, "harbor_bay"),
    Box("anaheim_huntington_harbour", -118.08, 33.70, -118.00, 33.75, "harbor_bay"),
    Box("channel_islands_nearshore", -120.8, 33.7, -118.0, 34.6, "nearshore_bay"),
    Box("monterey_bay", -122.15, 36.55, -121.65, 37.05, "harbor_bay"),
    Box("san_francisco_bay_delta", -122.65, 37.25, -121.55, 38.25, "harbor_bay"),
    Box("puget_sound", -123.25, 47.0, -122.0, 48.5, "harbor_bay"),
    Box("columbia_river_mouth", -124.15, 45.75, -123.7, 46.35, "estuary"),
    Box("chesapeake_bay", -77.6, 36.8, -75.6, 39.7, "harbor_bay"),
    Box("delaware_bay", -75.75, 38.75, -74.85, 39.45, "harbor_bay"),
    Box("new_york_harbor_long_island_sound", -74.35, 40.35, -72.7, 41.35, "harbor_bay"),
    Box("boston_harbor", -71.12, 42.25, -70.75, 42.45, "harbor_bay"),
    Box("tampa_bay", -82.9, 27.55, -82.35, 28.05, "harbor_bay"),
    Box("mobile_bay", -88.15, 30.25, -87.75, 30.8, "harbor_bay"),
    Box("galveston_bay", -95.25, 29.2, -94.55, 30.05, "harbor_bay"),
    Box("corpus_christi_bay", -97.55, 27.55, -97.05, 28.05, "harbor_bay"),
    Box("miami_biscayne_bay", -80.35, 25.35, -80.05, 25.95, "harbor_bay"),
    Box("charleston_harbor", -80.05, 32.65, -79.75, 32.9, "harbor_bay"),
    Box("savannah_river_estuary", -81.25, 31.9, -80.75, 32.25, "estuary"),
    Box("portland_maine_casco_bay", -70.45, 43.55, -69.9, 43.95, "harbor_bay"),
    Box("great_bahama_bank", -80.5, 22.0, -74.0, 27.5, "shallow_bank"),
    Box("gulf_of_california", -115.5, 23.0, -108.0, 32.0, "gulf_bay"),
    Box("sea_of_cortez_upper", -115.5, 29.0, -112.0, 32.2, "gulf_bay"),
    Box("bay_of_fundy", -67.5, 44.2, -64.5, 46.2, "harbor_bay"),
    Box("st_lawrence_estuary", -71.5, 47.0, -58.5, 51.8, "estuary"),
    Box("hudson_bay", -96.0, 51.0, -75.0, 63.5, "bay"),
    Box("baja_pacific_nearshore", -118.0, 28.0, -114.0, 32.8, "nearshore"),
)


def _sample_points(bbox: BBox, grid: int) -> list[tuple[float, float]]:
    parts = split_dateline_bbox(bbox)
    points: list[tuple[float, float]] = []
    n = max(2, min(9, int(grid)))
    for part in parts:
        for iy in range(n):
            lat = part.south + (part.north - part.south) * (iy / (n - 1))
            for ix in range(n):
                lon = part.west + (part.east - part.west) * (ix / (n - 1))
                points.append((normalize_lon(lon), lat))
    return points


def _containing_box(point: tuple[float, float], boxes: tuple[Box, ...]) -> Box | None:
    lon, lat = point
    for box in boxes:
        if box.contains_point(lon, lat):
            return box
    return None


def _intersecting_boxes(bbox: BBox, boxes: tuple[Box, ...]) -> list[Box]:
    return [box for box in boxes if box.intersects_bbox(bbox)]


@lru_cache(maxsize=2048)
def _cached_mask_key(west: float, south: float, east: float, north: float, pad_deg: float, grid: int, allow_harbors_bays: bool) -> dict[str, Any]:
    bbox = BBox(west=west, south=south, east=east, north=north)
    return _marine_mask_for_bbox_uncached(bbox, pad_deg=pad_deg, grid=grid, allow_harbors_bays=allow_harbors_bays)


def marine_mask_for_bbox(bbox: BBox, *, pad_deg: float | None = None, grid: int | None = None, allow_harbors_bays: bool | None = None) -> dict[str, Any]:
    settings = get_settings()
    pad = settings.marine_land_mask_coast_buffer_deg if pad_deg is None else pad_deg
    samples = settings.marine_land_mask_sample_grid if grid is None else grid
    harbors = settings.marine_land_mask_allow_harbors_bays if allow_harbors_bays is None else allow_harbors_bays
    padded = pad_bbox(bbox, pad)
    # Round the cache key to keep repeated viewport settle calls cheap while still
    # respecting viewport changes near coastlines.
    return _cached_mask_key(
        round(padded.west, 4),
        round(padded.south, 4),
        round(padded.east, 4),
        round(padded.north, 4),
        round(float(pad), 4),
        int(samples),
        bool(harbors),
    )


def _marine_mask_for_bbox_uncached(bbox: BBox, *, pad_deg: float, grid: int, allow_harbors_bays: bool) -> dict[str, Any]:
    harbor_hits = _intersecting_boxes(bbox, MARINE_HARBOR_BAY_BOXES) if allow_harbors_bays else []
    if harbor_hits:
        return {
            "ok": True,
            "should_query_ocean": True,
            "classification": "marine_harbor_bay_or_nearshore",
            "reason": "bbox_intersects_named_harbor_bay_estuary_or_nearshore_box",
            "confidence": 0.96,
            "ocean_fraction_estimate": 1.0,
            "sample_grid": grid,
            "coast_buffer_deg": pad_deg,
            "matched_water": [box.name for box in harbor_hits[:8]],
            "harbors_bays_included": True,
        }

    points = _sample_points(bbox, grid)
    land_hits = 0
    land_names: set[str] = set()
    for point in points:
        box = _containing_box(point, LAND_CORE_BOXES)
        if box:
            land_hits += 1
            land_names.add(box.name)

    total = max(1, len(points))
    possible_water = total - land_hits
    ocean_fraction = possible_water / total
    if possible_water == 0:
        return {
            "ok": True,
            "should_query_ocean": False,
            "classification": "landlocked_interior",
            "reason": "all_sample_points_inside_conservative_land_core_boxes",
            "confidence": 0.92,
            "ocean_fraction_estimate": 0.0,
            "sample_grid": grid,
            "coast_buffer_deg": pad_deg,
            "land_core_hits": sorted(land_names),
            "harbors_bays_included": allow_harbors_bays,
        }

    # Unknown points are intentionally treated as ocean/coastal possible, not as
    # land.  This protects bays, harbors, islands, deltas, fjords, and shoreline
    # tiles from false-negative masking.
    return {
        "ok": True,
        "should_query_ocean": True,
        "classification": "ocean_coastal_or_unknown",
        "reason": "at_least_one_sample_point_not_in_land_core_so_keep_marine_provider_path",
        "confidence": 0.70 if ocean_fraction < 0.35 else 0.86,
        "ocean_fraction_estimate": round(ocean_fraction, 3),
        "sample_grid": grid,
        "coast_buffer_deg": pad_deg,
        "land_core_hits": sorted(land_names),
        "harbors_bays_included": allow_harbors_bays,
    }


def marine_mask_for_point(lon: float, lat: float, *, allow_harbors_bays: bool | None = None) -> dict[str, Any]:
    """Point-level companion to ``marine_mask_for_bbox``.

    The bbox mask decides whether a provider tile is worth querying.  This point
    mask is stricter for renderer inputs: ocean samples, bait clusters, boat
    entities, and shark-intel markers must all pass this gate before they are
    exposed to the frontend.  Unknown coastal/nearshore points are kept as water
    to avoid clipping harbors, bays, islands, fjords, and deltas; only explicit
    conservative land-core points are rejected.
    """
    settings = get_settings()
    harbors = settings.marine_land_mask_allow_harbors_bays if allow_harbors_bays is None else allow_harbors_bays
    point = (normalize_lon(lon), float(lat))
    if harbors:
        water_box = _containing_box(point, MARINE_HARBOR_BAY_BOXES)
        if water_box:
            return {
                "ok": True,
                "is_water": True,
                "should_render_ocean": True,
                "classification": water_box.kind,
                "reason": "point_inside_named_harbor_bay_estuary_or_nearshore_box",
                "matched_water": water_box.name,
                "confidence": 0.97,
            }
    land_box = _containing_box(point, LAND_CORE_BOXES)
    if land_box:
        return {
            "ok": True,
            "is_water": False,
            "should_render_ocean": False,
            "classification": "land_core",
            "reason": "point_inside_conservative_land_core_box",
            "matched_land": land_box.name,
            "confidence": 0.92,
        }
    return {
        "ok": True,
        "is_water": True,
        "should_render_ocean": True,
        "classification": "ocean_coastal_or_unknown",
        "reason": "point_not_inside_conservative_land_core_so_keep_marine_render_path",
        "confidence": 0.72,
    }


def marine_mask_for_boat_point(lon: float, lat: float, *, allow_harbors_bays: bool | None = None) -> dict[str, Any]:
    """Stricter point mask for visible boat placement.

    Ocean provider calls and bait/shark scoring use a permissive coastal mask so
    harbors, bays, fjords and nearshore cells keep data.  Boats are visual
    entities; if their point is in an obvious coastal land slab they should not
    render.  Named harbor/bay boxes are accepted before coastal exclusions.
    """
    settings = get_settings()
    harbors = settings.marine_land_mask_allow_harbors_bays if allow_harbors_bays is None else allow_harbors_bays
    point = (normalize_lon(lon), float(lat))
    if harbors:
        water_box = _containing_box(point, MARINE_HARBOR_BAY_BOXES)
        # For boats, only true enclosed/protected water boxes override land.
        # Broad "nearshore" helper boxes keep ocean providers alive, but they
        # must not punch holes through island/mainland land exclusions.
        if water_box and water_box.kind not in {"nearshore", "nearshore_bay"}:
            return {
                "ok": True,
                "is_water": True,
                "should_render_ocean": True,
                "should_render_boat": True,
                "classification": water_box.kind,
                "reason": "boat_point_inside_named_harbor_bay_estuary_or_nearshore_box",
                "matched_water": water_box.name,
                "confidence": 0.98,
                "boat_point_mask": "harbor_bay_override_allowed",
            }

    base = marine_mask_for_point(point[0], point[1], allow_harbors_bays=False)
    if not base.get("should_render_ocean", True):
        base = dict(base)
        base["should_render_boat"] = False
        base["boat_point_mask"] = "rejected_by_conservative_land_core"
        return base

    land_box = _containing_box(point, BOAT_RENDER_LAND_EXCLUSION_BOXES)
    if land_box:
        return {
            "ok": True,
            "is_water": False,
            "should_render_ocean": False,
            "should_render_boat": False,
            "classification": land_box.kind,
            "reason": "boat_point_inside_strict_visual_land_exclusion_box",
            "matched_land": land_box.name,
            "confidence": 0.88,
            "boat_point_mask": "rejected_by_boat_visual_land_exclusion",
        }

    return {
        "ok": True,
        "is_water": True,
        "should_render_ocean": True,
        "should_render_boat": True,
        "classification": "boat_water_or_unknown_coastal",
        "reason": "boat_point_not_inside_land_core_or_visual_land_exclusion",
        "confidence": 0.76,
        "boat_point_mask": "allowed",
    }


def should_render_marine_point(lon: float, lat: float) -> bool:
    return bool(marine_mask_for_point(lon, lat).get("should_render_ocean", True))


def should_render_boat_point(lon: float, lat: float) -> bool:
    return bool(marine_mask_for_boat_point(lon, lat).get("should_render_boat", False))


def marine_point_filter_summary(points_checked: int, points_kept: int, purpose: str) -> dict[str, Any]:
    skipped = max(0, int(points_checked) - int(points_kept))
    return {
        "purpose": purpose,
        "point_level_mask": True,
        "points_checked": int(points_checked),
        "points_kept": int(points_kept),
        "points_skipped_land": skipped,
        "policy": "reject conservative land-core points; preserve named harbors, bays, estuaries, nearshore and unknown coastal water",
    }
