from __future__ import annotations

import hashlib
import json
import mmap
import os
import re
import shutil
import tempfile
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

Progress = Callable[[int, str], None]

_TAG_PREFIX = rb"(?:[A-Za-z_][A-Za-z0-9_.-]*:)?"
_OBJECT_OPEN_RE = re.compile(rb"<" + _TAG_PREFIX + rb"object\b([^>]*?\bid\s*=\s*([\"'])([0-9]+)\2[^>]*)>", re.I | re.S)
_ITEM_RE = re.compile(rb"<" + _TAG_PREFIX + rb"item\b([^>]*?\bobjectid\s*=\s*([\"'])([0-9]+)\2[^>]*)/\s*>", re.I | re.S)
_COMPONENT_RE = re.compile(rb"<" + _TAG_PREFIX + rb"component\b[^>]*?\bobjectid\s*=\s*([\"'])([0-9]+)\1", re.I | re.S)
_TRIANGLE_RE = re.compile(
    rb"<" + _TAG_PREFIX + rb"triangle\b([^>]*?\bv1\s*=\s*([\"'])([0-9]+)\2[^>]*?\bv2\s*=\s*([\"'])([0-9]+)\4[^>]*?\bv3\s*=\s*([\"'])([0-9]+)\6[^>]*)/\s*>",
    re.I | re.S,
)
_ATTR_RE = re.compile(rb"([A-Za-z_:][A-Za-z0-9_.:-]*)\s*=\s*([\"'])(.*?)\2", re.S)
_ID_ATTR_RE = re.compile(rb"\s+id\s*=\s*([\"'])[0-9]+\1", re.I)
_CLOSE_OBJECT_RE = re.compile(rb"</" + _TAG_PREFIX + rb"object\s*>", re.I)


def _attrs(blob: bytes) -> dict[str, str]:
    return {
        key.decode("utf-8", "replace"): value.decode("utf-8", "replace")
        for key, _quote, value in _ATTR_RE.findall(blob)
    }


def _normalized_transform(attrs: dict[str, str]) -> str:
    return " ".join(attrs.get("transform", "1 0 0 0 1 0 0 0 1 0 0 0").split())


def _copy_zip_entry(source: zipfile.ZipFile, destination: zipfile.ZipFile, info: zipfile.ZipInfo) -> None:
    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    clone.comment = info.comment
    clone.extra = info.extra
    clone.internal_attr = info.internal_attr
    clone.external_attr = info.external_attr
    clone.create_system = info.create_system
    clone.flag_bits = info.flag_bits
    clone.compress_type = zipfile.ZIP_DEFLATED
    with source.open(info, "r") as reader, destination.open(clone, "w", force_zip64=True) as writer:
        shutil.copyfileobj(reader, writer, length=8 * 1024 * 1024)


def _write_without_spans(source: Path, destination: Path, spans: list[tuple[int, int]]) -> None:
    spans = sorted(spans)
    with source.open("rb") as reader, destination.open("wb") as writer:
        cursor = 0
        for start, end in spans:
            if start < cursor:
                continue
            reader.seek(cursor)
            remaining = start - cursor
            while remaining:
                chunk = reader.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("Unexpected end of 3MF model while rewriting")
                writer.write(chunk)
                remaining -= len(chunk)
            cursor = end
        reader.seek(cursor)
        shutil.copyfileobj(reader, writer, length=8 * 1024 * 1024)


def _clean_3mf_model(model_path: Path, output_path: Path, progress: Progress) -> dict[str, Any]:
    start_time = time.time()
    object_rows: list[dict[str, Any]] = []
    item_rows: list[dict[str, Any]] = []
    component_refs: set[str] = set()
    duplicate_face_spans: list[tuple[int, int]] = []
    removed_faces = 0

    with model_path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        resources_end = data.rfind(b"</resources")
        if resources_end < 0:
            resources_end = len(data)
        pos = 0
        index = 0
        while True:
            match = _OBJECT_OPEN_RE.search(data, pos, resources_end)
            if not match:
                break
            close_match = _CLOSE_OBJECT_RE.search(data, match.end(), resources_end)
            if not close_match:
                raise ValueError(f"Unclosed 3MF object {match.group(3).decode()}")
            object_id = match.group(3).decode()
            opening = _ID_ATTR_RE.sub(b"", match.group(0), count=1)
            inner_start = match.end()
            inner_end = close_match.start()
            hasher = hashlib.blake2b(digest_size=32)
            hasher.update(opening)
            hasher.update(data[inner_start:inner_end])
            object_rows.append(
                {
                    "id": object_id,
                    "start": match.start(),
                    "end": close_match.end(),
                    "hash": hasher.hexdigest(),
                }
            )

            # Whole-object coincident duplicates are removed before Trimesh expands the scene.
            # Per-face cleanup is performed by the generic mesh path after import when practical.
            index += 1
            if index % 25 == 0:
                progress(min(28, 8 + index // 5), f"Mesh cleanup: scanned {index} objects")
            pos = close_match.end()

        build_start = data.rfind(b"<build")
        if build_start < 0:
            raise ValueError("3MF model has no build section")
        for item_index, match in enumerate(_ITEM_RE.finditer(data, build_start), start=0):
            attrs = _attrs(match.group(1))
            item_rows.append(
                {
                    "index": item_index,
                    "object_id": match.group(3).decode(),
                    "transform": _normalized_transform(attrs),
                    "other_attrs": tuple(sorted((k, v) for k, v in attrs.items() if k not in {"objectid", "transform"})),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        component_refs = {match.group(2).decode() for match in _COMPONENT_RE.finditer(data, 0, build_start)}

        by_id = {row["id"]: row for row in object_rows}
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for item in item_rows:
            obj = by_id.get(item["object_id"])
            if obj is None:
                continue
            groups[(obj["hash"], item["transform"], item["other_attrs"])].append(item)

        removed_item_spans: list[tuple[int, int]] = []
        removed_item_indices: set[int] = set()
        for entries in groups.values():
            if len(entries) <= 1:
                continue
            for duplicate in entries[1:]:
                removed_item_spans.append((duplicate["start"], duplicate["end"]))
                removed_item_indices.add(duplicate["index"])

        remaining_build_refs: dict[str, int] = defaultdict(int)
        for item in item_rows:
            if item["index"] not in removed_item_indices:
                remaining_build_refs[item["object_id"]] += 1

        removed_object_spans: list[tuple[int, int]] = []
        removed_object_ids: list[str] = []
        for obj in object_rows:
            if remaining_build_refs[obj["id"]] == 0 and obj["id"] not in component_refs:
                removed_object_spans.append((obj["start"], obj["end"]))
                removed_object_ids.append(obj["id"])

        spans = removed_item_spans + removed_object_spans + duplicate_face_spans
        _write_without_spans(model_path, output_path, spans)

    return {
        "format": "3mf",
        "source_objects": len(object_rows),
        "kept_objects": len(object_rows) - len(removed_object_spans),
        "source_build_items": len(item_rows),
        "kept_build_items": len(item_rows) - len(removed_item_spans),
        "removed_coincident_objects": len(removed_item_spans),
        "removed_object_definitions": len(removed_object_spans),
        "removed_duplicate_faces": removed_faces,
        "removed_object_ids": sorted(removed_object_ids, key=lambda value: int(value) if value.isdigit() else value),
        "elapsed_seconds": round(time.time() - start_time, 2),
        "input_model_bytes": model_path.stat().st_size,
        "output_model_bytes": output_path.stat().st_size,
    }


def clean_3mf(source: Path, destination: Path, progress: Progress) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cascade-cad-3mf-clean-") as temp_name:
        temp = Path(temp_name)
        replacements: dict[str, Path] = {}
        model_reports = []
        with zipfile.ZipFile(source, "r") as archive:
            model_infos = [info for info in archive.infolist() if info.filename.lower().endswith(".model")]
            if not model_infos:
                raise ValueError("The 3MF archive contains no .model document")
            for index, info in enumerate(model_infos, start=1):
                progress(5, f"Mesh cleanup: extracting model {index} of {len(model_infos)}")
                extracted = temp / f"model-{index}.xml"
                cleaned = temp / f"model-{index}-cleaned.xml"
                with archive.open(info, "r") as reader, extracted.open("wb") as writer:
                    shutil.copyfileobj(reader, writer, length=8 * 1024 * 1024)
                report = _clean_3mf_model(extracted, cleaned, progress)
                report["entry"] = info.filename
                model_reports.append(report)
                replacements[info.filename] = cleaned

            progress(32, "Mesh cleanup: rebuilding 3MF archive")
            temporary_output = destination.with_name(f".{destination.name}.{time.time_ns()}.tmp")
            with zipfile.ZipFile(
                temporary_output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=3,
                allowZip64=True,
            ) as output:
                for info in archive.infolist():
                    replacement = replacements.get(info.filename)
                    if replacement is None:
                        _copy_zip_entry(archive, output, info)
                        continue
                    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    clone.comment = info.comment
                    clone.extra = info.extra
                    clone.internal_attr = info.internal_attr
                    clone.external_attr = info.external_attr
                    clone.create_system = info.create_system
                    clone.flag_bits = info.flag_bits
                    # Store the cleaned model without recompression. The original source
                    # remains archived; this temporary working 3MF favors import speed and
                    # avoids several minutes of single-core zlib work on large XML meshes.
                    clone.compress_type = zipfile.ZIP_STORED
                    with replacement.open("rb") as reader, output.open(clone, "w", force_zip64=True) as writer:
                        shutil.copyfileobj(reader, writer, length=8 * 1024 * 1024)
            os.replace(temporary_output, destination)

    totals = {
        "removed_coincident_objects": sum(item["removed_coincident_objects"] for item in model_reports),
        "removed_object_definitions": sum(item["removed_object_definitions"] for item in model_reports),
        "removed_duplicate_faces": sum(item["removed_duplicate_faces"] for item in model_reports),
    }
    return {
        "enabled": True,
        "changed": any(totals.values()),
        "format": "3mf",
        "source_file": source.name,
        "cleaned_file": destination.name,
        "input_bytes": source.stat().st_size,
        "working_archive_bytes": destination.stat().st_size,
        "storage_mode": "temporary-uncompressed-model-for-throughput",
        "reduction_percent": round(
            (1 - sum(item["output_model_bytes"] for item in model_reports) / max(1, sum(item["input_model_bytes"] for item in model_reports))) * 100,
            2,
        ),
        **totals,
        "models": model_reports,
    }


def clean_generic_mesh(source: Path, destination: Path, progress: Progress) -> dict[str, Any]:
    import trimesh

    progress(8, "Mesh cleanup: reading mesh")
    loaded = trimesh.load(source, force="scene", process=False)
    scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
    before_faces = 0
    after_faces = 0
    before_vertices = 0
    after_vertices = 0
    total = max(1, len(scene.geometry))
    for index, mesh in enumerate(scene.geometry.values(), start=1):
        if not isinstance(mesh, trimesh.Trimesh):
            continue
        before_faces += len(mesh.faces)
        before_vertices += len(mesh.vertices)
        unique = mesh.unique_faces()
        mesh.update_faces(unique)
        mesh.remove_unreferenced_vertices()
        try:
            mesh.merge_vertices(digits_vertex=15)
        except TypeError:
            mesh.merge_vertices()
        after_faces += len(mesh.faces)
        after_vertices += len(mesh.vertices)
        progress(8 + int(22 * index / total), f"Mesh cleanup: geometry {index} of {total}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.{time.time_ns()}.tmp")
    suffix = destination.suffix.lower().lstrip(".")
    if suffix in {"glb", "gltf"}:
        scene.export(temp, file_type=suffix)
    else:
        # Scene export supports OBJ/PLY/3MF where the installed trimesh extras permit it.
        scene.export(temp, file_type=suffix)
    os.replace(temp, destination)
    return {
        "enabled": True,
        "changed": before_faces != after_faces or before_vertices != after_vertices,
        "format": suffix,
        "source_file": source.name,
        "cleaned_file": destination.name,
        "input_bytes": source.stat().st_size,
        "output_bytes": destination.stat().st_size,
        "removed_duplicate_faces": before_faces - after_faces,
        "removed_duplicate_vertices": before_vertices - after_vertices,
        "source_faces": before_faces,
        "kept_faces": after_faces,
        "source_vertices": before_vertices,
        "kept_vertices": after_vertices,
    }


def clean_mesh_source(source: Path, project_dir: Path, progress: Progress) -> tuple[Path, dict[str, Any]]:
    suffix = source.suffix.lower()
    cleaned = project_dir / "cleanup" / f"working-cleaned-{source.name}"
    if suffix == ".3mf":
        report = clean_3mf(source, cleaned, progress)
    else:
        report = clean_generic_mesh(source, cleaned, progress)
    report_path = project_dir / "cleanup" / "mesh-cleanup.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["report"] = "cleanup/mesh-cleanup.json"
    return cleaned, report
