"""Tests for the product registry."""

import pytest
from toolkit_engine.core.models import (
    ProductType,
    AuthMethod,
    ProductDefinition,
    ProductNotFoundError,
)
from toolkit_engine.core.registry import (
    register_product,
    get_product,
    list_products,
    reset_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the registry before each test."""
    reset_registry()
    yield
    reset_registry()


def test_register_and_get_product():
    """Test registering and retrieving a product."""
    product = register_product(
        product_id="hubspot",
        product_type=ProductType.CRM,
        name="HubSpot",
        api_base_url="https://api.hubapi.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"key": "value"},
    )

    assert product.product_id == "hubspot"
    assert product.name == "HubSpot"
    assert product.type == ProductType.CRM
    assert product.api_base_url == "https://api.hubapi.com"
    assert product.auth_method == AuthMethod.API_KEY
    assert product.auth_metadata == {"key": "value"}

    retrieved = get_product("hubspot")
    assert retrieved.product_id == product.product_id
    assert retrieved.name == product.name
    assert retrieved.type == product.type
    assert retrieved.api_base_url == product.api_base_url
    assert retrieved.auth_method == product.auth_method
    assert retrieved.auth_metadata == product.auth_metadata


def test_register_product_overwrite():
    """Test that registering a product twice overwrites the first."""
    register_product(
        product_id="test",
        product_type=ProductType.CRM,
        name="Original Name",
        api_base_url="https://api.original.com",
        auth_method=AuthMethod.API_KEY,
    )

    register_product(
        product_id="test",
        product_type=ProductType.ACCOUNTING,
        name="New Name",
        api_base_url="https://api.new.com",
        auth_method=AuthMethod.OAUTH2,
    )

    product = get_product("test")
    assert product.name == "New Name"
    assert product.type == ProductType.ACCOUNTING
    assert product.api_base_url == "https://api.new.com"
    assert product.auth_method == AuthMethod.OAUTH2


def test_get_product_not_found():
    """Test retrieving a non-existent product raises ProductNotFoundError."""
    with pytest.raises(ProductNotFoundError) as exc_info:
        get_product("nonexistent")

    assert "nonexistent" in str(exc_info.value)


def test_list_products():
    """Test listing multiple products."""
    register_product(
        product_id="hubspot",
        product_type=ProductType.CRM,
        name="HubSpot",
        api_base_url="https://api.hubapi.com",
        auth_method=AuthMethod.API_KEY,
    )

    register_product(
        product_id="xero",
        product_type=ProductType.ACCOUNTING,
        name="Xero",
        api_base_url="https://api.xero.com",
        auth_method=AuthMethod.OAUTH2,
    )

    products = list_products()
    assert len(products) == 2

    # Should be sorted by product_id
    assert products[0].product_id == "hubspot"
    assert products[1].product_id == "xero"


def test_list_products_empty():
    """Test listing products when none are registered."""
    products = list_products()
    assert len(products) == 0
    assert products == []


def test_list_products_order():
    """Test that list_products returns products in sorted order."""
    # Register in reverse alphabetical order
    register_product(
        product_id="zebra",
        product_type=ProductType.CRM,
        name="Zebra CRM",
        api_base_url="https://api.zebra.com",
        auth_method=AuthMethod.API_KEY,
    )

    register_product(
        product_id="alpha",
        product_type=ProductType.CRM,
        name="Alpha CRM",
        api_base_url="https://api.alpha.com",
        auth_method=AuthMethod.API_KEY,
    )

    register_product(
        product_id="beta",
        product_type=ProductType.CRM,
        name="Beta CRM",
        api_base_url="https://api.beta.com",
        auth_method=AuthMethod.API_KEY,
    )

    products = list_products()
    assert len(products) == 3
    assert products[0].product_id == "alpha"
    assert products[1].product_id == "beta"
    assert products[2].product_id == "zebra"


def test_reset_registry():
    """Test that reset_registry clears all products."""
    register_product(
        product_id="test1",
        product_type=ProductType.CRM,
        name="Test 1",
        api_base_url="https://api.test1.com",
        auth_method=AuthMethod.API_KEY,
    )

    register_product(
        product_id="test2",
        product_type=ProductType.CRM,
        name="Test 2",
        api_base_url="https://api.test2.com",
        auth_method=AuthMethod.API_KEY,
    )

    assert len(list_products()) == 2

    reset_registry()

    assert len(list_products()) == 0

    with pytest.raises(ProductNotFoundError):
        get_product("test1")


def test_register_product_default_auth_metadata():
    """Test that register_product handles None auth_metadata correctly."""
    product = register_product(
        product_id="test",
        product_type=ProductType.CRM,
        name="Test",
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata=None,
    )

    assert product.auth_metadata == {}
