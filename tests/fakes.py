"""Lekkie atrapy zależności Home Assistant dla testów runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class FakeServices:
    """Rejestruj wywołania usług bez uruchamiania Home Assistant."""

    def __init__(self, error: Exception | None = None) -> None:
        """Ustaw opcjonalny błąd zwracany przez każde wywołanie."""
        self.error = error
        self.calls: list[tuple[str, str, dict, bool]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict,
        *,
        blocking: bool,
        **_kwargs,
    ) -> None:
        """Zapisz jedno wywołanie usługi."""
        self.calls.append((domain, service, dict(data), blocking))
        if self.error is not None:
            raise self.error


@dataclass
class FakeState:
    """Minimalny stan encji wykorzystywany przez manual override."""

    state: str
    attributes: dict[str, Any]
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class FakeStateChange:
    """Minimalne zdarzenie zmiany położenia rolety."""

    entity_id: str
    old_state: FakeState
    new_state: FakeState


class FakeTimerRegistry:
    """Rejestruj nazwane callbacki czasowe i ich anulowanie."""

    def __init__(self) -> None:
        """Zainicjalizuj pusty rejestr."""
        self.registrations: list[tuple[Any, Any, datetime]] = []
        self.cancelled = 0

    def track(self, hass: Any, callback: Any, target: datetime):
        """Zapisz timer i zwróć funkcję anulującą."""
        self.registrations.append((hass, callback, target))

        def cancel() -> None:
            self.cancelled += 1

        return cancel
