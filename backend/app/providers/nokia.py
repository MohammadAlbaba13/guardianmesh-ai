"""Nokia integration boundary: no fabricated production API routes."""
from .camara import CamaraNetworkProvider


class NokiaNetworkProvider(CamaraNetworkProvider):
    name = "Nokia Network as Code sandbox adapter boundary"
    requested_mode = "nokia"
