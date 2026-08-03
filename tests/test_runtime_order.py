"""Testy kontraktów kolejności runtime bez zależności od Home Assistant."""

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1] / "custom_components" / "adaptive_cover"


def load_module(name: str, filename: str):
    """Wczytaj czysty moduł bez importowania pakietu integracji."""
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


models = load_module("adaptive_cover_models", "models.py")
schedule = load_module("adaptive_cover_schedule", "schedule.py")


class PendingRefreshTests(unittest.TestCase):
    """Sprawdzaj, czy zdarzenia nie giną podczas wykonywania starszej partii."""

    def test_new_event_survives_draining_previous_batch(self) -> None:
        """Zdarzenie dodane po drain należy już do następnego cyklu."""
        pending = models.PendingRefreshes()
        pending.add(models.RefreshTrigger.ENTITY_STATE)

        generation, batch = pending.drain()
        pending.add(models.RefreshTrigger.NIGHT_PURGE_DEADLINE)

        self.assertEqual(1, generation)
        self.assertEqual(
            frozenset({models.RefreshTrigger.ENTITY_STATE}),
            batch,
        )
        self.assertTrue(pending.contains(models.RefreshTrigger.NIGHT_PURGE_DEADLINE))

    def test_duplicate_causes_are_coalesced_without_losing_generation(self) -> None:
        """Scal identyczne przyczyny, zachowując informację o nowszym zdarzeniu."""
        pending = models.PendingRefreshes()
        pending.add(models.RefreshTrigger.ENTITY_STATE)
        pending.add(models.RefreshTrigger.ENTITY_STATE)

        generation, batch = pending.drain()

        self.assertEqual(2, generation)
        self.assertEqual(1, len(batch))


class ScheduleResolutionTests(unittest.TestCase):
    """Sprawdzaj kolejność źródeł końca harmonogramu."""

    def setUp(self) -> None:
        """Przygotuj stały zegar lokalny."""
        self.zone = timezone(timedelta(hours=2))
        self.now = datetime(2026, 7, 29, 12, 0, tzinfo=self.zone)
        self.sunset = datetime(2026, 7, 29, 20, 30, tzinfo=self.zone)

    def test_unavailable_end_entity_falls_back_to_explicit_time(self) -> None:
        """Niedostępna encja nie może wyłączyć poprawnego end_time."""
        result = schedule.resolve_end_time(
            local_now=self.now,
            timezone=self.zone,
            end_entity_configured=True,
            end_entity_value=None,
            explicit_end_time="23:15:00",
            sunset=self.sunset,
            sunset_offset_minutes=-30,
        )

        self.assertEqual("end_time", result.source)
        self.assertEqual(23, result.value.hour)
        self.assertEqual("end_entity_unavailable_or_invalid", result.fallback_reason)

    def test_invalid_entity_and_default_time_fall_back_to_sunset(self) -> None:
        """Zachód jest ostatnim działającym źródłem czasu."""
        result = schedule.resolve_end_time(
            local_now=self.now,
            timezone=self.zone,
            end_entity_configured=True,
            end_entity_value="unavailable",
            explicit_end_time="00:00:00",
            sunset=self.sunset,
            sunset_offset_minutes=-30,
        )

        self.assertEqual("sunset", result.source)
        self.assertEqual(self.sunset - timedelta(minutes=30), result.value)

    def test_next_deadline_rolls_to_tomorrow(self) -> None:
        """Termin, który minął, należy zaplanować na następny dzień."""
        result = schedule.next_local_deadline(
            local_now=self.now,
            configured_time="06:00:00",
            timezone=self.zone,
        )

        self.assertEqual(datetime(2026, 7, 30, 6, 0, tzinfo=self.zone), result)
