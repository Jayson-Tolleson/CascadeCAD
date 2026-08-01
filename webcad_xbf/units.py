"""Engineering unit conversion helpers for CascadeCAD.

Internal geometry remains millimetre-based.  Project, display, and export units can
therefore be configured independently without changing persisted geometry.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitSpec:
    key: str
    label: str
    mm_per_unit: float


UNITS: dict[str, UnitSpec] = {
    "in": UnitSpec("in", "Inches", 25.4),
    "ft": UnitSpec("ft", "Feet", 304.8),
    "ft-in": UnitSpec("ft-in", "Feet + Inches", 25.4),
    "yd": UnitSpec("yd", "Yards", 914.4),
    "mm": UnitSpec("mm", "Millimeters", 1.0),
    "cm": UnitSpec("cm", "Centimeters", 10.0),
    "m": UnitSpec("m", "Meters", 1000.0),
}

DEFAULT_PROJECT_UNIT = "mm"
DEFAULT_DISPLAY_UNIT = "in"
DEFAULT_EXPORT_UNIT = "mm"


def normalize_unit(unit: str | None, *, fallback: str = DEFAULT_PROJECT_UNIT) -> str:
    key = str(unit or fallback).strip().lower().replace(" ", "-")
    aliases = {
        "inch": "in", "inches": "in", '"': "in",
        "foot": "ft", "feet": "ft", "'": "ft",
        "feet+inches": "ft-in", "feet-inches": "ft-in", "ft+in": "ft-in",
        "yard": "yd", "yards": "yd",
        "millimeter": "mm", "millimeters": "mm", "millimetre": "mm", "millimetres": "mm",
        "centimeter": "cm", "centimeters": "cm", "centimetre": "cm", "centimetres": "cm",
        "meter": "m", "meters": "m", "metre": "m", "metres": "m",
        "imperial": "in", "metric": "mm",
    }
    key = aliases.get(key, key)
    return key if key in UNITS else fallback


def to_mm(value: float, unit: str | None) -> float:
    key = normalize_unit(unit)
    return float(value) * UNITS[key].mm_per_unit


def from_mm(value_mm: float, unit: str | None) -> float:
    key = normalize_unit(unit)
    return float(value_mm) / UNITS[key].mm_per_unit


def unit_options() -> list[dict[str, str | float]]:
    return [{"key": spec.key, "label": spec.label, "mm_per_unit": spec.mm_per_unit} for spec in UNITS.values()]
