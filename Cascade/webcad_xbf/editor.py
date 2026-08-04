from __future__ import annotations

import copy
import math
import re
import secrets
from typing import Any

MAX_HISTORY = 100
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_MATERIAL = {
    "name": "Unassigned",
    "density_kg_m3": 0.0,
    "color": "#b8c1cc",
    "description": "",
}


def _finite_vector(value: Any, name: str, limit: float) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numbers")
    result = []
    for item in value:
        number = float(item)
        if not math.isfinite(number) or abs(number) > limit:
            raise ValueError(f"{name} contains an invalid value")
        result.append(number)
    return result


def _scale_vector(value: Any) -> list[float]:
    values = _finite_vector(value, "scale", 1.0e6)
    if any(item <= 0.000001 for item in values):
        raise ValueError("scale values must be greater than 0.000001")
    return values


def normalize_transform(value: Any) -> dict[str, list[float]]:
    if not isinstance(value, dict):
        raise ValueError("transform must be an object")
    return {
        "position": _finite_vector(value.get("position", [0.0, 0.0, 0.0]), "position", 1.0e9),
        "rotation": _finite_vector(value.get("rotation", [0.0, 0.0, 0.0]), "rotation", 1.0e6),
        "scale": _scale_vector(value.get("scale", [1.0, 1.0, 1.0])),
    }


def normalize_material(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    density = float(source.get("density_kg_m3", 0.0) or 0.0)
    if not math.isfinite(density) or density < 0 or density > 100000:
        raise ValueError("material density must be between 0 and 100000 kg/m³")
    color = str(source.get("color") or DEFAULT_MATERIAL["color"]).strip()
    if not _HEX_COLOR.fullmatch(color):
        raise ValueError("material color must use #RRGGBB format")
    return {
        "name": str(source.get("name") or DEFAULT_MATERIAL["name"]).strip()[:120] or "Unassigned",
        "density_kg_m3": density,
        "color": color.lower(),
        "description": str(source.get("description") or "").strip()[:500],
    }


def component_record(component: dict[str, Any]) -> dict[str, Any]:
    component_id = str(component.get("id", "")).strip()
    if not component_id:
        raise ValueError("Component is missing an identifier")
    transform = component.get("transform") or {
        "position": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
    }
    normalized = normalize_transform(transform)
    material = normalize_material(component.get("material"))
    return {
        **copy.deepcopy(component),
        "id": component_id,
        "name": str(component.get("name") or component_id),
        "source_id": str(component.get("source_id") or component_id),
        "base_transform": copy.deepcopy(normalized),
        "transform": copy.deepcopy(normalized),
        "material": material,
        "visible": bool(component.get("visible", True)),
        "deleted": bool(component.get("deleted", False)),
        "duplicate": bool(component.get("duplicate", False)),
    }


def new_state(components: list[dict[str, Any]]) -> dict[str, Any]:
    records = {}
    for component in components:
        record = component_record(component)
        records[record["id"]] = record
    return {
        "version": 2,
        "revision": 0,
        "saved_revision": 0,
        "components": records,
        "undo": [],
        "redo": [],
    }


def migrate_state(state: dict[str, Any]) -> dict[str, Any]:
    """Upgrade editor state written by older CascadeCAD releases in-place."""
    if int(state.get("version", 1)) >= 2:
        # Still normalize records because early development builds may have partial v2 data.
        for component_id, component in list(state.get("components", {}).items()):
            record = component_record(component)
            record["id"] = component_id
            state["components"][component_id] = record
        return state
    upgraded = new_state(list(state.get("components", {}).values()))
    upgraded["revision"] = int(state.get("revision", 0))
    upgraded["saved_revision"] = int(state.get("saved_revision", 0))
    upgraded["undo"] = []
    upgraded["redo"] = []
    return upgraded


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "revision": int(state.get("revision", 0)),
        "saved_revision": int(state.get("saved_revision", 0)),
        "dirty": int(state.get("revision", 0)) != int(state.get("saved_revision", 0)),
        "can_undo": bool(state.get("undo")),
        "can_redo": bool(state.get("redo")),
    }


def component_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    return list(state.get("components", {}).values())


def _history_entry(operation: str, component_id: str, before: Any, after: Any) -> dict[str, Any]:
    return {
        "operation": operation,
        "component_id": component_id,
        "before": copy.deepcopy(before),
        "after": copy.deepcopy(after),
    }


def _apply_record(state: dict[str, Any], component_id: str, record: Any) -> None:
    if record is None:
        state["components"].pop(component_id, None)
    else:
        state["components"][component_id] = copy.deepcopy(record)


def _record_change(
    state: dict[str, Any], operation: str, component_id: str, before: Any, after: Any
) -> dict[str, Any]:
    _apply_record(state, component_id, after)
    state.setdefault("undo", []).append(_history_entry(operation, component_id, before, after))
    state["undo"] = state["undo"][-MAX_HISTORY:]
    state["redo"] = []
    state["revision"] = int(state.get("revision", 0)) + 1
    return state


def _get_component(state: dict[str, Any], component_id: str) -> dict[str, Any]:
    try:
        component = state["components"][component_id]
    except KeyError as exc:
        raise ValueError(f"Unknown component: {component_id}") from exc
    if component.get("deleted"):
        raise ValueError("The selected component is deleted")
    if component.get("editable") is False:
        raise ValueError("The selected assembly node is not directly editable")
    return component


def apply_operation(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    state = migrate_state(state)
    operation = str(payload.get("operation", "")).strip().lower()
    component_id = str(payload.get("component_id", "")).strip()
    if not component_id:
        raise ValueError("component_id is required")

    component = _get_component(state, component_id)
    before = copy.deepcopy(component)

    if operation == "transform":
        after = copy.deepcopy(component)
        after["transform"] = normalize_transform(payload.get("transform"))
        return _record_change(state, operation, component_id, before, after)

    if operation == "material":
        after = copy.deepcopy(component)
        after["material"] = normalize_material(payload.get("material"))
        return _record_change(state, operation, component_id, before, after)

    if operation == "visibility":
        after = copy.deepcopy(component)
        after["visible"] = bool(payload.get("visible", True))
        return _record_change(state, operation, component_id, before, after)

    if operation == "rename":
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("name is required")
        after = copy.deepcopy(component)
        after["name"] = name[:120]
        return _record_change(state, operation, component_id, before, after)

    if operation == "delete":
        after = copy.deepcopy(component)
        after["deleted"] = True
        return _record_change(state, operation, component_id, before, after)

    if operation == "duplicate":
        suffix = secrets.token_hex(3)
        duplicate_id = f"{component_id}_copy_{suffix}"
        after = copy.deepcopy(component)
        after["id"] = duplicate_id
        after["name"] = f"{component.get('name', component_id)} copy"
        after["source_id"] = str(component.get("source_id") or component_id)
        after["duplicate"] = True
        after["deleted"] = False
        position = list(after["transform"]["position"])
        offset = float(payload.get("offset", 100.0))
        if not math.isfinite(offset) or abs(offset) > 1.0e7:
            raise ValueError("Duplicate offset is invalid")
        position[0] += offset
        after["transform"]["position"] = position
        return _record_change(state, operation, duplicate_id, None, after)

    raise ValueError(f"Unsupported editor operation: {operation}")


def apply_batch_operation(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    component_ids = payload.get("component_ids")
    if not isinstance(component_ids, list) or not component_ids:
        return apply_operation(state, payload)
    seen: set[str] = set()
    for value in component_ids:
        component_id = str(value).strip()
        if not component_id or component_id in seen:
            continue
        seen.add(component_id)
        apply_operation(state, {**payload, "component_id": component_id})
    if not seen:
        raise ValueError("component_ids must contain at least one component")
    return state


def undo(state: dict[str, Any]) -> dict[str, Any]:
    state = migrate_state(state)
    history = state.setdefault("undo", [])
    if not history:
        raise ValueError("Nothing to undo")
    entry = history.pop()
    _apply_record(state, entry["component_id"], entry.get("before"))
    state.setdefault("redo", []).append(entry)
    state["revision"] = int(state.get("revision", 0)) + 1
    return state


def redo(state: dict[str, Any]) -> dict[str, Any]:
    state = migrate_state(state)
    history = state.setdefault("redo", [])
    if not history:
        raise ValueError("Nothing to redo")
    entry = history.pop()
    _apply_record(state, entry["component_id"], entry.get("after"))
    state.setdefault("undo", []).append(entry)
    state["revision"] = int(state.get("revision", 0)) + 1
    return state


def mark_saved(state: dict[str, Any], components: list[dict[str, Any]]) -> dict[str, Any]:
    # Preserve per-part materials and visibility metadata if the geometry writer
    # does not round-trip those fields on a particular Open CASCADE build.
    old = migrate_state(state).get("components", {})
    merged = []
    for component in components:
        previous = old.get(str(component.get("id")), {})
        record = dict(component)
        if "material" not in record and previous.get("material"):
            record["material"] = previous["material"]
        if "visible" not in record:
            record["visible"] = previous.get("visible", True)
        merged.append(record)
    fresh = new_state(merged)
    fresh["revision"] = int(state.get("revision", 0))
    fresh["saved_revision"] = fresh["revision"]
    return fresh
