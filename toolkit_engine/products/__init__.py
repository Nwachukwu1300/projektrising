"""Product adapters for different integration platforms."""

from .base import ProductAdapter
from .hubspot import HubSpotAdapter

__all__ = ["ProductAdapter", "HubSpotAdapter"]
