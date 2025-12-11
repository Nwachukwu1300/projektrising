"""Base class for product adapters."""

from abc import ABC, abstractmethod
from typing import Any

from toolkit_engine.core.models import ProductDefinition, Capability


class ProductAdapter(ABC):
    """
    Abstract base class for product-specific integration adapters.

    Each product (e.g., HubSpot, Salesforce, Xero) should have its own
    adapter that implements this interface.
    """

    def __init__(self, product_def: ProductDefinition):
        """
        Initialize the adapter with a product definition.

        Args:
            product_def: The product definition containing API details
        """
        self.product_def = product_def

    @property
    @abstractmethod
    def product_id(self) -> str:
        """
        Return the internal product identifier.

        Returns:
            Product ID string (e.g., 'hubspot', 'salesforce')
        """
        pass

    @abstractmethod
    def discover_spec(self) -> dict:
        """
        Discover and return the API specification for this product.

        This could be an OpenAPI spec, a custom schema, or any structured
        representation of the product's API.

        Returns:
            API specification as a dictionary

        Raises:
            DiscoveryError: If spec discovery fails
        """
        pass

    @abstractmethod
    def extract_capabilities(self, spec: dict) -> list[Capability]:
        """
        Extract capabilities from the API specification.

        Analyzes the spec and creates Capability objects for endpoints
        that are useful for the toolkit.

        Args:
            spec: The API specification dictionary

        Returns:
            List of Capability objects representing useful endpoints
        """
        pass

    @abstractmethod
    def build_auth_headers(self, credentials: dict) -> dict:
        """
        Build authentication headers for API requests.

        Args:
            credentials: Dictionary containing authentication credentials
                        (structure varies by product)

        Returns:
            Dictionary of HTTP headers for authentication

        Raises:
            ConfigError: If credentials are invalid or incomplete
        """
        pass
