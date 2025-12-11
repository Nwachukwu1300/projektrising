"""Core components for the Toolkit Integration Engine."""

from .models import (
    ProductType,
    AuthMethod,
    ProductDefinition,
    Capability,
    ProductNotFoundError,
    ConfigError,
)
from .registry import register_product, get_product, list_products, reset_registry
from .config_store import (
    get_base_dir,
    product_config_path,
    save_json,
    load_json,
    save_product_definition,
    load_product_definition,
)
from .discovery import (
    discover_capabilities,
    get_adapter_for_product,
    AdapterNotFoundError,
)

__all__ = [
    "ProductType",
    "AuthMethod",
    "ProductDefinition",
    "Capability",
    "ProductNotFoundError",
    "ConfigError",
    "register_product",
    "get_product",
    "list_products",
    "reset_registry",
    "get_base_dir",
    "product_config_path",
    "save_json",
    "load_json",
    "save_product_definition",
    "load_product_definition",
    "discover_capabilities",
    "get_adapter_for_product",
    "AdapterNotFoundError",
]
