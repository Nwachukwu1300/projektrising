"""Pipedrive CRM adapter implementation."""

import logging
from typing import Any

import httpx

from toolkit_engine.core.models import Capability, ConfigError
from .base import ProductAdapter

logger = logging.getLogger(__name__)

# Pipedrive API documentation
SPEC_URL = "https://developers.pipedrive.com/docs/api/v1/openapi.json"


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

    # Pipedrive uses "persons" for contacts
    if "/persons" in path_lower:
        return "contacts"
    elif "/organizations" in path_lower:
        return "organisations"
    elif "/deals" in path_lower:
        return "deals"
    elif "/activities" in path_lower:
        return "activities"
    elif "/products" in path_lower:
        return "products"

    return None


def detect_action(http_method: str, path: str) -> str | None:
    """
    Detect the action type from HTTP method and path.

    Args:
        http_method: HTTP method (GET, POST, PUT, DELETE)
        path: API endpoint path

    Returns:
        Action name or None if no action detected
    """
    method = http_method.upper()
    # Pipedrive uses {id} for path parameters
    has_id = "{id}" in path.lower()

    if method == "GET":
        if has_id:
            return "get"
        else:
            return "list"
    elif method == "POST":
        if not has_id:
            return "create"
    elif method == "PUT":
        if has_id:
            return "update"
    elif method == "DELETE":
        if has_id:
            return "delete"

    return None


class PipedriveAdapter(ProductAdapter):
    """
    Adapter for Pipedrive CRM integration.

    Implements discovery and capability extraction for Pipedrive's API.
    """

    @property
    def product_id(self) -> str:
        """Return the Pipedrive product identifier."""
        return "pipedrive"

    def discover_spec(self) -> dict:
        """
        Discover the Pipedrive API specification.

        Fetches the OpenAPI spec from Pipedrive's developer documentation.

        Returns:
            API specification as a dictionary

        Raises:
            DiscoveryError: If spec retrieval fails
        """
        try:
            logger.info(f"Discovering Pipedrive API spec from {SPEC_URL}")
            response = httpx.get(SPEC_URL, timeout=15.0)
            response.raise_for_status()

            spec = response.json()
            logger.info("Successfully retrieved Pipedrive API spec")
            return spec

        except httpx.HTTPStatusError as e:
            raise DiscoveryError(
                f"Failed to retrieve Pipedrive spec: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise DiscoveryError(f"Failed to connect to Pipedrive API: {e}")
        except Exception as e:
            raise DiscoveryError(f"Unexpected error during spec discovery: {e}")

    def extract_capabilities(self, spec: dict) -> list[Capability]:
        """
        Extract capabilities from Pipedrive API specification.

        Analyzes the OpenAPI spec and creates Capability objects for
        useful CRM endpoints (persons, organizations, deals, etc.).

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            List of Capability objects
        """
        capabilities = []

        # Get paths from spec
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
                if method.lower() in ["get", "post", "put", "delete"]:
                    action = detect_action(method, path)
                    if not action:
                        continue

                    capability = Capability(
                        product_id=self.product_def.product_id,
                        entity_name=entity,
                        action=action,
                        http_method=method.upper(),
                        path=path,
                        request_schema=None,
                        response_schema=None,
                        score=None,
                    )

                    capabilities.append(capability)
                    logger.debug(
                        f"Extracted capability: {entity}.{action} {method.upper()} {path}"
                    )

        logger.info(f"Extracted {len(capabilities)} capabilities from spec")
        return capabilities

    def build_auth_headers(self, credentials: dict) -> dict:
        """
        Build authentication headers for Pipedrive API.

        Pipedrive uses API token authentication via query parameters,
        NOT headers. This method just validates credentials exist.
        The actual token is added to query params by the CRM client.

        Args:
            credentials: Dictionary with 'api_token' key

        Returns:
            Empty dict (Pipedrive doesn't use auth headers)

        Raises:
            ConfigError: If api_token is missing
        """
        if "api_token" not in credentials:
            raise ConfigError(
                "Pipedrive credentials must include 'api_token' field"
            )

        # Pipedrive uses query params for auth, not headers
        # Return empty dict - the token will be added to query params
        return {}
