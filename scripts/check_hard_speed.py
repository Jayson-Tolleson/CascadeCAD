#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import cadquery as cq
import numpy as np

from webcad_xbf.faceted_worker import build_faceted_brep


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    vertices = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (0.0, 10.0, 0.0),
            (0.0, 0.0, 10.0),
        ],
        dtype=np.float64,
    )
    triangles = np.asarray(
        [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        dtype=np.int64,
    )
    with tempfile.TemporaryDirectory(prefix="cascade-cad-hard-speed-smoke-", dir=str(output)) as temp_name:
        temp = Path(temp_name)
        source = temp / "tetra.npz"
        brep = temp / "tetra.brep"
        np.savez(source, vertices=vertices, triangles=triangles)
        report = build_faceted_brep(
            source,
            brep,
            tolerance=0.05,
            fast_sewing=True,
            unify_same_domain=False,
        )
        reopened = cq.Shape.importBrep(str(brep))
        if reopened.isNull() or not reopened.Faces() or not reopened.isValid():
            raise RuntimeError("Hard-speed smoke BREP did not reopen as valid Part geometry")
        if int(report.get("triangle_count", 0)) != 4:
            raise RuntimeError(f"Unexpected hard-speed triangle report: {report}")
        if int(report.get("solid_count", 0)) < 1:
            raise RuntimeError(f"Closed tetrahedron did not become a faceted solid: {report}")
        final = output / "hard-speed-smoke-report.json"
        final.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "CascadeCAD hard-speed OCP smoke test: OK "
            f"({report.get('solid_count', 0)} solids, "
            f"FastSewing used={report.get('fast_sewing_used', False)})"
        )
        return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="/tmp/cascade-cad-hard-speed-smoke")
    args = parser.parse_args()
    run(Path(args.output).resolve())


if __name__ == "__main__":
    main()
