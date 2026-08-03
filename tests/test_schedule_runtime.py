"""Testy działania resolvera i kontrolera harmonogramu."""

from datetime import datetime, timedelta, timezone, tzinfo
import importlib.util
from pathlib import Path
import sys
import unittest
from fakes import FakeTimerRegistry

MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "adaptive_cover" / "schedule.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adaptive_cover_schedule_runtime", MODULE_PATH
)
schedule = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = schedule
SPEC.loader.exec_module(schedule)


class WarsawZone(tzinfo):
    """Minimalny model zmian czasu wymaganych przez testy 2026 roku."""

    def utcoffset(self, value):
        """Zwróć offset letni pomiędzy marcową i październikową zmianą."""
        if value is None:
            return timedelta(hours=1)
        summer = (value.month, value.day) > (3, 29) and (value.month, value.day) < (
            10,
            25,
        )
        if (value.month, value.day) == (3, 29):
            summer = value.hour >= 3
        if (value.month, value.day) == (10, 25):
            summer = value.hour < 3
        return timedelta(hours=2 if summer else 1)

    def dst(self, value):
        """Zwróć różnicę względem czasu standardowego."""
        return self.utcoffset(value) - timedelta(hours=1)

    def tzname(self, value):
        """Zwróć nazwę używaną wyłącznie diagnostycznie."""
        return "CEST" if self.dst(value) else "CET"


class ScheduleControllerTests(unittest.TestCase):
    """Sprawdzaj wymianę i anulowanie timerów."""

    def test_replacing_timer_cancels_previous_registration(self) -> None:
        """Jedna nazwa może wskazywać tylko jeden aktywny callback."""
        registry = FakeTimerRegistry()
        controller = schedule.ScheduleController(object(), registry.track)
        zone = timezone(timedelta(hours=2))

        controller.schedule(
            "end_time",
            datetime(2026, 7, 29, 20, 0, tzinfo=zone),
            object(),
        )
        controller.schedule(
            "end_time",
            datetime(2026, 7, 29, 21, 0, tzinfo=zone),
            object(),
        )

        self.assertEqual(1, registry.cancelled)
        self.assertEqual(21, controller.target("end_time").hour)

    def test_cancel_all_removes_every_timer(self) -> None:
        """Unload integracji nie może pozostawić callbacków."""
        registry = FakeTimerRegistry()
        controller = schedule.ScheduleController(object(), registry.track)
        zone = timezone(timedelta(hours=2))
        target = datetime(2026, 7, 29, 20, 0, tzinfo=zone)
        controller.schedule("end_time", target, object())
        controller.schedule("night_purge", target, object())

        controller.cancel_all()

        self.assertEqual(2, registry.cancelled)
        self.assertIsNone(controller.target("end_time"))
        self.assertIsNone(controller.target("night_purge"))


class ScheduleResolverTests(unittest.TestCase):
    """Sprawdzaj wspólną kolejność wszystkich źródeł czasu."""

    def setUp(self) -> None:
        """Ustaw stałą strefę i resolver."""
        self.zone = timezone(timedelta(hours=2))
        self.now = datetime(2026, 7, 29, 12, 0, tzinfo=self.zone)
        self.resolver = schedule.ScheduleResolver(self.zone)

    def test_unavailable_start_entity_falls_back_to_weekend(self) -> None:
        """Niedostępna encja startu nie może wyłączyć harmonogramu."""
        result = self.resolver.resolve_start(
            local_now=self.now,
            start_entity_configured=True,
            start_entity_value="unavailable",
            workday_configured=True,
            workday_state="off",
            explicit_start_time="06:00:00",
            workday_start_time="07:00:00",
            weekend_start_time="09:00:00",
        )

        self.assertEqual("weekend_start", result.source)
        self.assertEqual(9, result.value.hour)
        self.assertEqual(
            "start_entity_unavailable_or_invalid",
            result.fallback_reason,
        )

    def test_manual_override_uses_next_sunset(self) -> None:
        """Specjalny czas 9999 minut kończy się przy najbliższym zachodzie."""
        sunset_today = datetime(2026, 7, 29, 20, 30, tzinfo=self.zone)
        sunset_tomorrow = sunset_today + timedelta(days=1)

        result = self.resolver.manual_override_deadline(
            reference=self.now,
            duration={"minutes": 9999},
            sunset_today=sunset_today,
            sunset_tomorrow=sunset_tomorrow,
            sunset_offset_minutes=-15,
        )

        self.assertEqual(
            datetime(2026, 7, 29, 20, 15, tzinfo=self.zone),
            result,
        )

    def test_overnight_schedule_is_active_after_midnight(self) -> None:
        """Zakres 22:00-06:00 obejmuje noc po zmianie daty."""
        resolved = schedule.ResolvedSchedule(
            schedule.ResolvedTime(
                datetime(2026, 7, 29, 22, 0, tzinfo=self.zone),
                "start_time",
            ),
            schedule.ResolvedTime(
                datetime(2026, 7, 29, 6, 0, tzinfo=self.zone),
                "end_time",
            ),
        )

        self.assertTrue(resolved.active(datetime(2026, 7, 30, 1, 0, tzinfo=self.zone)))


class DaylightSavingTests(unittest.TestCase):
    """Sprawdzaj lokalne terminy w dniach zmiany czasu."""

    def test_deadline_uses_summer_offset_after_short_night(self) -> None:
        """Termin po zmianie na czas letni ma aktualny offset strefy."""
        zone = WarsawZone()
        now = datetime(2026, 3, 29, 1, 30, tzinfo=zone)

        target = schedule.next_local_deadline(
            local_now=now,
            configured_time="07:00:00",
            timezone=zone,
        )

        self.assertEqual(2 * 60 * 60, target.utcoffset().total_seconds())

    def test_deadline_uses_winter_offset_after_long_night(self) -> None:
        """Termin po zmianie na czas zimowy ma aktualny offset strefy."""
        zone = WarsawZone()
        now = datetime(2026, 10, 25, 1, 30, tzinfo=zone)

        target = schedule.next_local_deadline(
            local_now=now,
            configured_time="07:00:00",
            timezone=zone,
        )

        self.assertEqual(60 * 60, target.utcoffset().total_seconds())
