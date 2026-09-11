"""The installed demo always has a truthful offline fallback."""
import os
from .base import NetworkProvider, CapabilityResult, ProviderUnavailable
from .simulated import SimulatedNetworkProvider
from .camara import CamaraNetworkProvider
from .nokia import NokiaNetworkProvider


def select_provider(execution_mode=None, allow_fallback=False) -> NetworkProvider:
    mode = execution_mode or os.getenv("GUARDIANMESH_NETWORK_MODE", "SIMULATION").upper()
    if mode not in ("SIMULATION", "LIVE", "AUTO"):
        raise ValueError("GUARDIANMESH_NETWORK_MODE must be SIMULATION, LIVE or AUTO")
    if mode != "SIMULATION":
        from .service import NetworkActionService
        return NetworkActionService(mode, allow_fallback)
    requested = os.getenv("GUARDIANMESH_NETWORK_PROVIDER", "simulated").strip().lower()
    if requested == "simulated":
        return SimulatedNetworkProvider()
    if requested in ("camara", "nokia"):
        return SimulatedNetworkProvider(requested_mode=requested,
            notice=f"{requested.upper()} requested; authorized operator transport and device bindings are not installed. Active provider is SIMULATED; no carrier request is sent.")
    return SimulatedNetworkProvider(requested_mode=requested,
        notice="Unknown network provider requested. Active provider is SIMULATED; no external connection is attempted.")


__all__ = ["NetworkProvider", "CapabilityResult", "ProviderUnavailable", "SimulatedNetworkProvider",
           "CamaraNetworkProvider", "NokiaNetworkProvider", "select_provider"]
