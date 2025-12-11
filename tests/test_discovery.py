"""Tests for the discovery module."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from toolkit_engine.core.models import (
    ProductDefinition,
    ProductType,
    AuthMethod,
    Capability,
    ProductNotFoundError,
)
from toolkit_engine.core.registry import register_product, reset_registry
from toolkit_engine.core.discovery import (
    get_adapter_for_product,
    discover_capabilities,
    AdapterNotFoundError,
)
from toolkit_engine.products.hubspot import HubSpotAdapter


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the registry before each test."""
    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Set up a temporary home directory for config storage."""
    monkeypatch.setenv("TOOLKIT_ENGINE_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def hubspot_product():
    """Create and register a test HubSpot product."""
    product = register_product(
        product_id="hubspot",
        product_type=ProductType.CRM,
        name="HubSpot",
        api_base_url="https://api.hubapi.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"api_key_header": "Authorization"},
    )
    return product


@pytest.fixture
def hubspot_spec():
    """Load the HubSpot spec fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "hubspot_spec.json"
    with open(fixture_path) as f:
        return json.load(f)


def test_get_adapter_for_hubspot_product(hubspot_product):
    """Test getting adapter for HubSpot product."""
    adapter = get_adapter_for_product(hubspot_product)

    assert isinstance(adapter, HubSpotAdapter)
    assert adapter.product_id == "hubspot"
    assert adapter.product_def == hubspot_product


def test_get_adapter_for_unknown_product():
    """Test getting adapter for unsupported product."""
    unknown_product = ProductDefinition(
        product_id="unknown",
        name="Unknown CRM",
        type=ProductType.CRM,
        api_base_url="https://api.unknown.com",
        auth_method=AuthMethod.API_KEY,
    )

    with pytest.raises(AdapterNotFoundError) as exc_info:
        get_adapter_for_product(unknown_product)

    assert "unknown" in str(exc_info.value).lower()
    assert "hubspot" in str(exc_info.value).lower()


def test_discover_capabilities_product_not_found(temp_home):
    """Test discover_capabilities with non-existent product."""
    with pytest.raises(ProductNotFoundError):
        discover_capabilities("nonexistent")


def test_discover_capabilities_success(temp_home, hubspot_product, hubspot_spec):
    """Test successful capability discovery."""
    # Mock the adapter's discover_spec method
    with patch.object(HubSpotAdapter, "discover_spec", return_value=hubspot_spec):
        capabilities = discover_capabilities("hubspot")

        # Check that capabilities were returned
        assert len(capabilities) > 0
        assert all(isinstance(cap, Capability) for cap in capabilities)

        # Check that files were saved
        raw_spec_path = temp_home / "hubspot_raw_spec.json"
        capabilities_path = temp_home / "hubspot_capabilities.json"

        assert raw_spec_path.exists()
        assert capabilities_path.exists()

        # Verify raw spec was saved correctly
        with open(raw_spec_path) as f:
            saved_spec = json.load(f)
        assert saved_spec == hubspot_spec

        # Verify capabilities were saved correctly
        with open(capabilities_path) as f:
            saved_caps = json.load(f)

        assert saved_caps["product_id"] == "hubspot"
        assert saved_caps["total_capabilities"] == len(capabilities)
        assert len(saved_caps["capabilities"]) == len(capabilities)


def test_discover_capabilities_entities(temp_home, hubspot_product, hubspot_spec):
    """Test that discovered capabilities include expected entities."""
    with patch.object(HubSpotAdapter, "discover_spec", return_value=hubspot_spec):
        capabilities = discover_capabilities("hubspot")

        entities = {cap.entity_name for cap in capabilities}
        assert "contacts" in entities
        assert "organisations" in entities
        assert "deals" in entities


def test_discover_capabilities_actions(temp_home, hubspot_product, hubspot_spec):
    """Test that discovered capabilities include expected actions."""
    with patch.object(HubSpotAdapter, "discover_spec", return_value=hubspot_spec):
        capabilities = discover_capabilities("hubspot")

        # Get contacts capabilities
        contact_caps = [cap for cap in capabilities if cap.entity_name == "contacts"]
        actions = {cap.action for cap in contact_caps}

        assert "list" in actions
        assert "get" in actions
        assert "create" in actions
        assert "update" in actions


def test_discover_capabilities_saved_data_structure(
    temp_home, hubspot_product, hubspot_spec
):
    """Test the structure of saved capabilities data."""
    with patch.object(HubSpotAdapter, "discover_spec", return_value=hubspot_spec):
        capabilities = discover_capabilities("hubspot")

        capabilities_path = temp_home / "hubspot_capabilities.json"
        with open(capabilities_path) as f:
            saved_data = json.load(f)

        # Check structure
        assert "product_id" in saved_data
        assert "total_capabilities" in saved_data
        assert "capabilities" in saved_data

        # Check each capability entry
        for cap_data in saved_data["capabilities"]:
            assert "entity_name" in cap_data
            assert "action" in cap_data
            assert "http_method" in cap_data
            assert "path" in cap_data
            assert "score" in cap_data


def test_discover_capabilities_adapter_not_found(temp_home):
    """Test discover_capabilities with unsupported product."""
    # Register an unsupported product
    register_product(
        product_id="salesforce",
        product_type=ProductType.CRM,
        name="Salesforce",
        api_base_url="https://api.salesforce.com",
        auth_method=AuthMethod.OAUTH2,
    )

    with pytest.raises(AdapterNotFoundError):
        discover_capabilities("salesforce")


def test_discover_capabilities_with_empty_spec(temp_home, hubspot_product):
    """Test discover_capabilities with empty spec."""
    empty_spec = {"paths": {}}

    with patch.object(HubSpotAdapter, "discover_spec", return_value=empty_spec):
        capabilities = discover_capabilities("hubspot")

        assert capabilities == []

        # Files should still be created
        raw_spec_path = temp_home / "hubspot_raw_spec.json"
        capabilities_path = temp_home / "hubspot_capabilities.json"

        assert raw_spec_path.exists()
        assert capabilities_path.exists()


def test_get_adapter_case_insensitive():
    """Test that adapter resolution is case-insensitive."""
    # Test with uppercase product_id
    product = ProductDefinition(
        product_id="HUBSPOT",
        name="HubSpot",
        type=ProductType.CRM,
        api_base_url="https://api.hubapi.com",
        auth_method=AuthMethod.API_KEY,
    )

    adapter = get_adapter_for_product(product)
    assert isinstance(adapter, HubSpotAdapter)


def test_discover_capabilities_preserves_product_id(
    temp_home, hubspot_product, hubspot_spec
):
    """Test that capabilities preserve the correct product_id."""
    with patch.object(HubSpotAdapter, "discover_spec", return_value=hubspot_spec):
        capabilities = discover_capabilities("hubspot")

        # All capabilities should have the correct product_id
        for cap in capabilities:
            assert cap.product_id == "hubspot"
