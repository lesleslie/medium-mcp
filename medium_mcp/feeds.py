from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class FeedState:
    name: str
    required: bool = True
    cycles_total: int = 0
    entities_count: int = 0
    last_updated_timestamp: str | None = None
    errors_total: int = 0
    last_error: str | None = None

    def record_cycle(
        self,
        *,
        entities: int = 0,
        error: str | None = None,
    ) -> None:
        self.cycles_total += 1
        if error is not None:
            self.errors_total += 1
            self.last_error = error
            return
        self.entities_count += entities
        self.last_updated_timestamp = datetime.now(UTC).isoformat()

    @property
    def healthy(self) -> bool:
        """A feed is healthy when it has had at least one successful cycle.

        A feed with ``entities_count == 0`` after a successful cycle still
        reports degraded, because the surface-health illusion applies: a
        working transport over an empty upstream is not the same as
        non-empty data.
        """
        if not self.required:
            return self.cycles_total > 0 or self.errors_total == 0
        if self.errors_total > 0 and self.cycles_total == self.errors_total:
            return False
        return self.last_updated_timestamp is not None and self.entities_count > 0

    def mark_capability_unavailable(self, reason: str) -> None:
        if self.required:
            raise ValueError(f"required feed {self.name!r} cannot be marked unavailable: {reason}")
        self.errors_total += 1
        self.last_error = reason


FEEDS: dict[str, FeedState] = {
    "medium2": FeedState(name="medium2", required=True),
}


def required_feeds_healthy() -> bool:
    return all(f.healthy for f in FEEDS.values() if f.required)


def as_components() -> list[dict[str, Any]]:
    return [
        {
            "name": f.name,
            "required": f.required,
            "cycles_total": f.cycles_total,
            "entities_count": f.entities_count,
            "last_updated_timestamp": f.last_updated_timestamp,
            "errors_total": f.errors_total,
            "healthy": f.healthy,
        }
        for f in FEEDS.values()
    ]
