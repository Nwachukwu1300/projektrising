"""Discovery functionality for product API capabilities."""

import logging
from typing import Any

from toolkit_engine.core.models import (
    ProductDefinition,
    Capability,
    ProductNotFoundError,
    ConfigError,
)
from toolkit_engine.core.registry import get_product
from toolkit_engine.core.config_store import save_json
from toolkit_engine.products.base import ProductAdapter
from toolkit_engine.products.hubspot import HubSpotAdapter
from toolkit_engine.products.pipedrive import PipedriveAdapter

logger = logging.getLogger(__name__)


class AdapterNotFoundError(Exception):
    """Raised when no adapter is available for a product."""
    pass


def get_adapter_for_product(product: ProductDefinition) -> ProductAdapter:
    """
    Get the appropriate adapter for a product.

    Args:
        product: Product definition

    Returns:
        ProductAdapter instance for the product

    Raises:
        AdapterNotFoundError: If no adapter exists for the product type
    """
    product_id = product.product_id.lower()

    if product_id == "hubspot":
        return HubSpotAdapter(product)
    elif product_id == "pipedrive":
        return PipedriveAdapter(product)
    # Add more adapters here as they are implemented
    # elif product_id == "salesforce":
    #     return SalesforceAdapter(product)
    # elif product_id == "xero":
    #     return XeroAdapter(product)
    else:
        raise AdapterNotFoundError(
            f"No adapter available for product '{product.product_id}'. "
            f"Supported products: hubspot, pipedrive"
        )


def discover_capabilities(
    product_id: str,
    use_cached: bool = True
) -> list[Capability]:
    """
    Discover API capabilities for a product.

    This is the main entry point for capability discovery. It:
    1. Loads the product definition
    2. Selects the appropriate adapter
    3. Discovers the API specification
    4. Extracts capabilities from the spec
    5. Persists the spec and capabilities to disk

    Args:
        product_id: Internal product identifier
        use_cached: Whether to use cached spec (not implemented in Stage 2)

    Returns:
        List of discovered Capability objects

    Raises:
        ProductNotFoundError: If the product is not registered
        AdapterNotFoundError: If no adapter exists for the product
        DiscoveryError: If spec discovery fails
    """
    logger.info(f"Starting capability discovery for product '{product_id}'")

    # Step 1: Fetch product definition
    try:
        product = get_product(product_id)
    except ProductNotFoundError:
        logger.error(f"Product '{product_id}' not found in registry")
        raise

    logger.info(
        f"Found product: {product.name} ({product.type.value}, "
        f"{product.auth_method.value})"
    )

    # Step 2: Get appropriate adapter
    try:
        adapter = get_adapter_for_product(product)
    except AdapterNotFoundError:
        logger.error(f"No adapter available for '{product_id}'")
        raise

    logger.info(f"Using adapter: {adapter.__class__.__name__}")

    # Step 3: Discover API specification
    # TODO: In future, check use_cached and load from disk if available
    spec = adapter.discover_spec()

    # Step 4: Save raw spec to disk
    spec_path = save_json(product_id, "raw_spec", spec)
    logger.info(f"Saved raw spec to {spec_path}")

    # Step 5: Extract capabilities from spec
    capabilities = adapter.extract_capabilities(spec)
    logger.info(f"Extracted {len(capabilities)} capabilities")

    # Step 6: Serialize and save capabilities
    capabilities_data = {
        "product_id": product_id,
        "total_capabilities": len(capabilities),
        "capabilities": [
            {
                "entity_name": cap.entity_name,
                "action": cap.action,
                "http_method": cap.http_method,
                "path": cap.path,
                "score": cap.score,
            }
            for cap in capabilities
        ],
    }

    capabilities_path = save_json(product_id, "capabilities", capabilities_data)
    logger.info(f"Saved capabilities to {capabilities_path}")

    return capabilities
