"""The sole Domain Pack registration point; core code selects by identifier."""
from .base import DomainPack
from .identity import PACK as identity
from .smart_city import PACK as smart_city
from .fintech import PACK as fintech
from .tourism import PACK as tourism
from .industry import PACK as industry
from .climate import PACK as climate
from .open_innovation import PACK as open_innovation

_PACKS = {pack.metadata.id: pack for pack in (identity, smart_city, fintech, tourism, industry, climate, open_innovation)}


def get_domain(domain_id: str) -> DomainPack:
    try:
        return _PACKS[domain_id]
    except KeyError:
        raise ValueError(f"Unknown GuardianMesh domain: {domain_id}") from None


def list_domains() -> list[DomainPack]:
    return list(_PACKS.values())
