"""
Stage 4: Client Generation

This module provides functionality for generating working CRM clients
from product definitions and endpoint mappings.
"""

from .crm_client import ToolkitCRMClient, APIError
from .builder import generate_integration

__all__ = [
    "ToolkitCRMClient",
    "APIError",
    "generate_integration",
]
