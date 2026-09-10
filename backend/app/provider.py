"""Compatibility imports; the capability catalog is the source of truth."""
from .capabilities import list_capabilities
from .providers import NetworkProvider, SimulatedNetworkProvider, select_provider

ENDPOINTS = {item.id: item.endpoint for item in list_capabilities()}
__all__ = ["NetworkProvider", "SimulatedNetworkProvider", "select_provider", "ENDPOINTS"]
