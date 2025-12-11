"""Tests for the configuration store."""

import json
import os
import pytest
from pathlib import Path

from toolkit_engine.core.models import (
    ProductType,
    AuthMethod,
    ProductDefinition,
    ConfigError,
)
from toolkit_engine.core.config_store import (
    get_base_dir,
    product_config_path,
    save_json,
    load_json,
    save_product_definition,
    load_product_definition,
)


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Set up a temporary home directory for config storage."""
    monkeypatch.setenv("TOOLKIT_ENGINE_HOME", str(tmp_path))
    return tmp_path


def test_get_base_dir_with_env_var(temp_home):
    """Test get_base_dir uses TOOLKIT_ENGINE_HOME environment variable."""
    base_dir = get_base_dir()
    assert base_dir == temp_home
    assert base_dir.exists()


def test_get_base_dir_creates_directory(temp_home):
    """Test get_base_dir creates the directory if it doesn't exist."""
    # Remove the directory
    temp_home.rmdir()
    assert not temp_home.exists()

    # get_base_dir should create it
    base_dir = get_base_dir()
    assert base_dir.exists()
    assert base_dir.is_dir()


def test_product_config_path(temp_home):
    """Test product_config_path generates correct paths."""
    path = product_config_path("hubspot", "config")
    assert path == temp_home / "hubspot_config.json"

    path = product_config_path("xero", "mapping")
    assert path == temp_home / "xero_mapping.json"


def test_save_and_load_json(temp_home):
    """Test saving and loading JSON data."""
    data = {
        "key1": "value1",
        "key2": 42,
        "key3": ["list", "of", "items"],
    }

    # Save JSON
    path = save_json("test_product", "config", data)
    assert path.exists()
    assert path == temp_home / "test_product_config.json"

    # Load JSON
    loaded_data = load_json("test_product", "config")
    assert loaded_data == data


def test_save_json_creates_parent_directories(temp_home):
    """Test save_json creates parent directories if needed."""
    # This should work even though the directory structure exists
    data = {"test": "data"}
    path = save_json("nested_product", "config", data)

    assert path.exists()
    loaded = load_json("nested_product", "config")
    assert loaded == data


def test_load_json_missing_file(temp_home):
    """Test load_json raises ConfigError for missing file."""
    with pytest.raises(ConfigError) as exc_info:
        load_json("nonexistent", "config")

    assert "not found" in str(exc_info.value).lower()


def test_load_json_invalid_json(temp_home):
    """Test load_json raises ConfigError for invalid JSON."""
    path = product_config_path("invalid", "config")
    path.write_text("{ invalid json content")

    with pytest.raises(ConfigError) as exc_info:
        load_json("invalid", "config")

    assert "invalid json" in str(exc_info.value).lower()


def test_save_and_load_product_definition(temp_home):
    """Test saving and loading a ProductDefinition."""
    product = ProductDefinition(
        product_id="hubspot",
        name="HubSpot",
        type=ProductType.CRM,
        api_base_url="https://api.hubapi.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"api_key_header": "Authorization"},
    )

    # Save
    path = save_product_definition(product)
    assert path.exists()
    assert path == temp_home / "hubspot_product.json"

    # Load
    loaded_product = load_product_definition("hubspot")
    assert loaded_product.product_id == product.product_id
    assert loaded_product.name == product.name
    assert loaded_product.type == product.type
    assert loaded_product.api_base_url == product.api_base_url
    assert loaded_product.auth_method == product.auth_method
    assert loaded_product.auth_metadata == product.auth_metadata


def test_load_product_definition_missing_file(temp_home):
    """Test load_product_definition raises ConfigError for missing file."""
    with pytest.raises(ConfigError) as exc_info:
        load_product_definition("nonexistent")

    assert "not found" in str(exc_info.value).lower()


def test_load_product_definition_invalid_data(temp_home):
    """Test load_product_definition raises ConfigError for invalid data."""
    # Save invalid product data
    invalid_data = {
        "product_id": "invalid",
        "name": "Invalid",
        # Missing required fields
    }
    save_json("invalid", "product", invalid_data)

    with pytest.raises(ConfigError) as exc_info:
        load_product_definition("invalid")

    assert "failed to parse" in str(exc_info.value).lower()


def test_product_definition_round_trip_with_all_fields(temp_home):
    """Test round-trip conversion with all fields populated."""
    product = ProductDefinition(
        product_id="xero",
        name="Xero",
        type=ProductType.ACCOUNTING,
        api_base_url="https://api.xero.com",
        auth_method=AuthMethod.OAUTH2,
        auth_metadata={
            "token_url": "https://identity.xero.com/connect/token",
            "scopes": ["accounting.transactions", "accounting.contacts"],
        },
    )

    save_product_definition(product)
    loaded = load_product_definition("xero")

    assert loaded.product_id == product.product_id
    assert loaded.name == product.name
    assert loaded.type == product.type
    assert loaded.api_base_url == product.api_base_url
    assert loaded.auth_method == product.auth_method
    assert loaded.auth_metadata == product.auth_metadata


def test_product_definition_round_trip_with_empty_metadata(temp_home):
    """Test round-trip conversion with empty auth_metadata."""
    product = ProductDefinition(
        product_id="test",
        name="Test",
        type=ProductType.CRM,
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={},
    )

    save_product_definition(product)
    loaded = load_product_definition("test")

    assert loaded.auth_metadata == {}


def test_json_format(temp_home):
    """Test that saved JSON is properly formatted."""
    data = {"key": "value", "number": 42}
    path = save_json("formatted", "config", data)

    # Read the raw file content
    content = path.read_text()

    # Should be indented (pretty printed)
    assert "\n" in content
    assert "  " in content

    # Should be valid JSON
    parsed = json.loads(content)
    assert parsed == data
