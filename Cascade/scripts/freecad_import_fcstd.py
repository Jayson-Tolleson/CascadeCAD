"""Headless FCStd exact-shape extractor for CascadeCAD.

Executed inside FreeCADCmd through console stdin. It intentionally exports
final exact shapes as individual BREP files plus JSON metadata; CascadeCAD then
packs them into its canonical XBF assembly and generates the browser preview.
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path

import FreeCAD as App


def _truthy(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _safe(value: str, index: int) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return clean[:100] or f"part_{index:04d}"


def _color(obj) -> str:
    try:
        r, g, b = obj.ViewObject.ShapeColor
        return "#{:02x}{:02x}{:02x}".format(
            max(0, min(255, round(float(r) * 255))),
            max(0, min(255, round(float(g) * 255))),
            max(0, min(255, round(float(b) * 255))),
        )
    except Exception:
        return "#b8c1cc"


def _visible(obj) -> bool:
    try:
        return bool(obj.ViewObject.Visibility)
    except Exception:
        return True


def _property_value(obj, prop: str):
    try:
        value = getattr(obj, prop)
        if hasattr(value, "Value"):
            return float(value.Value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if hasattr(value, "toString"):
            return str(value.toString())
        return str(value)
    except Exception:
        return None


def _properties(obj) -> dict:
    result = {}
    for prop in list(getattr(obj, "PropertiesList", []) or []):
        if prop in {"Shape", "Placement", "ExpressionEngine", "Proxy"}:
            continue
        value = _property_value(obj, prop)
        if value is not None:
            text = value if isinstance(value, (int, float, bool)) else str(value)
            if len(str(text)) <= 500:
                result[prop] = text
    return result


def _is_final_shape_object(obj) -> bool:
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return False
    type_id = str(getattr(obj, "TypeId", ""))
    # A PartDesign::Body already exposes its final Tip shape. Importing each
    # feature below it would duplicate every intermediate pad/pocket/fillet.
    if type_id.startswith("PartDesign::Feature"):
        try:
            if obj.getParentGeoFeatureGroup() is not None:
                return False
        except Exception:
            pass
    if type_id in {"PartDesign::Feature", "PartDesign::FeatureBase"}:
        return False
    return True


def main() -> None:
    source = Path(os.environ["CASCADE_CAD_FCSTD_SOURCE"]).resolve()
    output_dir = Path(os.environ["CASCADE_CAD_FCSTD_OUTPUT_DIR"]).resolve()
    manifest_path = Path(os.environ["CASCADE_CAD_FCSTD_MANIFEST"]).resolve()
    recompute = _truthy("CASCADE_CAD_FCSTD_RECOMPUTE", "1")
    include_hidden = _truthy("CASCADE_CAD_FCSTD_INCLUDE_HIDDEN", "0")
    output_dir.mkdir(parents=True, exist_ok=True)

    document = None
    items = []
    warnings = []
    try:
        document = App.openDocument(str(source))
        if document is None:
            raise RuntimeError("FreeCAD returned no document")
        if recompute:
            try:
                document.recompute()
            except Exception as exc:
                warnings.append(f"Document recompute warning: {exc}")

        names = set()
        for index, obj in enumerate(list(document.Objects), start=1):
            if not _is_final_shape_object(obj):
                continue
            visible = _visible(obj)
            if not include_hidden and not visible:
                continue
            shape = obj.Shape.copy()
            try:
                shape.Placement = obj.getGlobalPlacement()
            except Exception:
                try:
                    shape.Placement = obj.Placement
                except Exception:
                    pass
            base = _safe(str(getattr(obj, "Name", "") or getattr(obj, "Label", "")), index)
            component_id = base
            serial = 2
            while component_id in names:
                component_id = f"{base}_{serial}"
                serial += 1
            names.add(component_id)
            brep_path = output_dir / f"{index:05d}-{component_id}.brep"
            shape.exportBrep(str(brep_path))
            if not brep_path.exists() or brep_path.stat().st_size < 80:
                warnings.append(f"Skipped {getattr(obj, 'Label', component_id)}: empty BREP")
                continue

            material_name = ""
            material_description = ""
            density = 0.0
            for key in ("Material", "MaterialCardName", "MaterialName"):
                try:
                    candidate = getattr(obj, key)
                    if candidate:
                        material_name = str(candidate)
                        break
                except Exception:
                    pass
            items.append({
                "component_id": component_id,
                "name": str(getattr(obj, "Name", component_id)),
                "label": str(getattr(obj, "Label", component_id)),
                "type_id": str(getattr(obj, "TypeId", "")),
                "brep_path": str(brep_path),
                "visible": visible,
                "color": _color(obj),
                "material_name": material_name,
                "material_description": material_description,
                "density_kg_m3": density,
                "properties": _properties(obj),
            })

        manifest_path.write_text(json.dumps({
            "format": "fcstd",
            "source": str(source),
            "document_name": str(getattr(document, "Name", source.stem)),
            "document_label": str(getattr(document, "Label", source.stem)),
            "recomputed": recompute,
            "include_hidden": include_hidden,
            "object_count": len(list(document.Objects)),
            "imported_count": len(items),
            "items": items,
            "warnings": warnings,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        manifest_path.write_text(json.dumps({
            "format": "fcstd",
            "source": str(source),
            "items": items,
            "warnings": warnings,
            "error": traceback.format_exc(),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        traceback.print_exc()
        raise
    finally:
        if document is not None:
            try:
                App.closeDocument(document.Name)
            except Exception:
                pass


if __name__ == "__main__":
    main()
