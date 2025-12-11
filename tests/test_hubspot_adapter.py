"""Tests for HubSpot adapter."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from toolkit_engine.core.models import (
    ProductDefinition,
    ProductType,
    AuthMethod,
    ConfigError,
)
from toolkit_engine.products.hubspot import (
    HubSpotAdapter,
    DiscoveryError,
    detect_entity,
    detect_action,
)


@pytest.fixture
def hubspot_product():
    """Create a test HubSpot product definition."""
    return ProductDefinition(
        product_id="hubspot",
        name="HubSpot",
        type=ProductType.CRM,
        api_base_url="https://api.hubapi.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"api_key_header": "Authorization"},
    )


@pytest.fixture
def hubspot_spec():
    """Load the HubSpot spec fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "hubspot_spec.json"
    with open(fixture_path) as f:
        return json.load(f)


def test_detect_entity_contacts():
    """Test entity detection for contacts paths."""
    assert detect_entity("/crm/v3/objects/contacts") == "contacts"
    assert detect_entity("/crm/v3/objects/contacts/{contactId}") == "contacts"
    assert detect_entity("/api/v1/contacts") == "contacts"


def test_detect_entity_companies():
    """Test entity detection for companies paths."""
    assert detect_entity("/crm/v3/objects/companies") == "organisations"
    assert detect_entity("/crm/v3/objects/companies/{companyId}") == "organisations"


def test_detect_entity_deals():
    """Test entity detection for deals paths."""
    assert detect_entity("/crm/v3/objects/deals") == "deals"
    assert detect_entity("/crm/v3/objects/deals/{dealId}") == "deals"


def test_detect_entity_unknown():
    """Test entity detection for unknown paths."""
    assert detect_entity("/api/v1/unknown") is None
    assert detect_entity("/settings") is None


def test_detect_action_list():
    """Test action detection for list operations."""
    assert detect_action("GET", "/crm/v3/objects/contacts") == "list"
    assert detect_action("get", "/api/contacts") == "list"


def test_detect_action_get():
    """Test action detection for get operations."""
    assert detect_action("GET", "/crm/v3/objects/contacts/{contactId}") == "get"
    assert detect_action("GET", "/api/contacts/{id}") == "get"


def test_detect_action_create():
    """Test action detection for create operations."""
    assert detect_action("POST", "/crm/v3/objects/contacts") == "create"
    assert detect_action("post", "/api/contacts") == "create"


def test_detect_action_update():
    """Test action detection for update operations."""
    assert detect_action("PATCH", "/crm/v3/objects/contacts/{contactId}") == "update"
    assert detect_action("PUT", "/api/contacts/{id}") == "update"


def test_detect_action_delete():
    """Test action detection for delete operations."""
    assert detect_action("DELETE", "/crm/v3/objects/contacts/{contactId}") == "delete"
    assert detect_action("delete", "/api/contacts/{id}") == "delete"


def test_detect_action_unknown():
    """Test action detection for unknown operations."""
    assert detect_action("POST", "/api/contacts/{id}") is None
    # Note: GET without ID returns "list", which is expected behavior


def test_adapter_product_id(hubspot_product):
    """Test that adapter returns correct product_id."""
    adapter = HubSpotAdapter(hubspot_product)
    assert adapter.product_id == "hubspot"


def test_discover_spec_success(hubspot_product, hubspot_spec):
    """Test successful spec discovery."""
    adapter = HubSpotAdapter(hubspot_product)

    with patch("httpx.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = hubspot_spec
        mock_get.return_value = mock_response

        spec = adapter.discover_spec()

        assert spec == hubspot_spec
        mock_get.assert_called_once()
        assert mock_get.call_args[1]["timeout"] == 10.0


def test_discover_spec_http_error(hubspot_product):
    """Test spec discovery with HTTP error."""
    adapter = HubSpotAdapter(hubspot_product)

    with patch("httpx.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        with pytest.raises(DiscoveryError) as exc_info:
            adapter.discover_spec()

        assert "HTTP 404" in str(exc_info.value)


def test_discover_spec_request_error(hubspot_product):
    """Test spec discovery with request error."""
    adapter = HubSpotAdapter(hubspot_product)

    with patch("httpx.get") as mock_get:
        mock_get.side_effect = httpx.RequestError("Connection failed", request=Mock())

        with pytest.raises(DiscoveryError) as exc_info:
            adapter.discover_spec()

        assert "Failed to connect" in str(exc_info.value)


def test_extract_capabilities_basic(hubspot_product, hubspot_spec):
    """Test capability extraction from spec."""
    adapter = HubSpotAdapter(hubspot_product)
    capabilities = adapter.extract_capabilities(hubspot_spec)

    # Should have capabilities for contacts, companies, and deals
    entities = {cap.entity_name for cap in capabilities}
    assert "contacts" in entities
    assert "organisations" in entities
    assert "deals" in entities

    # Check contacts capabilities
    contact_caps = [cap for cap in capabilities if cap.entity_name == "contacts"]
    actions = {cap.action for cap in contact_caps}

    assert "list" in actions
    assert "get" in actions
    assert "create" in actions
    assert "update" in actions
    assert "delete" in actions

    # Verify a specific capability
    list_cap = next(cap for cap in contact_caps if cap.action == "list")
    assert list_cap.http_method == "GET"
    assert list_cap.path == "/crm/v3/objects/contacts"
    assert list_cap.product_id == "hubspot"


def test_extract_capabilities_company_operations(hubspot_product, hubspot_spec):
    """Test that company/organisation operations are extracted."""
    adapter = HubSpotAdapter(hubspot_product)
    capabilities = adapter.extract_capabilities(hubspot_spec)

    org_caps = [cap for cap in capabilities if cap.entity_name == "organisations"]
    assert len(org_caps) > 0

    # Should have list and create at minimum
    actions = {cap.action for cap in org_caps}
    assert "list" in actions
    assert "create" in actions
    assert "get" in actions
    assert "update" in actions


def test_extract_capabilities_deal_operations(hubspot_product, hubspot_spec):
    """Test that deal operations are extracted."""
    adapter = HubSpotAdapter(hubspot_product)
    capabilities = adapter.extract_capabilities(hubspot_spec)

    deal_caps = [cap for cap in capabilities if cap.entity_name == "deals"]
    assert len(deal_caps) > 0

    actions = {cap.action for cap in deal_caps}
    assert "list" in actions
    assert "create" in actions


def test_extract_capabilities_skips_unknown_entities(hubspot_product, hubspot_spec):
    """Test that unknown entities are skipped."""
    adapter = HubSpotAdapter(hubspot_product)
    capabilities = adapter.extract_capabilities(hubspot_spec)

    # The internal endpoint should be skipped
    entities = {cap.entity_name for cap in capabilities}
    assert "internal" not in entities
    assert "something" not in entities


def test_build_auth_headers_success(hubspot_product):
    """Test building auth headers with valid credentials."""
    adapter = HubSpotAdapter(hubspot_product)
    credentials = {"access_token": "test-token-123"}

    headers = adapter.build_auth_headers(credentials)

    assert headers == {"Authorization": "Bearer test-token-123"}


def test_build_auth_headers_missing_token(hubspot_product):
    """Test building auth headers without access token."""
    adapter = HubSpotAdapter(hubspot_product)
    credentials = {}

    with pytest.raises(ConfigError) as exc_info:
        adapter.build_auth_headers(credentials)

    assert "access_token" in str(exc_info.value)


def test_extract_capabilities_empty_spec(hubspot_product):
    """Test capability extraction with empty spec."""
    adapter = HubSpotAdapter(hubspot_product)
    empty_spec = {"paths": {}}

    capabilities = adapter.extract_capabilities(empty_spec)

    assert capabilities == []


def test_extract_capabilities_no_paths(hubspot_product):
    """Test capability extraction with missing paths."""
    adapter = HubSpotAdapter(hubspot_product)
    spec = {"openapi": "3.0.0"}

    capabilities = adapter.extract_capabilities(spec)

    assert capabilities == []
