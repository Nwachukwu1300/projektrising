"""Tests for Stage 4 builder module."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from toolkit_engine.core import ProductType, AuthMethod, register_product, ConfigError, ProductNotFoundError
from toolkit_engine.core.models import ProductDefinition
from toolkit_engine.generator import generate_integration
from toolkit_engine.generator.crm_client import ToolkitCRMClient
from toolkit_engine.products.base import ProductAdapter


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create temporary config directory."""
    config_dir = tmp_path / "toolkit_config"
    config_dir.mkdir()
    monkeypatch.setenv("TOOLKIT_ENGINE_HOME", str(config_dir))
    return config_dir


@pytest.fixture
def mock_adapter():
    """Create a mock adapter for testing."""
    adapter = Mock(spec=ProductAdapter)
    adapter.build_auth_headers.return_value = {"Authorization": "Bearer test_token"}
    return adapter


@pytest.fixture(autouse=True)
def patch_get_adapter(mock_adapter):
    """Auto-patch get_adapter_for_product for all builder tests."""
    with patch("toolkit_engine.generator.builder.get_adapter_for_product", return_value=mock_adapter):
        yield


@pytest.fixture
def registered_product(temp_config_dir):
    """Register a test product."""
    product = register_product(
        product_id="testcrm",
        product_type=ProductType.CRM,
        name="Test CRM",
        api_base_url="https://api.testcrm.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"api_key_header": "Authorization", "api_key_prefix": "Bearer "},
    )
    return product


@pytest.fixture
def sample_mapping_file(temp_config_dir):
    """Create a sample mapping file."""
    mapping = {
        "contacts": {
            "list": {
                "http_method": "GET",
                "path": "/api/contacts"
            },
            "get": {
                "http_method": "GET",
                "path": "/api/contacts/{id}"
            },
            "create": {
                "http_method": "POST",
                "path": "/api/contacts"
            }
        }
    }

    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping, f)

    return mapping_file


# ===== Integration Tests =====

def test_generate_integration_success(registered_product, sample_mapping_file):
    """Test generating integration with all components."""
    credentials = {"access_token": "test_token"}

    client = generate_integration("testcrm", credentials)

    assert isinstance(client, ToolkitCRMClient)
    assert client.product_def.product_id == "testcrm"
    assert client.credentials == credentials
    assert "contacts" in client.mapping
    assert client.mapping["contacts"]["list"]["http_method"] == "GET"

    client.close()


def test_generate_integration_loads_product_from_disk(sample_mapping_file, temp_config_dir):
    """Test that generate_integration loads product from disk if not in registry."""
    # Create product definition file directly without registering
    product_data = {
        "product_id": "diskcrm",
        "type": "crm",
        "name": "Disk CRM",
        "api_base_url": "https://api.diskcrm.com",
        "auth_method": "api_key",
        "auth_metadata": {"api_key_header": "X-API-Key", "api_key_prefix": ""}
    }

    product_file = temp_config_dir / "diskcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(product_data, f)

    # Create mapping file
    mapping = {
        "contacts": {
            "list": {
                "http_method": "GET",
                "path": "/contacts"
            }
        }
    }
    mapping_file = temp_config_dir / "diskcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping, f)

    credentials = {"api_key": "test"}
    client = generate_integration("diskcrm", credentials)

    assert client.product_def.product_id == "diskcrm"
    assert client.product_def.name == "Disk CRM"

    client.close()


def test_generate_integration_product_not_found(temp_config_dir):
    """Test that generate_integration raises error when product not found."""
    credentials = {"access_token": "test"}

    with pytest.raises(ProductNotFoundError) as exc_info:
        generate_integration("nonexistent", credentials)

    assert "not found" in str(exc_info.value).lower()
    assert "register" in str(exc_info.value).lower()


def test_generate_integration_mapping_not_found(registered_product, temp_config_dir):
    """Test that generate_integration raises error when mapping file missing."""
    # Product exists but no mapping file
    credentials = {"access_token": "test"}

    with pytest.raises(ConfigError) as exc_info:
        generate_integration("testcrm", credentials)

    assert "No mapping found" in str(exc_info.value)
    assert "select" in str(exc_info.value).lower()


def test_generate_integration_passes_credentials(registered_product, sample_mapping_file):
    """Test that credentials are passed to client."""
    credentials = {"access_token": "my_secret_token", "refresh_token": "refresh"}

    client = generate_integration("testcrm", credentials)

    assert client.credentials == credentials

    client.close()


def test_generate_integration_uses_adapter(registered_product, sample_mapping_file):
    """Test that generate_integration uses correct adapter."""
    credentials = {"access_token": "test"}

    client = generate_integration("testcrm", credentials)

    # Adapter should be set
    assert client.adapter is not None
    # Adapter should be able to build headers
    headers = client.adapter.build_auth_headers(credentials)
    assert "Authorization" in headers

    client.close()


def test_generate_integration_creates_http_client(registered_product, sample_mapping_file):
    """Test that integration creates HTTP client."""
    credentials = {"access_token": "test"}

    client = generate_integration("testcrm", credentials)

    assert client.http_client is not None
    assert client._owns_client is True  # Should own the client

    client.close()


def test_generate_integration_full_workflow(temp_config_dir):
    """Test complete workflow: register, create mapping, generate."""
    # Step 1: Register product
    product = register_product(
        product_id="workflow_test",
        product_type=ProductType.CRM,
        name="Workflow Test CRM",
        api_base_url="https://api.workflow.com",
        auth_method=AuthMethod.OAUTH2,
        auth_metadata={"token_url": "https://auth.workflow.com/token", "scopes": ["crm.read"]},
    )

    # Step 2: Create mapping (simulating Stage 3 output)
    mapping = {
        "contacts": {
            "list": {"http_method": "GET", "path": "/v1/contacts"},
            "get": {"http_method": "GET", "path": "/v1/contacts/{contactId}"},
            "create": {"http_method": "POST", "path": "/v1/contacts"},
            "update": {"http_method": "PUT", "path": "/v1/contacts/{contactId}"}
        },
        "organisations": {
            "list": {"http_method": "GET", "path": "/v1/companies"},
            "get": {"http_method": "GET", "path": "/v1/companies/{id}"}
        }
    }

    mapping_file = temp_config_dir / "workflow_test_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping, f)

    # Step 3: Generate integration
    credentials = {"access_token": "workflow_token"}
    client = generate_integration("workflow_test", credentials)

    # Verify everything is connected
    assert client.product_def.product_id == "workflow_test"
    assert client.product_def.auth_method == AuthMethod.OAUTH2
    assert "contacts" in client.mapping
    assert "organisations" in client.mapping
    assert len(client.mapping["contacts"]) == 4  # list, get, create, update
    assert len(client.mapping["organisations"]) == 2  # list, get

    client.close()


def test_integration_with_different_auth_methods(temp_config_dir):
    """Test generate_integration works with different auth methods."""
    # Test with API Key
    api_key_product = register_product(
        product_id="apikey_crm",
        product_type=ProductType.CRM,
        name="API Key CRM",
        api_base_url="https://api.apikey.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"api_key_header": "X-API-Key", "api_key_prefix": ""},
    )

    mapping = {"contacts": {"list": {"http_method": "GET", "path": "/contacts"}}}
    mapping_file = temp_config_dir / "apikey_crm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping, f)

    client_api_key = generate_integration("apikey_crm", {"api_key": "key123"})
    assert client_api_key.credentials == {"api_key": "key123"}
    client_api_key.close()

    # Test with OAuth2
    oauth_product = register_product(
        product_id="oauth_crm",
        product_type=ProductType.CRM,
        name="OAuth CRM",
        api_base_url="https://api.oauth.com",
        auth_method=AuthMethod.OAUTH2,
        auth_metadata={"token_url": "https://auth.oauth.com/token", "scopes": []},
    )

    mapping_file = temp_config_dir / "oauth_crm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping, f)

    client_oauth = generate_integration("oauth_crm", {"access_token": "oauth_token"})
    assert client_oauth.credentials == {"access_token": "oauth_token"}
    client_oauth.close()


def test_generate_integration_mapping_structure(registered_product, temp_config_dir):
    """Test that mapping structure is correctly loaded."""
    mapping = {
        "contacts": {
            "list": {"http_method": "GET", "path": "/api/v2/contacts"},
            "get": {"http_method": "GET", "path": "/api/v2/contacts/{id}"}
        },
        "deals": {
            "create": {"http_method": "POST", "path": "/api/v2/deals"}
        }
    }

    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping, f)

    client = generate_integration("testcrm", {"access_token": "test"})

    # Verify mapping structure
    assert "contacts" in client.mapping
    assert "deals" in client.mapping
    assert client.mapping["contacts"]["list"]["path"] == "/api/v2/contacts"
    assert client.mapping["deals"]["create"]["http_method"] == "POST"

    client.close()
