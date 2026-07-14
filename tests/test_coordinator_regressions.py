"""Testy regresyjne struktury koordynatora niewymagające instalacji Home Assistant."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
COORDINATOR_PATH = (
    ROOT / "custom_components" / "adaptive_cover" / "coordinator.py"
)
INIT_PATH = ROOT / "custom_components" / "adaptive_cover" / "__init__.py"
SWITCH_PATH = ROOT / "custom_components" / "adaptive_cover" / "switch.py"
CALCULATION_PATH = ROOT / "custom_components" / "adaptive_cover" / "calculation.py"


def function_named(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Return one named function from a parsed module."""
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


class NightPurgeDeadlineTests(unittest.TestCase):
    """Pilnuj, aby koniec nocnego wietrzenia wykonywał rzeczywiste zamknięcie."""

    @classmethod
    def setUpClass(cls) -> None:
        """Wczytaj strukturę kodu bez importowania zależności Home Assistant."""
        cls.tree = ast.parse(COORDINATOR_PATH.read_text(encoding="utf-8"))
        cls.callback = function_named(cls.tree, "async_close_after_night_purge")
        cls.apply_close = function_named(cls.tree, "_async_apply_night_purge_close")

    def test_deadline_sends_close_position_directly(self) -> None:
        """Nie przepuszczaj zamknięcia przez dzienną blokadę harmonogramu."""
        calls = [
            node
            for node in ast.walk(self.apply_close)
            if isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "self.async_set_manual_position"
        ]

        self.assertEqual(1, len(calls))
        self.assertEqual("cover", ast.unparse(calls[0].value.args[0]))
        self.assertEqual("close_position", ast.unparse(calls[0].value.args[1]))
        self.assertIn(
            "enforce_current_target=False",
            ast.unparse(calls[0].value),
        )

    def test_deadline_respects_window_and_manual_control(self) -> None:
        """Zachowaj zabezpieczenia użytkownika podczas wymuszonego końca wietrzenia."""
        calls = {
            ast.unparse(node.func)
            for node in ast.walk(self.apply_close)
            if isinstance(node, ast.Call)
        }

        self.assertIn("self.async_handle_window_policy", calls)
        self.assertIn("self.manager.is_cover_manual", calls)
        self.assertIn("self.manager.reset_if_needed", calls)

    def test_deadline_does_not_reenable_normal_state_change(self) -> None:
        """Nie wracaj do ścieżki blokowanej przed godziną startu automatyki."""
        assignments = [
            node
            for node in ast.walk(self.callback)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and ast.unparse(target) == "self.state_change"
                for target in node.targets
            )
        ]

        self.assertEqual([], assignments)

    def test_callback_delegates_to_shared_close_path(self) -> None:
        """Use the same forced-close implementation for timer and startup catch-up."""
        calls = {
            ast.unparse(node.func)
            for node in ast.walk(self.callback)
            if isinstance(node, ast.Call)
        }
        self.assertIn("self._async_apply_night_purge_close", calls)

    def test_first_refresh_catches_up_missed_deadline(self) -> None:
        """Close after a restart occurring between purge deadline and daily start."""
        handler = function_named(self.tree, "async_handle_first_refresh")
        calls = {
            ast.unparse(node.func)
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
        }
        self.assertIn("self._night_purge_close_overdue", calls)
        self.assertIn("self._async_apply_night_purge_close", calls)


class CoordinatorExecutionTests(unittest.TestCase):
    """Guard coordinator execution ordering and gating rules."""

    @classmethod
    def setUpClass(cls) -> None:
        """Parse runtime modules without importing Home Assistant."""
        cls.source = COORDINATOR_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.init_tree = ast.parse(INIT_PATH.read_text(encoding="utf-8"))
        cls.switch_tree = ast.parse(SWITCH_PATH.read_text(encoding="utf-8"))
        cls.calculation_tree = ast.parse(
            CALCULATION_PATH.read_text(encoding="utf-8")
        )

    def test_restore_entities_before_first_automation_pass(self) -> None:
        """Do not consume first refresh before RestoreEntity switches are loaded."""
        setup = function_named(self.init_tree, "async_setup_entry")
        calls = [
            (ast.unparse(node.func), node.lineno)
            for node in ast.walk(setup)
            if isinstance(node, ast.Call)
        ]
        forward_line = next(
            line for name, line in calls if name.endswith("async_forward_entry_setups")
        )
        initialized_line = next(
            line
            for name, line in calls
            if name.endswith("schedule_runtime_initialization")
        )
        self.assertLess(forward_line, initialized_line)

    def test_startup_events_cannot_issue_physical_movement(self) -> None:
        """Calculate during startup but execute handlers only after stabilization."""
        update = ast.unparse(function_named(self.tree, "_async_calculate_update_data"))
        service = ast.unparse(function_named(self.tree, "async_handle_call_service"))
        self.assertIn("self._runtime_initialized", update)
        self.assertIn("if not self._runtime_initialized", service)
        self.assertIn("runtime_initializing", service)

    def test_strict_sun_requires_numeric_sensor_value(self) -> None:
        """Do not interpret unavailable irradiance as strong sunlight."""
        climate_state = next(
            node
            for node in ast.walk(self.calculation_tree)
            if isinstance(node, ast.ClassDef) and node.name == "ClimateCoverState"
        )
        body = ast.unparse(climate_state)
        self.assertIn("numeric_value_above_threshold", body)
        self.assertIn("strict_sun_value", body)

    def test_intermediate_cover_states_return_before_refresh(self) -> None:
        """Ensure ignored motor states cannot trigger manual-override processing."""
        handler = function_named(self.tree, "async_check_cover_state_change")
        ignored_if = next(
            node
            for node in handler.body
            if isinstance(node, ast.If)
            and "ignore_intermediate_states" in ast.unparse(node.test)
        )
        self.assertTrue(any(isinstance(node, ast.Return) for node in ignored_if.body))

    def test_emergency_decisions_bypass_generic_limits(self) -> None:
        """Keep rain and wind movement independent from cooldown and manual mode."""
        handler = function_named(self.tree, "movement_block_reason")
        body = ast.unparse(handler)
        self.assertIn("EMERGENCY_DECISION_CODES", body)
        self.assertIn("SCHEDULE_EXEMPT_DECISION_CODES", body)
        self.assertIn("not emergency and self.manager.is_cover_manual", body)
        self.assertIn("not emergency and (not self.manager.can_move", body)

    def test_manual_override_uses_absolute_deadline(self) -> None:
        """Prevent a shrinking relative duration from resetting at half-time."""
        manager_init = function_named(self.tree, "__init__")
        manager_source = self.source[manager_init.lineno - 1 :]
        self.assertIn("manual_control_until", manager_source)
        reset = ast.unparse(function_named(self.tree, "reset_if_needed"))
        self.assertIn("current_time >= deadline", reset)

    def test_zero_is_valid_interpolation_endpoint(self) -> None:
        """Allow the normal 0-100 mapping to start at zero."""
        interpolation = ast.unparse(function_named(self.tree, "interpolate_states"))
        self.assertIn("self.start_value is not None", interpolation)

    def test_universal_schedule_uses_universal_option(self) -> None:
        """Use start_time when no Workday entity is configured."""
        effective = ast.unparse(function_named(self.tree, "_effective_start_value"))
        self.assertIn("CONF_START_TIME", effective)
        self.assertIn("{'on', 'off'}", effective)

    def test_control_switch_uses_shared_movement_gates(self) -> None:
        """Do not reintroduce schedule or manual gates before safety decisions."""
        turn_on = ast.unparse(function_named(self.switch_tree, "async_turn_on"))
        self.assertIn("async_handle_call_service", turn_on)
        self.assertNotIn("adaptive_movement_allowed", turn_on)
        self.assertNotIn("is_cover_manual", turn_on)


if __name__ == "__main__":
    unittest.main()
