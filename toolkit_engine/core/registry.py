"""Product registry for managing registered products."""

import logging
from typing import Any

from .models import ProductDefinition, ProductType, AuthMethod, ProductNotFoundError

logger = logging.getLogger(__name__)

# In-memory storage for registered products
_PRODUCTS: dict[str, ProductDefinition] = {}


def register_product(
    product_id: str,
    product_type: ProductType,
    name: str,
    api_base_url: str,
    auth_method: AuthMethod,
    auth_metadata: dict | None = None,
) -> ProductDefinition:
    """
    Register a product in the registry.

    Args:
        product_id: Internal key for the product (e.g., "hubspot")
        product_type: Type of product (CRM or ACCOUNTING)
        name: Human-readable name
        api_base_url: Base URL for the product's API
        auth_method: Authentication method
        auth_metadata: Additional authentication details

    Returns:
        The registered ProductDefinition

    Note:
        If product_id already exists, it will be overwritten.
    """
    if product_id in _PRODUCTS:
        logger.warning(f"Product '{product_id}' already exists. Overwriting.")

    if auth_metadata is None:
        auth_metadata = {}

    product = ProductDefinition(
        product_id=product_id,
        name=name,
        type=product_type,
        api_base_url=api_base_url,
        auth_method=auth_method,
        auth_metadata=auth_metadata,
    )

    _PRODUCTS[product_id] = product
    logger.info(f"Registered product: {product_id} ({name})")

    return product


def get_product(product_id: str) -> ProductDefinition:
    """
    Retrieve a product from the registry.

    Args:
        product_id: Internal key for the product

    Returns:
        The ProductDefinition for the given product_id

    Raises:
        ProductNotFoundError: If the product is not in the registry
    """
    if product_id not in _PRODUCTS:
        raise ProductNotFoundError(f"Product '{product_id}' not found in registry")

    return _PRODUCTS[product_id]


def list_products() -> list[ProductDefinition]:
    """
    List all registered products.

    Returns:
        List of ProductDefinition objects sorted by product_id
    """
    return sorted(_PRODUCTS.values(), key=lambda p: p.product_id)


def reset_registry() -> None:
    """
    Clear all products from the registry.

    This is primarily intended for testing.
    """
    global _PRODUCTS
    _PRODUCTS = {}
    logger.debug("Registry reset")
