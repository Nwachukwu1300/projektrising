"""Core data models for the Toolkit Integration Engine."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ProductType(Enum):
    """Type of product being integrated."""
    CRM = "crm"
    ACCOUNTING = "accounting"


class AuthMethod(Enum):
    """Authentication method for API access."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"


@dataclass
class ProductDefinition:
    """Definition of a product to be integrated."""
    product_id: str
    name: str
    type: ProductType
    api_base_url: str
    auth_method: AuthMethod
    auth_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert ProductDefinition to a dictionary."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "type": self.type.value,
            "api_base_url": self.api_base_url,
            "auth_method": self.auth_method.value,
            "auth_metadata": self.auth_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductDefinition":
        """Create ProductDefinition from a dictionary."""
        return cls(
            product_id=data["product_id"],
            name=data["name"],
            type=ProductType(data["type"]),
            api_base_url=data["api_base_url"],
            auth_method=AuthMethod(data["auth_method"]),
            auth_metadata=data.get("auth_metadata", {}),
        )


@dataclass
class Capability:
    """
    Represents a capability (endpoint) of a product.

    This will be used in later stages for discovery and ranking.
    """
    product_id: str
    entity_name: str
    action: str
    http_method: str
    path: str
    request_schema: dict | None = None
    response_schema: dict | None = None
    score: float | None = None


class ProductNotFoundError(Exception):
    """Raised when a product is not found in the registry."""
    pass


class ConfigError(Exception):
    """Raised when there is an error loading or saving configuration."""
    pass
