from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, computed_field


class ProviderStatus(BaseModel):
    provider: str
    mode: str
    enabled: bool
    live_ok: bool = False
    cache_hit: bool = False
    degraded: bool = False
    valid_time: str | None = None
    generated_time: str
    error: str | None = None
    details: dict[str, Any] = {}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ok(self) -> bool:
        """Compatibility alias used by server smoke tests and route JSON.

        The project historically used `live_ok`; some direct diagnostics and
        operators naturally check `status.ok`. Treat any enabled live/last-good
        provider response as ok unless it carries a hard error.
        """
        return bool(self.enabled and self.live_ok and not self.error)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
