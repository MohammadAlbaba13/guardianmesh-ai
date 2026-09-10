"""Compatibility facade for the original three Smart City scenario identifiers."""
from .domains.base import Scenario
from .domains.smart_city import SCENARIOS, PACK, scenario_telemetry


def scenario_catalog() -> list[dict]:
    return PACK.catalog()


__all__ = ["Scenario", "SCENARIOS", "scenario_catalog", "scenario_telemetry"]
