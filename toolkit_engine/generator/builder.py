"""
Builder module for generating CRM client integrations.

This module provides the generate_integration function that combines
product definitions, adapters, and mappings into a working CRM client.
"""

from typing import Any

from ..core import (
    get_product,
    load_product_definition,
    get_adapter_for_product,
    get_base_dir,
    ProductNotFoundError,
    ConfigError,
)
from .crm_client import ToolkitCRMClient


def generate_integration(product_id: str, credentials: dict[str, Any]) -> ToolkitCRMClient:
    """
    Generate a working CRM client from product definition and mapping.

    This function ties together all stages:
    - Stage 1: Product definition (registry/config)
    - Stage 2: Product adapter
    - Stage 3: Endpoint mapping
    - Stage 4: Client generation

    Args:
        product_id: Product identifier (e.g., 'hubspot')
        credentials: Authentication credentials (e.g., {"access_token": "..."})

    Returns:
        Configured ToolkitCRMClient ready to use

    Raises:
        ProductNotFoundError: If product is not registered
        ConfigError: If mapping file is missing
        ValueError: If adapter cannot be found

    Example:
        >>> client = generate_integration('hubspot', {'access_token': 'token123'})
        >>> contacts = client.list_contacts()
        >>> client.close()
    """
    # Step 1: Load product definition
    try:
        # First try to get from in-memory registry
        product_def = get_product(product_id)
    except ProductNotFoundError:
        # Fall back to loading from disk
        try:
            product_def = load_product_definition(product_id)
        except ConfigError as e:
            raise ProductNotFoundError(
                f"Product '{product_id}' not found. "
                f"Register it first with 'toolkit-engine register'."
            ) from e

    # Step 2: Get product adapter
    adapter = get_adapter_for_product(product_def)

    # Step 3: Load mapping from Stage 3
    base_dir = get_base_dir()
    mapping_file = base_dir / f"{product_id}_mapping.json"

    if not mapping_file.exists():
        raise ConfigError(
            f"No mapping found for '{product_id}'. "
            f"Run 'toolkit-engine select --id {product_id}' first."
        )

    import json
    with open(mapping_file) as f:
        mapping = json.load(f)

    # Step 4: Create and return client
    return ToolkitCRMClient(
        product_def=product_def,
        mapping=mapping,
        adapter=adapter,
        credentials=credentials,
    )
