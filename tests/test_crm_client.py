"""Tests for Stage 4 CRM client."""

import json
import pytest
import httpx
from unittest.mock import Mock, MagicMock, patch

from toolkit_engine.core.models import ProductDefinition, ProductType, AuthMethod
from toolkit_engine.generator.crm_client import ToolkitCRMClient, APIError
from toolkit_engine.products.base import ProductAdapter


@pytest.fixture
def mock_product_def():
    """Create a mock product definition."""
    return ProductDefinition(
        product_id="test",
        type=ProductType.CRM,
        name="Test CRM",
        api_base_url="https://api.test.com",
        auth_method=AuthMethod.API_KEY,
        auth_metadata={"api_key_header": "Authorization", "api_key_prefix": "Bearer "},
    )


@pytest.fixture
def mock_adapter():
    """Create a mock product adapter."""
    adapter = Mock(spec=ProductAdapter)
    adapter.build_auth_headers.return_value = {"Authorization": "Bearer test_token"}
    return adapter


@pytest.fixture
def sample_mapping():
    """Create a sample endpoint mapping."""
    return {
        "contacts": {
            "list": {
                "http_method": "GET",
                "path": "/crm/v3/objects/contacts"
            },
            "get": {
                "http_method": "GET",
                "path": "/crm/v3/objects/contacts/{contactId}"
            },
            "create": {
                "http_method": "POST",
                "path": "/crm/v3/objects/contacts"
            },
            "update": {
                "http_method": "PATCH",
                "path": "/crm/v3/objects/contacts/{contactId}"
            }
        },
        "organisations": {
            "list": {
                "http_method": "GET",
                "path": "/crm/v3/objects/companies"
            },
            "get": {
                "http_method": "GET",
                "path": "/crm/v3/objects/companies/{companyId}"
            },
            "create": {
                "http_method": "POST",
                "path": "/crm/v3/objects/companies"
            },
            "update": {
                "http_method": "PATCH",
                "path": "/crm/v3/objects/companies/{companyId}"
            }
        }
    }


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    return Mock(spec=httpx.Client)


@pytest.fixture
def crm_client(mock_product_def, sample_mapping, mock_adapter, mock_http_client):
    """Create a CRM client for testing."""
    return ToolkitCRMClient(
        product_def=mock_product_def,
        mapping=sample_mapping,
        adapter=mock_adapter,
        credentials={"access_token": "test_token"},
        http_client=mock_http_client,
    )


# ===== Construction and Lifecycle Tests =====

def test_client_initialization(mock_product_def, sample_mapping, mock_adapter):
    """Test that client initializes correctly."""
    client = ToolkitCRMClient(
        product_def=mock_product_def,
        mapping=sample_mapping,
        adapter=mock_adapter,
        credentials={"access_token": "test"},
    )

    assert client.product_def == mock_product_def
    assert client.mapping == sample_mapping
    assert client.adapter == mock_adapter
    assert client.credentials == {"access_token": "test"}
    assert client.timeout_seconds == 10.0
    assert client.max_retries == 3
    assert client._owns_client is True


def test_client_with_custom_http_client(mock_product_def, sample_mapping, mock_adapter, mock_http_client):
    """Test that client uses provided HTTP client."""
    client = ToolkitCRMClient(
        product_def=mock_product_def,
        mapping=sample_mapping,
        adapter=mock_adapter,
        credentials={"access_token": "test"},
        http_client=mock_http_client,
    )

    assert client.http_client == mock_http_client
    assert client._owns_client is False


def test_client_close(mock_product_def, sample_mapping, mock_adapter):
    """Test that close() closes owned HTTP client."""
    client = ToolkitCRMClient(
        product_def=mock_product_def,
        mapping=sample_mapping,
        adapter=mock_adapter,
        credentials={"access_token": "test"},
    )

    # Mock the http_client
    client.http_client = Mock()
    client.close()

    client.http_client.close.assert_called_once()


def test_client_context_manager(mock_product_def, sample_mapping, mock_adapter):
    """Test context manager support."""
    with ToolkitCRMClient(
        product_def=mock_product_def,
        mapping=sample_mapping,
        adapter=mock_adapter,
        credentials={"access_token": "test"},
    ) as client:
        assert client is not None

    # Client should be closed after context


# ===== URL Building Tests =====

def test_build_url(crm_client):
    """Test URL building from base URL and path."""
    url = crm_client._build_url("/crm/v3/objects/contacts")
    assert url == "https://api.test.com/crm/v3/objects/contacts"


def test_build_url_strips_slashes(crm_client):
    """Test that URL building handles extra slashes."""
    # Base URL with trailing slash
    crm_client.product_def.api_base_url = "https://api.test.com/"
    url = crm_client._build_url("/crm/v3/objects/contacts")
    assert url == "https://api.test.com/crm/v3/objects/contacts"


def test_substitute_path_params(crm_client):
    """Test path parameter substitution."""
    path = "/crm/v3/objects/contacts/{contactId}"
    result = crm_client._substitute_path_params(path, contactId="123")
    assert result == "/crm/v3/objects/contacts/123"


def test_substitute_multiple_path_params(crm_client):
    """Test substituting multiple path parameters."""
    path = "/api/{version}/objects/{objectType}/{id}"
    result = crm_client._substitute_path_params(
        path,
        version="v3",
        objectType="contacts",
        id="456"
    )
    assert result == "/api/v3/objects/contacts/456"


# ===== HTTP Request Tests =====

def test_request_success(crm_client, mock_http_client):
    """Test successful HTTP request."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "123"}'
    mock_response.json.return_value = {"id": "123"}
    mock_http_client.request.return_value = mock_response

    result = crm_client._request("GET", "/crm/v3/objects/contacts")

    assert result == {"id": "123"}
    mock_http_client.request.assert_called_once()


def test_request_builds_auth_headers(crm_client, mock_http_client, mock_adapter):
    """Test that request builds auth headers."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{}'
    mock_response.json.return_value = {}
    mock_http_client.request.return_value = mock_response

    crm_client._request("GET", "/test")

    mock_adapter.build_auth_headers.assert_called_once_with({"access_token": "test_token"})


def test_request_retries_on_5xx(crm_client, mock_http_client):
    """Test that request retries on 5xx errors."""
    # First two attempts fail with 500, third succeeds
    mock_response_fail = Mock()
    mock_response_fail.status_code = 500
    mock_response_fail.text = "Internal Server Error"

    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.content = b'{"ok": true}'
    mock_response_success.json.return_value = {"ok": True}

    mock_http_client.request.side_effect = [
        mock_response_fail,
        mock_response_fail,
        mock_response_success
    ]

    with patch("time.sleep"):  # Mock sleep to speed up test
        result = crm_client._request("GET", "/test")

    assert result == {"ok": True}
    assert mock_http_client.request.call_count == 3


def test_request_fails_on_4xx(crm_client, mock_http_client):
    """Test that request fails immediately on 4xx errors."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_http_client.request.return_value = mock_response

    with pytest.raises(APIError) as exc_info:
        crm_client._request("GET", "/test")

    assert exc_info.value.status_code == 404
    assert "404" in str(exc_info.value)
    # Should not retry
    assert mock_http_client.request.call_count == 1


def test_request_raises_after_max_retries(crm_client, mock_http_client):
    """Test that request raises APIError after max retries."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Server Error"
    mock_http_client.request.return_value = mock_response

    with patch("time.sleep"):
        with pytest.raises(APIError) as exc_info:
            crm_client._request("GET", "/test")

    assert exc_info.value.status_code == 500
    assert mock_http_client.request.call_count == 3  # max_retries


def test_request_retries_on_network_error(crm_client, mock_http_client):
    """Test that request retries on network errors."""
    # First attempt fails with network error, second succeeds
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{}'
    mock_response.json.return_value = {}

    mock_http_client.request.side_effect = [
        httpx.RequestError("Connection failed"),
        mock_response
    ]

    with patch("time.sleep"):
        result = crm_client._request("GET", "/test")

    assert result == {}
    assert mock_http_client.request.call_count == 2


def test_request_with_query_params(crm_client, mock_http_client):
    """Test request with query parameters."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{}'
    mock_response.json.return_value = {}
    mock_http_client.request.return_value = mock_response

    crm_client._request("GET", "/test", params={"limit": 10, "offset": 20})

    call_kwargs = mock_http_client.request.call_args[1]
    assert call_kwargs["params"] == {"limit": 10, "offset": 20}


def test_request_with_json_body(crm_client, mock_http_client):
    """Test request with JSON body."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "new"}'
    mock_response.json.return_value = {"id": "new"}
    mock_http_client.request.return_value = mock_response

    payload = {"name": "Test"}
    result = crm_client._request("POST", "/test", json_body=payload)

    assert result == {"id": "new"}
    call_kwargs = mock_http_client.request.call_args[1]
    assert call_kwargs["json"] == payload


def test_request_with_path_params(crm_client, mock_http_client):
    """Test request with path parameter substitution."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{}'
    mock_response.json.return_value = {}
    mock_http_client.request.return_value = mock_response

    crm_client._request("GET", "/contacts/{contactId}", path_params={"contactId": "123"})

    call_kwargs = mock_http_client.request.call_args[1]
    assert "/contacts/123" in call_kwargs["url"]


def test_request_empty_response(crm_client, mock_http_client):
    """Test request with empty response body."""
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.content = b''
    mock_http_client.request.return_value = mock_response

    result = crm_client._request("DELETE", "/test")

    assert result == {}


# ===== Contact Methods Tests =====

def test_list_contacts_success(crm_client, mock_http_client):
    """Test listing contacts."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"results": [{"id": "1"}, {"id": "2"}]}'
    mock_response.json.return_value = {"results": [{"id": "1"}, {"id": "2"}]}
    mock_http_client.request.return_value = mock_response

    contacts = crm_client.list_contacts()

    assert len(contacts) == 2
    assert contacts[0]["id"] == "1"
    assert contacts[1]["id"] == "2"


def test_list_contacts_with_filters(crm_client, mock_http_client):
    """Test listing contacts with filters."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"results": []}'
    mock_response.json.return_value = {"results": []}
    mock_http_client.request.return_value = mock_response

    crm_client.list_contacts(filters={"limit": 5})

    call_kwargs = mock_http_client.request.call_args[1]
    assert call_kwargs["params"] == {"limit": 5}


def test_list_contacts_handles_list_response(crm_client, mock_http_client):
    """Test list_contacts handles direct list response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'[{"id": "1"}]'
    mock_response.json.return_value = [{"id": "1"}]
    mock_http_client.request.return_value = mock_response

    contacts = crm_client.list_contacts()

    assert len(contacts) == 1
    assert contacts[0]["id"] == "1"


def test_list_contacts_handles_data_response(crm_client, mock_http_client):
    """Test list_contacts handles 'data' key response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"data": [{"id": "1"}]}'
    mock_response.json.return_value = {"data": [{"id": "1"}]}
    mock_http_client.request.return_value = mock_response

    contacts = crm_client.list_contacts()

    assert len(contacts) == 1
    assert contacts[0]["id"] == "1"


def test_list_contacts_no_endpoint(crm_client):
    """Test list_contacts raises error when no endpoint configured."""
    crm_client.mapping["contacts"].pop("list")

    with pytest.raises(ValueError) as exc_info:
        crm_client.list_contacts()

    assert "No 'list' endpoint configured" in str(exc_info.value)


def test_get_contact_success(crm_client, mock_http_client):
    """Test getting a single contact."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "123", "name": "John"}'
    mock_response.json.return_value = {"id": "123", "name": "John"}
    mock_http_client.request.return_value = mock_response

    contact = crm_client.get_contact("123")

    assert contact["id"] == "123"
    assert contact["name"] == "John"


def test_create_contact_success(crm_client, mock_http_client):
    """Test creating a contact."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "new", "name": "Jane"}'
    mock_response.json.return_value = {"id": "new", "name": "Jane"}
    mock_http_client.request.return_value = mock_response

    payload = {"name": "Jane", "email": "jane@test.com"}
    contact = crm_client.create_contact(payload)

    assert contact["id"] == "new"
    call_kwargs = mock_http_client.request.call_args[1]
    assert call_kwargs["json"] == payload


def test_update_contact_success(crm_client, mock_http_client):
    """Test updating a contact."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "123", "name": "Updated"}'
    mock_response.json.return_value = {"id": "123", "name": "Updated"}
    mock_http_client.request.return_value = mock_response

    payload = {"name": "Updated"}
    contact = crm_client.update_contact("123", payload)

    assert contact["name"] == "Updated"


# ===== Organisation Methods Tests =====

def test_list_organisations_success(crm_client, mock_http_client):
    """Test listing organisations."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"results": [{"id": "org1"}]}'
    mock_response.json.return_value = {"results": [{"id": "org1"}]}
    mock_http_client.request.return_value = mock_response

    orgs = crm_client.list_organisations()

    assert len(orgs) == 1
    assert orgs[0]["id"] == "org1"


def test_get_organisation_success(crm_client, mock_http_client):
    """Test getting a single organisation."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "org1", "name": "Acme Corp"}'
    mock_response.json.return_value = {"id": "org1", "name": "Acme Corp"}
    mock_http_client.request.return_value = mock_response

    org = crm_client.get_organisation("org1")

    assert org["id"] == "org1"
    assert org["name"] == "Acme Corp"


def test_create_organisation_success(crm_client, mock_http_client):
    """Test creating an organisation."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "new_org"}'
    mock_response.json.return_value = {"id": "new_org"}
    mock_http_client.request.return_value = mock_response

    payload = {"name": "New Corp"}
    org = crm_client.create_organisation(payload)

    assert org["id"] == "new_org"


def test_update_organisation_success(crm_client, mock_http_client):
    """Test updating an organisation."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "org1", "name": "Updated Corp"}'
    mock_response.json.return_value = {"id": "org1", "name": "Updated Corp"}
    mock_http_client.request.return_value = mock_response

    payload = {"name": "Updated Corp"}
    org = crm_client.update_organisation("org1", payload)

    assert org["name"] == "Updated Corp"


# ===== APIError Tests =====

def test_api_error_with_status_code():
    """Test APIError stores status code."""
    error = APIError("Request failed", status_code=404)
    assert str(error) == "Request failed"
    assert error.status_code == 404


def test_api_error_without_status_code():
    """Test APIError works without status code."""
    error = APIError("Network error")
    assert str(error) == "Network error"
    assert error.status_code is None
