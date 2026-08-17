"""JSON-serializable Alert v0.2 output contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AlertResult:
    grid_id: str
    alert_required: bool | None
    alert_level: str | None
    alert_reason_codes: tuple[str, ...]
    alert_event_types: tuple[str, ...]
    installation_need_delta: float | None
    previous_risk_level: str | None
    current_risk_level: str | None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["alert_reason_codes"] = list(self.alert_reason_codes)
        result["alert_event_types"] = list(self.alert_event_types)
        return result
