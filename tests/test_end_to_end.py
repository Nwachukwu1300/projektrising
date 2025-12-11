"""Integration tests for Stage 5 end-to-end demo workflow."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from toolkit_engine.core import ProductType, AuthMethod, ConfigError, ProductNotFoundError
from toolkit_engine.core.models import ProductDefinition
from toolkit_engine.demo import run_demo
from toolkit_engine.generator.crm_client import ToolkitCRMClient


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create temporary config directory for testing."""
    config_dir = tmp_path / "toolkit_config"
    config_dir.mkdir()
    monkeypatch.setenv("TOOLKIT_ENGINE_HOME", str(config_dir))
    return config_dir


@pytest.fixture
def sample_product_data():
    """Sample product definition data."""
    return {
        "product_id": "testcrm",
        "type": "crm",
        "name": "Test CRM",
        "api_base_url": "https://api.testcrm.com",
        "auth_method": "oauth2",
        "auth_metadata": {
            "token_url": "https://auth.testcrm.com/token",
            "scopes": ["crm.read", "crm.write"]
        }
    }


@pytest.fixture
def sample_capabilities():
    """Sample capabilities data."""
    return [
        {
            "product_id": "testcrm",
            "entity_name": "contacts",
            "action": "list",
            "http_method": "GET",
            "path": "/api/contacts",
            "score": 0.95
        },
        {
            "product_id": "testcrm",
            "entity_name": "contacts",
            "action": "get",
            "http_method": "GET",
            "path": "/api/contacts/{id}",
            "score": 0.90
        }
    ]


@pytest.fixture
def sample_mapping():
    """Sample mapping data."""
    return {
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
        },
        "organisations": {
            "list": {
                "http_method": "GET",
                "path": "/api/companies"
            }
        }
    }


@pytest.fixture
def mock_crm_client():
    """Create a mock CRM client for testing."""
    client = Mock(spec=ToolkitCRMClient)

    # Mock list_contacts to return sample data
    client.list_contacts.return_value = [
        {
            "id": "101",
            "properties": {
                "firstname": "John",
                "lastname": "Doe",
                "email": "john@example.com"
            }
        },
        {
            "id": "102",
            "properties": {
                "firstname": "Jane",
                "lastname": "Smith",
                "email": "jane@example.com"
            }
        }
    ]

    # Mock get_contact
    client.get_contact.return_value = {
        "id": "101",
        "properties": {
            "firstname": "John",
            "lastname": "Doe",
            "email": "john@example.com"
        }
    }

    # Mock close method
    client.close.return_value = None

    return client


def test_end_to_end_demo_success(
    temp_config_dir,
    sample_product_data,
    sample_capabilities,
    sample_mapping,
    mock_crm_client,
    capsys
):
    """Test successful end-to-end demo workflow with all components."""

    # Step 1: Create product definition file
    product_file = temp_config_dir / "testcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(sample_product_data, f)

    # Step 2: Create capabilities file
    capabilities_file = temp_config_dir / "testcrm_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(sample_capabilities, f)

    # Step 3: Create mapping file
    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(sample_mapping, f)

    # Step 4: Mock generate_integration to return our mock client
    with patch("toolkit_engine.demo.generate_integration", return_value=mock_crm_client):
        # Step 5: Run the demo
        credentials = {"access_token": "test_token"}

        # Should not raise any exceptions
        run_demo("testcrm", credentials)

        # Verify client methods were called
        mock_crm_client.list_contacts.assert_called_once()
        mock_crm_client.get_contact.assert_called_once_with("101")
        mock_crm_client.close.assert_called_once()

    # Verify output messages
    captured = capsys.readouterr()
    assert "Starting demo for 'testcrm'" in captured.out
    assert "✓ Loaded: Test CRM" in captured.out
    assert "✓ Capabilities file exists" in captured.out
    assert "✓ Mapping file exists" in captured.out
    assert "✓ Client created successfully" in captured.out
    assert "✓ Retrieved 2 contacts" in captured.out
    assert "✓ Retrieved single contact: 101" in captured.out
    assert "✓ Demo completed successfully!" in captured.out


def test_demo_missing_mapping(
    temp_config_dir,
    sample_product_data,
    sample_capabilities,
    capsys
):
    """Test demo fails gracefully when mapping file is missing."""

    # Step 1: Create product definition file
    product_file = temp_config_dir / "testcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(sample_product_data, f)

    # Step 2: Create capabilities file
    capabilities_file = temp_config_dir / "testcrm_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(sample_capabilities, f)

    # Step 3: DO NOT create mapping file (this is the test condition)

    # Step 4: Run demo and expect ConfigError
    credentials = {"access_token": "test_token"}

    with pytest.raises(ConfigError) as exc_info:
        run_demo("testcrm", credentials)

    # Verify error message is helpful
    error_message = str(exc_info.value)
    assert "No mapping found" in error_message
    assert "testcrm" in error_message
    assert "select" in error_message.lower()

    # Verify output shows where it got stuck
    captured = capsys.readouterr()
    assert "Starting demo for 'testcrm'" in captured.out
    assert "✓ Loaded: Test CRM" in captured.out
    assert "✓ Capabilities file exists" in captured.out
    assert "✗ Mapping file not found" in captured.out
    assert "toolkit-engine select --id testcrm" in captured.out


def test_demo_product_not_found(temp_config_dir, capsys):
    """Test demo fails when product is not registered."""
    credentials = {"access_token": "test_token"}

    # The demo catches ProductNotFoundError and tries to load from disk,
    # which then raises ConfigError if file doesn't exist
    with pytest.raises((ProductNotFoundError, ConfigError)) as exc_info:
        run_demo("nonexistent", credentials)

    error_message = str(exc_info.value)
    assert "not found" in error_message.lower() or "configuration file" in error_message.lower()

    # Verify helpful output
    captured = capsys.readouterr()
    assert "Starting demo for 'nonexistent'" in captured.out
    assert "✗ Error:" in captured.out
    assert "register" in captured.out.lower()


def test_demo_auto_discovers_capabilities(
    temp_config_dir,
    sample_product_data,
    sample_mapping,
    mock_crm_client,
    capsys
):
    """Test demo automatically runs discovery if capabilities file is missing."""

    # Step 1: Create product definition file
    product_file = temp_config_dir / "testcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(sample_product_data, f)

    # Step 2: DO NOT create capabilities file (will trigger auto-discovery)

    # Step 3: Create mapping file
    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(sample_mapping, f)

    # Step 4: Mock discover_capabilities to return sample data
    mock_capabilities = [
        {"entity_name": "contacts", "action": "list"},
        {"entity_name": "contacts", "action": "get"}
    ]

    with patch("toolkit_engine.demo.discover_capabilities", return_value=mock_capabilities) as mock_discover:
        with patch("toolkit_engine.demo.generate_integration", return_value=mock_crm_client):
            credentials = {"access_token": "test_token"}

            # Should complete successfully with auto-discovery
            run_demo("testcrm", credentials)

            # Verify discovery was called
            mock_discover.assert_called_once_with("testcrm")

    # Verify output shows discovery happened
    captured = capsys.readouterr()
    assert "✗ Capabilities file not found" in captured.out
    assert "Running discovery automatically" in captured.out
    assert "✓ Discovered 2 capabilities" in captured.out


def test_demo_api_error_handling(
    temp_config_dir,
    sample_product_data,
    sample_capabilities,
    sample_mapping,
    capsys
):
    """Test demo handles API errors gracefully."""
    from toolkit_engine.generator.crm_client import APIError

    # Setup files
    product_file = temp_config_dir / "testcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(sample_product_data, f)

    capabilities_file = temp_config_dir / "testcrm_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(sample_capabilities, f)

    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(sample_mapping, f)

    # Create mock client that raises APIError
    mock_client = Mock(spec=ToolkitCRMClient)
    mock_client.list_contacts.side_effect = APIError("Unauthorized", status_code=401)
    mock_client.close.return_value = None

    with patch("toolkit_engine.demo.generate_integration", return_value=mock_client):
        credentials = {"access_token": "invalid_token"}

        with pytest.raises(APIError) as exc_info:
            run_demo("testcrm", credentials)

        assert exc_info.value.status_code == 401

        # Verify close was still called (cleanup)
        mock_client.close.assert_called_once()

    # Verify helpful error output
    captured = capsys.readouterr()
    assert "✗ API Error: Unauthorized" in captured.out
    assert "HTTP Status: 401" in captured.out
    assert "Invalid or expired access token" in captured.out


def test_demo_with_no_contacts_returned(
    temp_config_dir,
    sample_product_data,
    sample_capabilities,
    sample_mapping,
    capsys
):
    """Test demo handles empty contact list gracefully."""

    # Setup files
    product_file = temp_config_dir / "testcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(sample_product_data, f)

    capabilities_file = temp_config_dir / "testcrm_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(sample_capabilities, f)

    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(sample_mapping, f)

    # Create mock client that returns empty list
    mock_client = Mock(spec=ToolkitCRMClient)
    mock_client.list_contacts.return_value = []
    mock_client.close.return_value = None

    with patch("toolkit_engine.demo.generate_integration", return_value=mock_client):
        credentials = {"access_token": "test_token"}

        # Should complete without errors
        run_demo("testcrm", credentials)

        # Verify get_contact was NOT called (no contacts to get)
        mock_client.get_contact.assert_not_called()

    # Verify output
    captured = capsys.readouterr()
    assert "✓ Retrieved 0 contacts" in captured.out
    assert "✓ Demo completed successfully!" in captured.out


def test_demo_full_workflow_integration(
    temp_config_dir,
    sample_product_data,
    sample_capabilities,
    sample_mapping,
    mock_crm_client,
    capsys
):
    """Test complete workflow simulating real user experience."""

    # This test simulates what happens when a user runs:
    # 1. toolkit-engine register --id testcrm ...
    # 2. (capabilities auto-discovered or manual)
    # 3. toolkit-engine select --id testcrm
    # 4. toolkit-engine demo-full --id testcrm --token xxx

    # Simulate Step 1: Product registered (file exists)
    product_file = temp_config_dir / "testcrm_product.json"
    with open(product_file, "w") as f:
        json.dump(sample_product_data, f)

    # Simulate Step 2: Capabilities discovered (file exists)
    capabilities_file = temp_config_dir / "testcrm_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(sample_capabilities, f)

    # Simulate Step 3: User selected endpoints (mapping exists)
    mapping_file = temp_config_dir / "testcrm_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(sample_mapping, f)

    # Simulate Step 4: Run demo-full
    with patch("toolkit_engine.demo.generate_integration", return_value=mock_crm_client):
        credentials = {"access_token": "user_real_token"}

        # Execute the demo
        run_demo("testcrm", credentials)

    # Verify complete workflow executed
    captured = capsys.readouterr()

    # Check all 5 steps completed
    assert "Step 1: Loading product definition" in captured.out
    assert "Step 2: Checking for capabilities" in captured.out
    assert "Step 3: Checking for endpoint mapping" in captured.out
    assert "Step 4: Generating CRM client" in captured.out
    assert "Step 5: Demonstrating API calls" in captured.out

    # Check success indicators
    assert "✓" in captured.out  # Multiple success checkmarks
    assert "Demo completed successfully" in captured.out

    # Check usage instructions at end
    assert "from toolkit_engine.generator import generate_integration" in captured.out
    assert "client = generate_integration('testcrm', credentials)" in captured.out
