"""Nokia QoD adapter using the documented v1 RapidAPI transport via QoDConfig."""
from .camara import CamaraNetworkProvider


class NokiaNetworkProvider(CamaraNetworkProvider):
    name = "Nokia Network as Code sandbox adapter boundary"
    requested_mode = "nokia"
