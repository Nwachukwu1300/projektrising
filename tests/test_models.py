"""Tests for core data models."""

import pytest
from toolkit_engine.core.models import (
    ProductType,
    AuthMethod,
    ProductDefinition,
    Capability,
    ProductNotFoundError,
    ConfigError,
)


def test_product_type_enum():
    """Test ProductType enum values."""
    assert ProductType.CRM.value == "crm"
    assert ProductType.ACCOUNTING.value == "accounting"
    assert ProductType("crm") == ProductType.CRM
    assert ProductType("accounting") == ProductType.ACCOUNTING


def test_auth_method_enum():
    """Test AuthMethod enum values."""
    assert AuthMethod.API_KEY.value == "api_key"
    assert AuthMethod.OAUTH2.value == "oauth2"
    assert AuthMethod("api_key") == AuthMethod.API_KEY
    assert AuthMethod("oauth2") == AuthMethod.OAUTH2


def test_product_definition_creation():
    """Test creating a ProductDefinition with valid fields."""
    product = ProductDefinition(
        product_id="test_crm",
        name="Test CRM",
        type=ProductType.CRM,
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"key": "value"},
    )

    assert product.product_id == "test_crm"
    assert product.name == "Test CRM"
    assert product.type == ProductType.CRM
    assert product.api_base_url == "https://api.test.com"
    assert product.auth_method == AuthMethod.API_KEY
    assert product.auth_metadata == {"key": "value"}


def test_product_definition_default_auth_metadata():
    """Test ProductDefinition with default auth_metadata."""
    product = ProductDefinition(
        product_id="test_crm",
        name="Test CRM",
        type=ProductType.CRM,
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.API_KEY,
    )

    assert product.auth_metadata == {}


def test_product_definition_to_dict():
    """Test converting ProductDefinition to dictionary."""
    product = ProductDefinition(
        product_id="test_crm",
        name="Test CRM",
        type=ProductType.CRM,
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"key": "value"},
    )

    product_dict = product.to_dict()

    assert product_dict["product_id"] == "test_crm"
    assert product_dict["name"] == "Test CRM"
    assert product_dict["type"] == "crm"
    assert product_dict["api_base_url"] == "https://api.test.com"
    assert product_dict["auth_method"] == "api_key"
    assert product_dict["auth_metadata"] == {"key": "value"}


def test_product_definition_from_dict():
    """Test creating ProductDefinition from dictionary."""
    data = {
        "product_id": "test_crm",
        "name": "Test CRM",
        "type": "crm",
        "api_base_url": "https://api.test.com",
        "auth_method": "api_key",
        "auth_metadata": {"key": "value"},
    }

    product = ProductDefinition.from_dict(data)

    assert product.product_id == "test_crm"
    assert product.name == "Test CRM"
    assert product.type == ProductType.CRM
    assert product.api_base_url == "https://api.test.com"
    assert product.auth_method == AuthMethod.API_KEY
    assert product.auth_metadata == {"key": "value"}


def test_product_definition_round_trip():
    """Test round-trip conversion to/from dictionary."""
    original = ProductDefinition(
        product_id="test_crm",
        name="Test CRM",
        type=ProductType.ACCOUNTING,
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.OAUTH2,
        auth_metadata={"token_url": "https://auth.test.com"},
    )

    product_dict = original.to_dict()
    reconstructed = ProductDefinition.from_dict(product_dict)

    assert reconstructed.product_id == original.product_id
    assert reconstructed.name == original.name
    assert reconstructed.type == original.type
    assert reconstructed.api_base_url == original.api_base_url
    assert reconstructed.auth_method == original.auth_method
    assert reconstructed.auth_metadata == original.auth_metadata


def test_capability_creation():
    """Test creating a Capability."""
    capability = Capability(
        product_id="test_crm",
        entity_name="contacts",
        action="list",
        http_method="GET",
        path="/contacts",
        request_schema={"page": "int"},
        response_schema={"results": "array"},
        score=0.95,
    )

    assert capability.product_id == "test_crm"
    assert capability.entity_name == "contacts"
    assert capability.action == "list"
    assert capability.http_method == "GET"
    assert capability.path == "/contacts"
    assert capability.request_schema == {"page": "int"}
    assert capability.response_schema == {"results": "array"}
    assert capability.score == 0.95


def test_capability_defaults():
    """Test Capability with default values."""
    capability = Capability(
        product_id="test_crm",
        entity_name="contacts",
        action="list",
        http_method="GET",
        path="/contacts",
    )

    assert capability.request_schema is None
    assert capability.response_schema is None
    assert capability.score is None


def test_custom_exceptions():
    """Test custom exception types."""
    with pytest.raises(ProductNotFoundError):
        raise ProductNotFoundError("Test error")

    with pytest.raises(ConfigError):
        raise ConfigError("Test error")
