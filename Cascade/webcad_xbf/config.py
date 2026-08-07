from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(primary: str, legacy: str, default: str) -> str:
    """Read the CascadeCAD setting, with v0.1.0 compatibility."""
    return os.getenv(primary, os.getenv(legacy, default))


def _int_env(primary: str, legacy: str, default: int) -> int:
    try:
        return int(_env(primary, legacy, str(default)))
    except ValueError:
        return default


def _float_env(primary: str, legacy: str, default: float) -> float:
    try:
        return float(_env(primary, legacy, str(default)))
    except ValueError:
        return default


def _bool_env(primary: str, legacy: str, default: bool) -> bool:
    value = _env(primary, legacy, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _base_path(value: str) -> str:
    value = value.strip()
    if not value or value == "/":
        return ""
    return "/" + value.strip("/")


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    base_path: str
    storage: Path
    max_upload_bytes: int
    chunk_bytes: int
    storage_reserve_bytes: int
    preview_tolerance: float
    preview_angular_tolerance: float
    worker_poll_seconds: float
    worker_threads: int
    job_recovery_limit: int
    max_faceted_step_triangles: int
    step_export_timeout_seconds: int
    faceted_step_chunk_triangles: int
    max_csg_triangles: int
    faceted_workers: int
    faceted_queue_depth: int
    faceted_memory_budget_gb: float
    faceted_cache_enabled: bool
    faceted_cache_max_bytes: int
    faceted_direct_ocp: bool
    faceted_freecad_fallback: bool
    faceted_unify_same_domain: bool
    secret_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=_env("CASCADE_CAD_HOST", "WEBCAD_HOST", "127.0.0.1"),
            port=_int_env("CASCADE_CAD_PORT", "WEBCAD_PORT", 8790),
            base_path=_base_path(
                _env("CASCADE_CAD_BASE_PATH", "WEBCAD_BASE_PATH", "/cascade-cad")
            ),
            storage=Path(
                _env(
                    "CASCADE_CAD_STORAGE",
                    "WEBCAD_STORAGE",
                    "/home/jayson_tolleson/Cascade/projects",
                )
            ),
            max_upload_bytes=_int_env(
                "CASCADE_CAD_MAX_UPLOAD_BYTES",
                "WEBCAD_MAX_UPLOAD_BYTES",
                8 * 1024**3,
            ),
            chunk_bytes=_int_env(
                "CASCADE_CAD_CHUNK_BYTES",
                "WEBCAD_CHUNK_BYTES",
                16 * 1024**2,
            ),
            storage_reserve_bytes=max(
                256 * 1024**2,
                _int_env(
                    "CASCADE_CAD_STORAGE_RESERVE_BYTES",
                    "WEBCAD_STORAGE_RESERVE_BYTES",
                    1024**3,
                ),
            ),
            preview_tolerance=_float_env(
                "CASCADE_CAD_PREVIEW_TOLERANCE",
                "WEBCAD_PREVIEW_TOLERANCE",
                2.0,
            ),
            preview_angular_tolerance=_float_env(
                "CASCADE_CAD_PREVIEW_ANGULAR_TOLERANCE",
                "WEBCAD_PREVIEW_ANGULAR_TOLERANCE",
                0.30,
            ),
            worker_poll_seconds=_float_env(
                "CASCADE_CAD_WORKER_POLL_SECONDS",
                "WEBCAD_WORKER_POLL_SECONDS",
                1.0,
            ),
            worker_threads=max(
                1,
                _int_env(
                    "CASCADE_CAD_WORKER_THREADS",
                    "WEBCAD_WORKER_THREADS",
                    1,
                ),
            ),
            job_recovery_limit=max(
                0,
                _int_env(
                    "CASCADE_CAD_JOB_RECOVERY_LIMIT",
                    "WEBCAD_JOB_RECOVERY_LIMIT",
                    1,
                ),
            ),
            max_faceted_step_triangles=max(
                1,
                _int_env(
                    "CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES",
                    "WEBCAD_MAX_FACETED_STEP_TRIANGLES",
                    5_000_000,
                ),
            ),
            step_export_timeout_seconds=max(
                60,
                _int_env(
                    "CASCADE_CAD_STEP_EXPORT_TIMEOUT_SECONDS",
                    "WEBCAD_STEP_EXPORT_TIMEOUT_SECONDS",
                    3600,
                ),
            ),
            faceted_step_chunk_triangles=max(
                100,
                _int_env(
                    "CASCADE_CAD_FACETED_STEP_CHUNK_TRIANGLES",
                    "WEBCAD_FACETED_STEP_CHUNK_TRIANGLES",
                    1000,
                ),
            ),
            max_csg_triangles=max(
                1,
                _int_env(
                    "CASCADE_CAD_MAX_CSG_TRIANGLES",
                    "WEBCAD_MAX_CSG_TRIANGLES",
                    10_000_000,
                ),
            ),
            faceted_workers=max(
                1,
                min(32, _int_env("CASCADE_CAD_FACETED_WORKERS", "WEBCAD_FACETED_WORKERS", 2)),
            ),
            faceted_queue_depth=max(
                1,
                min(60, _int_env("CASCADE_CAD_FACETED_QUEUE_DEPTH", "WEBCAD_FACETED_QUEUE_DEPTH", 60)),
            ),
            faceted_memory_budget_gb=max(
                1.0,
                _float_env("CASCADE_CAD_FACETED_MEMORY_BUDGET_GB", "WEBCAD_FACETED_MEMORY_BUDGET_GB", 10.0),
            ),
            faceted_cache_enabled=_bool_env(
                "CASCADE_CAD_FACETED_CACHE_ENABLED", "WEBCAD_FACETED_CACHE_ENABLED", True
            ),
            faceted_cache_max_bytes=max(
                1024**3,
                _int_env(
                    "CASCADE_CAD_FACETED_CACHE_MAX_BYTES",
                    "WEBCAD_FACETED_CACHE_MAX_BYTES",
                    20 * 1024**3,
                ),
            ),
            faceted_direct_ocp=_bool_env(
                "CASCADE_CAD_FACETED_DIRECT_OCP", "WEBCAD_FACETED_DIRECT_OCP", True
            ),
            faceted_freecad_fallback=_bool_env(
                "CASCADE_CAD_FACETED_FREECAD_FALLBACK", "WEBCAD_FACETED_FREECAD_FALLBACK", True
            ),
            faceted_unify_same_domain=_bool_env(
                "CASCADE_CAD_FACETED_UNIFY_SAME_DOMAIN", "WEBCAD_FACETED_UNIFY_SAME_DOMAIN", True
            ),
            secret_key=_env(
                "CASCADE_CAD_SECRET_KEY",
                "WEBCAD_SECRET_KEY",
                "development-only-change-me",
            ),
        )
