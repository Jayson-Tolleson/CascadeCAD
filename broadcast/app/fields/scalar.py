"""LFTR x/y/z scalar-field primitives.

The renderer should not draw raw provider points.  Provider adapters fill normalized
fields, this engine samples those fields, and render patches/features are derived from
that truth.  The same primitives support atmosphere altitude volumes and ocean depth
volumes.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class ScalarField2D:
    name: str
    values: list[list[float]]
    west: float
    south: float
    east: float
    north: float

    @property
    def rows(self) -> int:
        return len(self.values)

    @property
    def cols(self) -> int:
        return len(self.values[0]) if self.values else 0

    def bilinear(self, lon: float, lat: float, default: float = 0.0) -> float:
        if self.rows == 0 or self.cols == 0:
            return default
        if self.rows == 1 and self.cols == 1:
            return self.values[0][0]
        x = 0.0 if self.east == self.west else (lon - self.west) / (self.east - self.west)
        y = 0.0 if self.north == self.south else (lat - self.south) / (self.north - self.south)
        x = clamp(x)
        y = clamp(y)
        fx = x * max(0, self.cols - 1)
        fy = y * max(0, self.rows - 1)
        x0 = int(fx)
        y0 = int(fy)
        x1 = min(self.cols - 1, x0 + 1)
        y1 = min(self.rows - 1, y0 + 1)
        tx = fx - x0
        ty = fy - y0
        a = self.values[y0][x0]
        b = self.values[y0][x1]
        c = self.values[y1][x0]
        d = self.values[y1][x1]
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def _lower_bound_index(levels: Sequence[float], z: float) -> int:
    if len(levels) <= 1:
        return 0
    for idx in range(len(levels) - 1):
        lo, hi = levels[idx], levels[idx + 1]
        if lo <= z <= hi or hi <= z <= lo:
            return idx
    return 0 if z < min(levels) else len(levels) - 2


@dataclass(frozen=True)
class ScalarField3D:
    name: str
    # values[z_index][row][col]
    values: list[list[list[float]]]
    west: float
    south: float
    east: float
    north: float
    z_levels: list[float]
    z_kind: str = "altitude_or_depth_m"

    @property
    def z_count(self) -> int:
        return len(self.values)

    def layer(self, z_index: int) -> ScalarField2D:
        idx = max(0, min(len(self.values) - 1, z_index))
        return ScalarField2D(self.name, self.values[idx], self.west, self.south, self.east, self.north)

    def trilinear(self, lon: float, lat: float, z: float, default: float = 0.0) -> float:
        if not self.values or not self.z_levels:
            return default
        if len(self.values) == 1 or len(self.z_levels) == 1:
            return self.layer(0).bilinear(lon, lat, default)
        z0_idx = _lower_bound_index(self.z_levels, z)
        z1_idx = min(len(self.z_levels) - 1, z0_idx + 1)
        z0 = self.z_levels[z0_idx]
        z1 = self.z_levels[z1_idx]
        tz = 0.0 if z1 == z0 else clamp((z - z0) / (z1 - z0))
        low = self.layer(z0_idx).bilinear(lon, lat, default)
        high = self.layer(z1_idx).bilinear(lon, lat, default)
        return low * (1 - tz) + high * tz


def depth_label(value: float) -> str:
    return "surface" if abs(value) < 1e-9 else f"{value:g}m"


def parse_depth_levels_m(labels: Sequence[str] | str | None, fallback: Sequence[float] = (0, 10, 25, 50, 100)) -> list[float]:
    if labels is None:
        return [float(v) for v in fallback]
    if isinstance(labels, str):
        parts = [part.strip() for part in labels.split(',') if part.strip()]
    else:
        parts = [str(part).strip() for part in labels if str(part).strip()]
    levels: list[float] = []
    for part in parts:
        lower = part.lower()
        if lower in {"surface", "surf", "sfc"}:
            levels.append(0.0)
            continue
        match = re.search(r"-?\d+(?:\.\d+)?", lower)
        if match:
            levels.append(abs(float(match.group(0))))
    if not levels:
        levels = [float(v) for v in fallback]
    levels = sorted(set(round(v, 3) for v in levels))
    if 0.0 not in levels:
        levels.insert(0, 0.0)
    # A surface-only provider request still keeps backend compatibility by exposing
    # default compute levels for derived features.  Streamed channels remain surface-first.
    if len(levels) == 1 and levels[0] == 0.0:
        levels = [float(v) for v in fallback]
    return levels


def labels_from_depths(levels: Sequence[float]) -> list[str]:
    return [depth_label(float(v)) for v in levels]
