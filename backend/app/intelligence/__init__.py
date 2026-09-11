"""Offline first: optional local generation never blocks a deterministic demo."""
import os
from .base import Reasoner
from .deterministic import DeterministicReasoner
from .llm import LocalLLMReasoner


def choose_reasoner(requested=None) -> Reasoner:
    requested = requested or os.getenv("GUARDIANMESH_REASONER", "deterministic").strip().lower()
    if requested == "deterministic":
        return DeterministicReasoner()
    if requested == "local_llm":
        try:
            return LocalLLMReasoner(os.getenv("GUARDIANMESH_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                os.getenv("GUARDIANMESH_OLLAMA_MODEL", ""), float(os.getenv("GUARDIANMESH_OLLAMA_TIMEOUT", "4")),
                cpu_only=os.getenv("GUARDIANMESH_OLLAMA_CPU_ONLY", "false").lower() == "true")
        except ValueError:
            return DeterministicReasoner(requested_mode=requested,
                fallback_reason="Local LLM configuration is missing or invalid; deterministic reasoning applied.")
    return DeterministicReasoner(requested_mode=requested,
        fallback_reason="Unknown reasoner requested; deterministic reasoning applied.")


__all__ = ["Reasoner", "DeterministicReasoner", "LocalLLMReasoner", "choose_reasoner"]
