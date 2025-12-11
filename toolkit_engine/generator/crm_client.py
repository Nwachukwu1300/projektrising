"""
CRM Client Implementation

Provides a unified client for interacting with CRM APIs using
the mappings generated in Stage 3.
"""

import time
import httpx
from typing import Any

from ..core.models import ProductDefinition
from ..products.base import ProductAdapter


class APIError(Exception):
    """Raised when API requests fail after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ToolkitCRMClient:
    """
    Universal CRM client that uses product mappings to call APIs.

    Features:
    - Dynamic endpoint routing based on mapping config
    - Automatic authentication via ProductAdapter
    - Built-in retries for transient failures
    - Path parameter substitution
    """

    def __init__(
        self,
        product_def: ProductDefinition,
        mapping: dict[str, dict[str, dict[str, str]]],
        adapter: ProductAdapter,
        credentials: dict[str, Any],
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
    ):
        """
        Initialize the CRM client.

        Args:
            product_def: Product definition with API base URL
            mapping: Endpoint mapping from Stage 3 select command
            adapter: Product adapter for auth and spec handling
            credentials: Auth credentials (e.g., {"access_token": "..."})
            http_client: Optional httpx client (created if None)
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.product_def = product_def
        self.mapping = mapping
        self.adapter = adapter
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Track if we own the HTTP client (for cleanup)
        self._owns_client = http_client is None

        if http_client is None:
            self.http_client = httpx.Client(timeout=timeout_seconds)
        else:
            self.http_client = http_client

    def close(self) -> None:
        """Close the HTTP client if we created it."""
        if self._owns_client and self.http_client:
            self.http_client.close()

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False

    def _build_url(self, path: str) -> str:
        """
        Build full URL from base URL and path.

        Args:
            path: API path (e.g., "/crm/v3/objects/contacts")

        Returns:
            Full URL
        """
        base_url = self.product_def.api_base_url.rstrip("/")
        path = path.lstrip("/")
        return f"{base_url}/{path}"

    def _substitute_path_params(self, path: str, **params) -> str:
        """
        Substitute path parameters like {contactId} with actual values.

        Args:
            path: Path template (e.g., "/contacts/{contactId}")
            **params: Parameter values

        Returns:
            Path with substituted values
        """
        result = path
        for key, value in params.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an authenticated HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            params: Query parameters
            json_body: JSON request body
            path_params: Path parameter substitutions

        Returns:
            Response JSON as dict

        Raises:
            APIError: On non-2xx response after retries
        """
        # Substitute path parameters
        if path_params:
            path = self._substitute_path_params(path, **path_params)

        # Build full URL
        url = self._build_url(path)

        # Get auth headers from adapter
        headers = self.adapter.build_auth_headers(self.credentials)
        headers["Content-Type"] = "application/json"

        # Some products (like Pipedrive) use query params for auth instead of headers
        # If credentials contain 'api_token', add it to query params
        if params is None:
            params = {}
        if "api_token" in self.credentials:
            params["api_token"] = self.credentials["api_token"]

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.http_client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )

                # Success - return response
                if 200 <= response.status_code < 300:
                    return response.json() if response.content else {}

                # 4xx errors - don't retry, fail immediately
                if 400 <= response.status_code < 500:
                    raise APIError(
                        f"API request failed: {response.status_code} {response.text}",
                        status_code=response.status_code
                    )

                # 5xx errors - retry
                last_error = APIError(
                    f"Server error: {response.status_code} {response.text}",
                    status_code=response.status_code
                )

            except httpx.RequestError as e:
                # Network errors - retry
                last_error = APIError(f"Request failed: {str(e)}")

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)

        # All retries exhausted
        raise last_error or APIError("Request failed after retries")

    # ===== CONTACTS METHODS =====

    def list_contacts(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        List contacts from the CRM.

        Args:
            filters: Optional query parameters for filtering

        Returns:
            List of contact dicts
        """
        endpoint = self.mapping.get("contacts", {}).get("list")
        if not endpoint:
            raise ValueError("No 'list' endpoint configured for contacts")

        response = self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            params=filters,
        )

        # Handle different response formats
        if isinstance(response, list):
            return response
        elif "results" in response:
            return response["results"]
        elif "data" in response:
            return response["data"]
        else:
            # Assume top-level dict is a single contact
            return [response] if response else []

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        """
        Get a single contact by ID.

        Args:
            contact_id: Contact identifier

        Returns:
            Contact dict
        """
        endpoint = self.mapping.get("contacts", {}).get("get")
        if not endpoint:
            raise ValueError("No 'get' endpoint configured for contacts")

        return self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            path_params={"contactId": contact_id, "id": contact_id},
        )

    def create_contact(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new contact.

        Args:
            payload: Contact data

        Returns:
            Created contact dict
        """
        endpoint = self.mapping.get("contacts", {}).get("create")
        if not endpoint:
            raise ValueError("No 'create' endpoint configured for contacts")

        return self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            json_body=payload,
        )

    def update_contact(self, contact_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing contact.

        Args:
            contact_id: Contact identifier
            payload: Updated contact data

        Returns:
            Updated contact dict
        """
        endpoint = self.mapping.get("contacts", {}).get("update")
        if not endpoint:
            raise ValueError("No 'update' endpoint configured for contacts")

        return self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            path_params={"contactId": contact_id, "id": contact_id},
            json_body=payload,
        )

    # ===== ORGANISATIONS METHODS =====

    def list_organisations(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        List organisations from the CRM.

        Args:
            filters: Optional query parameters for filtering

        Returns:
            List of organisation dicts
        """
        endpoint = self.mapping.get("organisations", {}).get("list")
        if not endpoint:
            raise ValueError("No 'list' endpoint configured for organisations")

        response = self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            params=filters,
        )

        # Handle different response formats
        if isinstance(response, list):
            return response
        elif "results" in response:
            return response["results"]
        elif "data" in response:
            return response["data"]
        else:
            return [response] if response else []

    def get_organisation(self, org_id: str) -> dict[str, Any]:
        """
        Get a single organisation by ID.

        Args:
            org_id: Organisation identifier

        Returns:
            Organisation dict
        """
        endpoint = self.mapping.get("organisations", {}).get("get")
        if not endpoint:
            raise ValueError("No 'get' endpoint configured for organisations")

        return self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            path_params={"companyId": org_id, "organisationId": org_id, "id": org_id},
        )

    def create_organisation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new organisation.

        Args:
            payload: Organisation data

        Returns:
            Created organisation dict
        """
        endpoint = self.mapping.get("organisations", {}).get("create")
        if not endpoint:
            raise ValueError("No 'create' endpoint configured for organisations")

        return self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            json_body=payload,
        )

    def update_organisation(self, org_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing organisation.

        Args:
            org_id: Organisation identifier
            payload: Updated organisation data

        Returns:
            Updated organisation dict
        """
        endpoint = self.mapping.get("organisations", {}).get("update")
        if not endpoint:
            raise ValueError("No 'update' endpoint configured for organisations")

        return self._request(
            method=endpoint["http_method"],
            path=endpoint["path"],
            path_params={"companyId": org_id, "organisationId": org_id, "id": org_id},
            json_body=payload,
        )
