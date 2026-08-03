"""Czyste rozstrzyganie harmonogramów Adaptive Cover."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from typing import Any


@dataclass(frozen=True, slots=True)
class ResolvedTime:
    """Wynik wyboru źródła czasu wraz z informacją diagnostyczną."""

    value: datetime | None
    source: str
    raw_value: Any = None
    fallback_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedSchedule:
    """Kompletny, diagnostyczny wynik rozstrzygnięcia harmonogramu."""

    start: ResolvedTime
    end: ResolvedTime

    def active(self, now: datetime) -> bool:
        """Sprawdź zakres, również wtedy, gdy przechodzi przez północ."""
        if self.start.value is None:
            return self.end.value is None or now < self.end.value
        if self.end.value is None:
            return now >= self.start.value
        if self.start.value <= self.end.value:
            return self.start.value <= now < self.end.value
        return now >= self.start.value or now < self.end.value


class ScheduleResolver:
    """Rozstrzygaj wszystkie czasy bez zależności od Home Assistant."""

    def __init__(self, timezone: tzinfo) -> None:
        """Zapisz strefę używaną przez wszystkie źródła czasu."""
        self.timezone = timezone

    def resolve_start(
        self,
        *,
        local_now: datetime,
        start_entity_configured: bool,
        start_entity_value: Any,
        workday_configured: bool,
        workday_state: Any,
        explicit_start_time: Any,
        workday_start_time: Any,
        weekend_start_time: Any,
    ) -> ResolvedTime:
        """Wybierz start: encja, Workday/Weekend, następnie wartość zwykła."""
        entity_result = self._start_entity_result(
            local_now,
            start_entity_configured,
            start_entity_value,
        )
        if entity_result is not None and entity_result.value is not None:
            return entity_result
        configured, source, workday_fallback = self._configured_start_source(
            workday_configured=workday_configured,
            workday_state=workday_state,
            explicit_start_time=explicit_start_time,
            workday_start_time=workday_start_time,
            weekend_start_time=weekend_start_time,
        )
        fallback = entity_result.fallback_reason if entity_result is not None else None
        return self._parsed_start_result(
            local_now=local_now,
            configured=configured,
            source=source,
            explicit_start_time=explicit_start_time,
            fallback_reason=fallback or workday_fallback,
        )

    def _start_entity_result(
        self,
        local_now: datetime,
        configured: bool,
        value: Any,
    ) -> ResolvedTime | None:
        """Rozstrzygnij opcjonalną encję startu."""
        if not configured:
            return None
        parsed = parse_local_datetime(
            value,
            local_now=local_now,
            timezone=self.timezone,
        )
        if parsed is not None:
            return ResolvedTime(parsed, "start_entity", value)
        return ResolvedTime(
            None,
            "start_entity",
            value,
            "start_entity_unavailable_or_invalid",
        )

    def _parsed_start_result(
        self,
        *,
        local_now: datetime,
        configured: Any,
        source: str,
        explicit_start_time: Any,
        fallback_reason: str | None,
    ) -> ResolvedTime:
        """Parsuj wybrane źródło i zastosuj zwykły start jako fallback."""
        parsed = parse_local_datetime(
            configured,
            local_now=local_now,
            timezone=self.timezone,
        )
        if parsed is not None:
            return ResolvedTime(parsed, source, configured, fallback_reason)
        default_start = parse_local_datetime(
            explicit_start_time,
            local_now=local_now,
            timezone=self.timezone,
        )
        if default_start is not None:
            return ResolvedTime(
                default_start,
                "start_time",
                explicit_start_time,
                fallback_reason or f"{source}_invalid",
            )
        return ResolvedTime(
            None,
            "unavailable",
            configured,
            fallback_reason or "start_time_invalid",
        )

    @staticmethod
    def _configured_start_source(
        *,
        workday_configured: bool,
        workday_state: Any,
        explicit_start_time: Any,
        workday_start_time: Any,
        weekend_start_time: Any,
    ) -> tuple[Any, str, str | None]:
        """Wybierz skonfigurowane źródło bez parsowania daty."""
        if not workday_configured:
            return explicit_start_time, "start_time", None
        normalized = str(workday_state).lower()
        is_workday = normalized != "off"
        configured = workday_start_time if is_workday else weekend_start_time
        source = "workday_start" if is_workday else "weekend_start"
        fallback = (
            None if normalized in {"on", "off"} else "workday_unavailable_assumed_on"
        )
        return configured, source, fallback

    def resolve(
        self,
        *,
        local_now: datetime,
        start_entity_configured: bool,
        start_entity_value: Any,
        workday_configured: bool,
        workday_state: Any,
        explicit_start_time: Any,
        workday_start_time: Any,
        weekend_start_time: Any,
        end_entity_configured: bool,
        end_entity_value: Any,
        explicit_end_time: Any,
        sunset: datetime | None,
        sunset_offset_minutes: int | float,
    ) -> ResolvedSchedule:
        """Zwróć jeden wynik używany przez wykonanie, sensory i diagnostykę."""
        return ResolvedSchedule(
            start=self.resolve_start(
                local_now=local_now,
                start_entity_configured=start_entity_configured,
                start_entity_value=start_entity_value,
                workday_configured=workday_configured,
                workday_state=workday_state,
                explicit_start_time=explicit_start_time,
                workday_start_time=workday_start_time,
                weekend_start_time=weekend_start_time,
            ),
            end=resolve_end_time(
                local_now=local_now,
                timezone=self.timezone,
                end_entity_configured=end_entity_configured,
                end_entity_value=end_entity_value,
                explicit_end_time=explicit_end_time,
                sunset=sunset,
                sunset_offset_minutes=sunset_offset_minutes,
            ),
        )

    def manual_override_deadline(
        self,
        *,
        reference: datetime,
        duration: dict[str, int | float],
        sunset_today: datetime | None,
        sunset_tomorrow: datetime | None,
        sunset_offset_minutes: int | float,
    ) -> datetime:
        """Wyznacz reset ręczny po czasie albo przy najbliższym zachodzie."""
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=self.timezone)
        if duration.get("minutes") != 9999:
            return reference + timedelta(**duration)

        offset = timedelta(minutes=float(sunset_offset_minutes))
        for sunset_value in (sunset_today, sunset_tomorrow):
            if sunset_value is not None and sunset_value + offset > reference:
                return sunset_value + offset
        return reference + timedelta(minutes=9999)

    def next_deadline(
        self,
        *,
        local_now: datetime,
        configured_time: str,
    ) -> datetime | None:
        """Wyznacz kolejny termin w strefie całego harmonogramu."""
        return next_local_deadline(
            local_now=local_now,
            configured_time=configured_time,
            timezone=self.timezone,
        )

    def night_purge_overdue(
        self,
        *,
        local_now: datetime,
        configured_time: str,
        start_time: datetime | None,
    ) -> bool:
        """Sprawdź pominięty poranny termin po restarcie integracji."""
        try:
            close_time = time.fromisoformat(configured_time)
        except (TypeError, ValueError):
            return False
        if close_time >= time(12) or local_now.time() < close_time:
            return False
        if start_time is None:
            return False
        local_start = start_time.astimezone(self.timezone)
        return local_now < local_start


class ScheduleController:
    """Zarządzaj nazwanymi timerami powiązanymi z cyklem życia wpisu."""

    def __init__(self, hass: Any, track_point: Callable) -> None:
        """Zapisz zależność Home Assistant bez importowania jej w tym module."""
        self._hass = hass
        self._track_point = track_point
        self._listeners: dict[str, Callable] = {}
        self._targets: dict[str, datetime] = {}

    def schedule(
        self,
        name: str,
        target: datetime,
        callback: Callable,
    ) -> Callable:
        """Utwórz lub zastąp timer o wskazanej nazwie."""
        self.cancel(name)
        listener = self._track_point(self._hass, callback, target)
        self._listeners[name] = listener
        self._targets[name] = target
        return listener

    def cancel(self, name: str) -> None:
        """Anuluj timer i usuń jego termin diagnostyczny."""
        listener = self._listeners.pop(name, None)
        if listener is not None:
            listener()
        self._targets.pop(name, None)

    def mark_fired(self, name: str) -> None:
        """Usuń timer, którego callback został już wywołany."""
        self._listeners.pop(name, None)
        self._targets.pop(name, None)

    def cancel_all(self) -> None:
        """Anuluj wszystkie timery przy wyładowaniu integracji."""
        for name in tuple(self._listeners):
            self.cancel(name)

    def target(self, name: str) -> datetime | None:
        """Zwróć zaplanowany termin wskazanego timera."""
        return self._targets.get(name)


def parse_local_datetime(
    value: Any,
    *,
    local_now: datetime,
    timezone: tzinfo,
) -> datetime | None:
    """Zamień godzinę lub znacznik czasu na świadomą datę lokalną."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "unavailable", "none"}:
        return None

    try:
        parsed_time = time.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone)
        return parsed.astimezone(timezone)

    return datetime.combine(local_now.date(), parsed_time, tzinfo=timezone)


def resolve_end_time(
    *,
    local_now: datetime,
    timezone: tzinfo,
    end_entity_configured: bool,
    end_entity_value: Any,
    explicit_end_time: Any,
    sunset: datetime | None,
    sunset_offset_minutes: int | float,
) -> ResolvedTime:
    """Wybierz dostępne źródło końca w jednej, jawnej kolejności."""
    fallback_reason = None
    if end_entity_configured:
        entity_time = parse_local_datetime(
            end_entity_value,
            local_now=local_now,
            timezone=timezone,
        )
        if entity_time is not None:
            return ResolvedTime(entity_time, "end_entity", end_entity_value)
        fallback_reason = "end_entity_unavailable_or_invalid"

    if explicit_end_time not in {None, "", "00:00:00"}:
        configured_time = parse_local_datetime(
            explicit_end_time,
            local_now=local_now,
            timezone=timezone,
        )
        if configured_time is not None:
            return ResolvedTime(
                configured_time,
                "end_time",
                explicit_end_time,
                fallback_reason,
            )
        fallback_reason = "end_time_invalid"

    if sunset is None:
        return ResolvedTime(
            None,
            "unavailable",
            None,
            fallback_reason or "sunset_unavailable",
        )
    return ResolvedTime(
        sunset + timedelta(minutes=float(sunset_offset_minutes)),
        "sunset",
        sunset.isoformat(),
        fallback_reason,
    )


def next_local_deadline(
    *,
    local_now: datetime,
    configured_time: str,
    timezone: tzinfo,
) -> datetime | None:
    """Wyznacz najbliższe wystąpienie lokalnej godziny."""
    try:
        deadline_time = time.fromisoformat(configured_time)
    except (TypeError, ValueError):
        return None

    target = datetime.combine(local_now.date(), deadline_time, tzinfo=timezone)
    if target <= local_now:
        target = datetime.combine(
            local_now.date() + timedelta(days=1),
            deadline_time,
            tzinfo=timezone,
        )
    return target
