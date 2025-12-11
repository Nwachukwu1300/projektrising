"""HubSpot CRM adapter implementation."""

import logging
from typing import Any

import httpx

from toolkit_engine.core.models import Capability, ConfigError
from .base import ProductAdapter

logger = logging.getLogger(__name__)

# HubSpot OpenAPI spec URL for CRM objects
# Using the direct OpenAPI spec endpoint for CRM v3
SPEC_URL = "https://api.hubspot.com/api-catalog-public/v1/apis/crm/v3"


class DiscoveryError(Exception):
    """Raised when API specification discovery fails."""
    pass


def detect_entity(path: str) -> str | None:
    """
    Detect the entity type from an API path.

    Args:
        path: API endpoint path

    Returns:
        Entity name or None if no entity detected
    """
    path_lower = path.lower()

    if "contacts" in path_lower:
        return "contacts"
    elif "companies" in path_lower:
        return "organisations"
    elif "deals" in path_lower:
        return "deals"
    elif "tickets" in path_lower:
        return "tickets"
    elif "products" in path_lower:
        return "products"
    elif "line_items" in path_lower or "lineitems" in path_lower:
        return "line_items"
    elif "quotes" in path_lower:
        return "quotes"

    return None


def detect_action(http_method: str, path: str) -> str | None:
    """
    Detect the action type from HTTP method and path.

    Args:
        http_method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        path: API endpoint path

    Returns:
        Action name or None if no action detected
    """
    method = http_method.upper()
    has_id = "{id}" in path.lower() or "{contactid}" in path.lower() or \
             "{companyid}" in path.lower() or "{dealid}" in path.lower() or \
             "{ticketid}" in path.lower() or "{productid}" in path.lower()

    if method == "GET":
        if has_id:
            return "get"
        else:
            return "list"
    elif method == "POST":
        if not has_id:
            return "create"
    elif method in ["PATCH", "PUT"]:
        if has_id:
            return "update"
    elif method == "DELETE":
        if has_id:
            return "delete"

    return None


class HubSpotAdapter(ProductAdapter):
    """
    Adapter for HubSpot CRM integration.

    Implements discovery and capability extraction for HubSpot's CRM API.
    """

    @property
    def product_id(self) -> str:
        """Return the HubSpot product identifier."""
        return "hubspot"

    def discover_spec(self) -> dict:
        """
        Discover the HubSpot API specification.

        Fetches the OpenAPI spec from HubSpot's public API catalog.

        Returns:
            API specification as a dictionary

        Raises:
            DiscoveryError: If spec retrieval fails
        """
        try:
            logger.info(f"Discovering HubSpot API spec from {SPEC_URL}")
            response = httpx.get(SPEC_URL, timeout=10.0)
            response.raise_for_status()

            spec = response.json()
            logger.info("Successfully retrieved HubSpot API spec")
            return spec

        except httpx.HTTPStatusError as e:
            raise DiscoveryError(
                f"Failed to retrieve HubSpot spec: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise DiscoveryError(f"Failed to connect to HubSpot API: {e}")
        except Exception as e:
            raise DiscoveryError(f"Unexpected error during spec discovery: {e}")

    def extract_capabilities(self, spec: dict) -> list[Capability]:
        """
        Extract capabilities from HubSpot API specification.

        Analyzes the OpenAPI spec and creates Capability objects for
        useful CRM endpoints (contacts, companies, deals, etc.).

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            List of Capability objects
        """
        capabilities = []

        # Handle different spec formats
        paths = spec.get("paths", {})
        if not paths and "openapi" in spec:
            # Try alternate structure
            paths = spec.get("paths", {})

        logger.debug(f"Found {len(paths)} paths in spec")

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue

            # Detect entity from path
            entity = detect_entity(path)
            if not entity:
                continue

            # Process each HTTP method
            for method, details in methods.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    action = detect_action(method, path)
                    if not action:
                        continue

                    capability = Capability(
                        product_id=self.product_def.product_id,
                        entity_name=entity,
                        action=action,
                        http_method=method.upper(),
                        path=path,
                        request_schema=None,  # Will be populated in later stages
                        response_schema=None,  # Will be populated in later stages
                        score=None,  # Will be calculated in Stage 3
                    )

                    capabilities.append(capability)
                    logger.debug(
                        f"Extracted capability: {entity}.{action} {method.upper()} {path}"
                    )

        logger.info(f"Extracted {len(capabilities)} capabilities from spec")
        return capabilities

    def build_auth_headers(self, credentials: dict) -> dict:
        """
        Build authentication headers for HubSpot API.

        HubSpot uses Bearer token authentication with either:
        - Private app access tokens
        - OAuth 2.0 access tokens

        Args:
            credentials: Dictionary with 'access_token' key

        Returns:
            Dictionary of authentication headers

        Raises:
            ConfigError: If access_token is missing
        """
        if "access_token" not in credentials:
            raise ConfigError(
                "HubSpot credentials must include 'access_token' field"
            )

        token = credentials["access_token"]
        return {"Authorization": f"Bearer {token}"}
