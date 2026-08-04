import csv
import re
from pathlib import Path
from app.schemas.scene import BBox
from app.spatial.base import ReportPoint

EXAMPLE_REPORTS = """id,title,lat,lon,observed_at,summary
report-port-everglades,Bait flicker off Port Everglades,26.091,-80.116,2026-06-16T00:00:00Z,Small bait pods near inlet edge
report-key-largo,Rain shelf near Key Largo,25.095,-80.438,2026-06-16T00:10:00Z,Light rain band drifting northeast
report-bimini,Current rip east of Bimini,25.728,-79.298,2026-06-16T00:20:00Z,Visible rip line with scattered birds
"""


def ensure_example_reports(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(EXAMPLE_REPORTS, encoding="utf-8")


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _first_nonblank(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _report_index_keys(row: dict[str, str]) -> list[str]:
    def sort_key(key: str) -> int:
        try:
            return int(key.split("_", 1)[1])
        except Exception:
            return 9999
    return sorted([key for key, value in row.items() if key.startswith("report_") and _clean(value)], key=sort_key)


def _report_from_zippy_row(row: dict[str, str], index: int) -> ReportPoint | None:
    try:
        latitude = float(row.get("lat", ""))
        longitude = float(row.get("lon", ""))
    except ValueError:
        return None
    report_keys = _report_index_keys(row)
    reports = [_clean(row.get(key)) for key in report_keys]
    title = _first_nonblank(row, ["name", "location"]) or f"LFTR fishing location {index}"
    location = _clean(row.get("location"))
    summary = " | ".join(reports[:3]) or location or title
    csv_fields = {key: _clean(value) for key, value in row.items() if _clean(value)}
    return ReportPoint(
        id=f"zippy-location-{index}",
        title=title,
        latitude=latitude,
        longitude=longitude,
        observed_at="legacy-zippy-csv",
        summary=summary,
        source="zippy_fishloclist_csv",
        csv_fields=csv_fields,
        report_indices=report_keys,
    )


def _report_from_standard_row(row: dict[str, str], index: int) -> ReportPoint | None:
    try:
        latitude = float(row.get("lat", row.get("latitude", "")))
        longitude = float(row.get("lon", row.get("longitude", "")))
    except ValueError:
        return None
    csv_fields = {key: _clean(value) for key, value in row.items() if _clean(value)}
    report_keys = _report_index_keys(row)
    return ReportPoint(
        id=_clean(row.get("id")) or f"csv-location-{index}",
        title=_clean(row.get("title")) or _clean(row.get("name")) or f"LFTR fishing location {index}",
        latitude=latitude,
        longitude=longitude,
        observed_at=_clean(row.get("observed_at")) or _clean(row.get("date")) or "csv",
        summary=_clean(row.get("summary")) or _first_nonblank(row, report_keys[:3]) or _clean(row.get("location")) or "CSV location",
        source=_clean(row.get("source")) or "csv",
        csv_fields=csv_fields,
        report_indices=report_keys,
    )


def load_reports(path: Path) -> list[ReportPoint]:
    ensure_example_reports(path)
    reports: list[ReportPoint] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        is_zippy = "report_1" in fieldnames and "name" in fieldnames and "id" not in fieldnames
        for index, row in enumerate(reader, start=1):
            report = _report_from_zippy_row(row, index) if is_zippy else _report_from_standard_row(row, index)
            if report:
                reports.append(report)
    return reports


def filter_reports_by_bbox(reports: list[ReportPoint], bbox: BBox) -> list[ReportPoint]:
    return [report for report in reports if bbox.west <= report.longitude <= bbox.east and bbox.south <= report.latitude <= bbox.north]
