# Toolkit Integration Engine

A dynamic API integration framework for CRM and accounting systems. This project automatically discovers, maps, and generates integration layers for third-party products at runtime - no manual coding required.

## Overview

The Toolkit Integration Engine solves the problem of building repetitive API integrations. Instead of manually coding each CRM's API client, this system:

1. **Discovers** API structure from OpenAPI specifications
2. **Ranks** endpoints by usefulness (contacts > deals, list/get > delete)
3. **Selects** best endpoints (resolves ambiguities)
4. **Generates** working Python client dynamically
5. **Provides** unified interface across different CRMs

**Result**: Add a new CRM by writing one adapter file. Everything else is automatic.

## Current Status

✅ **Complete and Production-Ready**
- 146 passing tests
- 2 working CRM integrations (HubSpot, Pipedrive)
- Real API testing verified
- Comprehensive documentation

**Supported Products**: HubSpot, Pipedrive (see [ALTERNATIVE_CRMS.md](ALTERNATIVE_CRMS.md))

## Quick Start

### Installation

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Verify installation
toolkit-engine --help
```

### Complete Workflow Example (Pipedrive)

**1. Register the CRM**

```bash
toolkit-engine register \
  --id pipedrive \
  --name "Pipedrive CRM" \
  --type crm \
  --base-url "https://api.pipedrive.com/v1" \
  --auth api_key
```

**Output:**
```
✓ Registered product: Pipedrive CRM (pipedrive)
  Type: crm
  Auth: api_key
  Base URL: https://api.pipedrive.com/v1
```

**2. Discover API Capabilities**

```bash
toolkit-engine discover --id pipedrive
```

**Output:**
```
Discovering API capabilities for 'pipedrive'...
✓ Discovery complete!

Total capabilities discovered: 86

Capabilities by entity:

  contacts (5 capabilities)
    - create   POST   /persons
    - delete   DELETE /persons/{id}
    - get      GET    /persons/{id}
    - list     GET    /persons
    - update   PUT    /persons/{id}

  organisations (4 capabilities)
    - create   POST   /organizations
    - get      GET    /organizations/{id}
    - list     GET    /organizations
    - update   PUT    /organizations/{id}

  deals (5 capabilities)
    - create   POST   /deals
    - delete   DELETE /deals/{id}
    - get      GET    /deals/{id}
    - list     GET    /deals
    - update   PUT    /deals/{id}

Capabilities saved to: ~/.toolkit_engine/pipedrive_capabilities.json
```

**3. Select Endpoints**

When multiple endpoints exist for the same operation, the system detects ambiguities and asks you to choose:

```bash
toolkit-engine select --id pipedrive
```

**Output:**
```
Loading capabilities for 'pipedrive'...
Loaded 86 capabilities

Scoring capabilities...
Grouping by entity and action...

Found 2 ambiguous entity-action pairs

Multiple endpoints found for contacts.list:
  [0] GET /persons (score: 0.95)
  [1] GET /persons/collection (score: 0.82)

Enter your choice (0-1): 0
✓ Selected option 0

Mapping saved to: ~/.toolkit_engine/pipedrive_mapping.json
```

**Alternative**: Auto-select best endpoints (non-interactive):
```bash
python3 auto_select_pipedrive.py
```

**4. Get API Credentials**

Get your Pipedrive API token:
1. Sign up at [pipedrive.com](https://www.pipedrive.com) (free trial)
2. Go to **Settings** → **Personal preferences** → **API**
3. Copy your **Personal API token**

**5. Test the Integration**

```bash
export PIPEDRIVE_API_TOKEN=your_token_here
toolkit-engine demo-full --id pipedrive
```

**Output:**
```
Starting demo for 'pipedrive'...

Step 1: Loading product definition...
✓ Loaded: Pipedrive CRM
  Type: crm
  Auth: api_key
  Base URL: https://api.pipedrive.com/v1

Step 2: Checking for capabilities...
✓ Capabilities file exists

Step 3: Checking for endpoint mapping...
✓ Mapping file exists

Step 4: Generating CRM client...
✓ Client created successfully

Step 5: Demonstrating API calls...

Fetching contacts...
✓ Retrieved 2 contacts
  Sample: ID=1, Name=Benjamin Leon, Email=benjamin.leon@gmail.com

✓ get_contact() working

==================================================
✓ Demo completed successfully!
==================================================

The Toolkit Integration Engine is working correctly.
You can now use this client in your applications:

  from toolkit_engine.generator import generate_integration

  client = generate_integration('pipedrive', credentials)
  contacts = client.list_contacts()
  client.close()
```

**6. Use in Your Application**

```python
from toolkit_engine.generator import generate_integration

# Initialize client with credentials
credentials = {"api_token": "your_pipedrive_token"}
client = generate_integration("pipedrive", credentials)

try:
    # List all contacts
    contacts = client.list_contacts()
    print(f"Found {len(contacts)} contacts")

    for contact in contacts[:5]:  # First 5
        print(f"  - {contact['name']}: {contact.get('email')}")

    # Get a specific contact
    if contacts:
        contact_id = contacts[0]["id"]
        contact_detail = client.get_contact(str(contact_id))
        print(f"\nContact details: {contact_detail['name']}")

    # Create a new contact
    new_contact = client.create_contact({
        "name": "Jane Doe",
        "email": [{"value": "jane@example.com", "primary": True}],
        "phone": [{"value": "+1234567890", "primary": True}]
    })
    print(f"Created contact: {new_contact['id']}")

    # Update a contact
    updated = client.update_contact(str(contact_id), {
        "job_title": "Senior Developer"
    })
    print(f"Updated contact: {updated['id']}")

finally:
    # Always close the HTTP client
    client.close()
```

**Using Context Manager** (automatic cleanup):
```python
from toolkit_engine.generator import generate_integration

credentials = {"api_token": "your_token"}

with generate_integration("pipedrive", credentials) as client:
    contacts = client.list_contacts()
    for contact in contacts:
        print(contact['name'])
    # client.close() called automatically
```

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer (main.py)                      │
│  register | list | discover | select | demo-full           │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   Registry   │    │  Product Adapter │    │   Generator  │
│              │    │                  │    │              │
│ - register   │    │ - discover_spec  │    │ - generate_  │
│ - get        │    │ - extract_caps   │    │   integration│
│ - list       │    │ - build_auth     │    │              │
└──────────────┘    └──────────────────┘    └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Config Store (JSON Files)                        │
│  - Product definitions                                       │
│  - Discovered capabilities                                   │
│  - Endpoint mappings                                         │
│                                                              │
│  Location: ~/.toolkit_engine/{product_id}_{type}.json      │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Patterns

- **Adapter Pattern**: Product-specific logic isolated in adapters
- **Registry Pattern**: In-memory cache with disk persistence
- **Builder Pattern**: `generate_integration()` assembles components
- **Context Manager**: Automatic resource cleanup
- **Strategy Pattern**: Pluggable scoring algorithms

### Data Flow

```
1. Register → Store product metadata
2. Discover → Fetch OpenAPI spec → Extract capabilities → Score & rank
3. Select → Detect ambiguities → User chooses → Save mapping
4. Generate → Load components → Create client → Ready to use
5. Use → HTTP requests with auth & retry → Real API data
```

## Configuration Storage

Files are stored in `~/.toolkit_engine/` by default:

```
~/.toolkit_engine/
├── pipedrive_product.json       # Product definition
├── pipedrive_capabilities.json  # Discovered API capabilities
└── pipedrive_mapping.json       # Selected endpoint mapping
```

Override location:
```bash
export TOOLKIT_ENGINE_HOME=/custom/path
```

## CLI Reference

### Commands

**`register`** - Register a new product
```bash
toolkit-engine register \
  --id PRODUCT_ID \
  --name "Product Name" \
  --type {crm|accounting} \
  --base-url "https://api.example.com" \
  --auth {api_key|oauth2}
```

**`list`** - List all registered products
```bash
toolkit-engine list
```

**`discover`** - Discover API capabilities
```bash
toolkit-engine discover --id PRODUCT_ID [--verbose]
```

**`select`** - Select endpoints interactively
```bash
toolkit-engine select --id PRODUCT_ID
```

**`demo-full`** - Run complete end-to-end demo
```bash
toolkit-engine demo-full --id PRODUCT_ID [--token TOKEN]

# Token can also be via environment variable:
export PRODUCT_ID_API_TOKEN=token
toolkit-engine demo-full --id PRODUCT_ID
```

## API Reference

### Generated Client Methods

Every generated client provides these methods:

**Contacts:**
- `list_contacts(filters=None) -> list[dict]`
- `get_contact(contact_id: str) -> dict`
- `create_contact(payload: dict) -> dict`
- `update_contact(contact_id: str, payload: dict) -> dict`

**Organisations:**
- `list_organisations(filters=None) -> list[dict]`
- `get_organisation(org_id: str) -> dict`
- `create_organisation(payload: dict) -> dict`
- `update_organisation(org_id: str, payload: dict) -> dict`

**Context Manager:**
- `__enter__()` - Initialize
- `__exit__()` - Cleanup
- `close()` - Manual cleanup

## Testing

**Run all tests:**
```bash
pytest  # 146 tests, ~0.3s
```

**Run with verbose output:**
```bash
pytest -v
```

**Run with coverage:**
```bash
pytest --cov=toolkit_engine --cov-report=term-missing
```

**Run specific test file:**
```bash
pytest tests/test_end_to_end.py -v
```

**Test Breakdown:**
- Core tests: 64 tests (models, registry, config, discovery, adapters)
- Selection tests: 33 tests (scoring, ambiguity detection, CLI)
- Generator tests: 42 tests (HTTP client, builder, CRUD operations)
- Integration tests: 7 tests (end-to-end workflow)

## Extending the System

### Overview

The Toolkit Integration Engine is designed for easy extension. Adding a new CRM requires **one adapter file** that implements three core methods. The registry, discovery, selection, and client generation work automatically.

### Simple guide: add any CRM

Use these plain-language steps for any CRM, no matter the vendor:

1. **Learn the API.** Find the public OpenAPI/Swagger file or a reliable description of the CRM endpoints. Note the paths for contacts, companies, deals, etc., as well as the auth style (API key, OAuth, custom header).
2. **Create an adapter file.** Copy `toolkit_engine/products/example.py` or another adapter, rename it (for example `yourcrm.py`), and update the `product_id` plus helper logic. Keep the three required methods:
   - `discover_spec()` downloads or loads the spec.
   - `extract_capabilities()` loops through paths/methods and maps them to standard entities and CRUD actions.
   - `build_auth_headers()` checks the expected credentials and returns headers (or an empty dict if auth is handled elsewhere).
3. **Detect entities and actions.** Inside the adapter, write small helper functions that translate product-specific paths into common names (e.g., `/people` → `contacts`). Decide when a path represents list/get/create/update/delete by inspecting the HTTP method and whether the path contains an ID parameter.
4. **Handle authentication quirks.** If the CRM wants OAuth tokens plus an instance URL, return the correct header and store extra metadata on the product definition so the generic client can assemble requests correctly.
5. **Wire up discovery.** Add the adapter to `toolkit_engine/core/discovery.py` so `get_adapter_for_product()` can return it. This is usually a single entry in a dictionary or if/elif chain.
6. **Register and test via CLI.** Run:
   ```bash
   toolkit-engine register --id yourcrm --name "Your CRM" --type crm \
     --base-url "https://api.yourcrm.com" --auth oauth2
   toolkit-engine discover --id yourcrm
   toolkit-engine select --id yourcrm
   toolkit-engine demo-full --id yourcrm
   ```
   Supply real credentials for the new product and confirm `list_contacts()` or similar methods work.
7. **Document what changed.** Update README/design notes with any product-specific hints (e.g., “`/Accounts` should be mapped to organisations”). Future maintainers can then follow the same flow for the next CRM.

**Architecture for Extension:**

```
Your New Adapter
       ↓
   discover_spec()        → Fetch OpenAPI/API spec from product
       ↓
extract_capabilities()    → Parse spec, identify useful endpoints
       ↓
build_auth_headers()      → Handle product-specific authentication
       ↓
   [System handles the rest automatically]
```

### Step-by-Step: Adding a New CRM

#### Step 1: Create Adapter File

Create `toolkit_engine/products/{product_name}.py` implementing `ProductAdapter`:

```python
"""Product adapter for YourCRM."""

import logging
from typing import Any
import httpx

from toolkit_engine.core.models import Capability, ConfigError
from .base import ProductAdapter

logger = logging.getLogger(__name__)

# Define spec URL for your product
SPEC_URL = "https://api.yourcrm.com/v1/openapi.json"


class DiscoveryError(Exception):
    """Raised when API specification discovery fails."""
    pass


class YourCRMAdapter(ProductAdapter):
    """Adapter for YourCRM integration."""

    @property
    def product_id(self) -> str:
        """Return product identifier (must match registration ID)."""
        return "yourcrm"

    def discover_spec(self) -> dict:
        """
        Fetch OpenAPI specification from product's API.

        Returns:
            API specification as dictionary

        Raises:
            DiscoveryError: If spec retrieval fails
        """
        try:
            logger.info(f"Discovering YourCRM API spec from {SPEC_URL}")
            response = httpx.get(SPEC_URL, timeout=15.0)
            response.raise_for_status()

            spec = response.json()
            logger.info("Successfully retrieved YourCRM API spec")
            return spec

        except httpx.HTTPStatusError as e:
            raise DiscoveryError(
                f"Failed to retrieve spec: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise DiscoveryError(f"Failed to connect to API: {e}")
        except Exception as e:
            raise DiscoveryError(f"Unexpected error: {e}")

    def extract_capabilities(self, spec: dict) -> list[Capability]:
        """
        Extract useful capabilities from API specification.

        Parse the OpenAPI spec and create Capability objects for
        CRM endpoints (contacts, companies, deals, etc.).

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            List of Capability objects
        """
        capabilities = []
        paths = spec.get("paths", {})

        logger.debug(f"Found {len(paths)} paths in spec")

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue

            # Detect entity from path
            entity = self._detect_entity(path)
            if not entity:
                continue

            # Process each HTTP method
            for method, details in methods.items():
                if method.lower() in ["get", "post", "put", "delete"]:
                    action = self._detect_action(method, path)
                    if not action:
                        continue

                    capability = Capability(
                        product_id=self.product_def.product_id,
                        entity_name=entity,
                        action=action,
                        http_method=method.upper(),
                        path=path,
                        request_schema=None,  # Optional: extract from spec
                        response_schema=None, # Optional: extract from spec
                        score=None,           # Scoring happens later
                    )

                    capabilities.append(capability)
                    logger.debug(
                        f"Extracted: {entity}.{action} {method.upper()} {path}"
                    )

        logger.info(f"Extracted {len(capabilities)} capabilities")
        return capabilities

    def build_auth_headers(self, credentials: dict) -> dict:
        """
        Build authentication headers for API requests.

        Different products use different auth patterns:
        - OAuth2 Bearer token (HubSpot): Header-based
        - API Key in query params (Pipedrive): Return empty dict
        - Custom API key header (others): Custom header

        Args:
            credentials: Dictionary with auth credentials

        Returns:
            Dictionary of HTTP headers (or empty dict for query param auth)

        Raises:
            ConfigError: If credentials are invalid
        """
        # Example 1: OAuth2 Bearer Token (Header-based)
        if "access_token" not in credentials:
            raise ConfigError(
                "YourCRM credentials must include 'access_token' field"
            )
        return {"Authorization": f"Bearer {credentials['access_token']}"}

        # Example 2: API Key in Query Parameters
        # If your CRM uses query params (like Pipedrive), return empty dict:
        # if "api_token" not in credentials:
        #     raise ConfigError("Credentials must include 'api_token' field")
        # return {}  # Token added to query params by CRM client

        # Example 3: Custom API Key Header
        # if "api_key" not in credentials:
        #     raise ConfigError("Credentials must include 'api_key' field")
        # return {"X-API-Key": credentials["api_key"]}

    # Helper methods for entity/action detection

    def _detect_entity(self, path: str) -> str | None:
        """
        Detect entity type from API path.

        Map product-specific paths to standard entity names.

        Examples:
            /contacts → contacts
            /persons → contacts (Pipedrive)
            /companies → organisations
            /deals → deals
        """
        path_lower = path.lower()

        if "/contacts" in path_lower or "/persons" in path_lower:
            return "contacts"
        elif "/companies" in path_lower or "/organizations" in path_lower:
            return "organisations"
        elif "/deals" in path_lower or "/opportunities" in path_lower:
            return "deals"
        elif "/activities" in path_lower:
            return "activities"

        return None

    def _detect_action(self, http_method: str, path: str) -> str | None:
        """
        Detect CRUD action from HTTP method and path.

        Standard patterns:
            GET /resource → list
            GET /resource/{id} → get
            POST /resource → create
            PUT /resource/{id} → update
            DELETE /resource/{id} → delete
        """
        method = http_method.upper()

        # Check for ID parameter (varies by product)
        has_id = (
            "{id}" in path.lower() or
            "{contactId}" in path or
            "/:id" in path
        )

        if method == "GET":
            return "get" if has_id else "list"
        elif method == "POST" and not has_id:
            return "create"
        elif method == "PUT" and has_id:
            return "update"
        elif method == "DELETE" and has_id:
            return "delete"

        return None
```

#### Step 2: Register Adapter

Add your adapter to `toolkit_engine/core/discovery.py`:

```python
from toolkit_engine.products.yourcrm import YourCRMAdapter

def get_adapter_for_product(product: ProductDefinition) -> ProductAdapter:
    product_id = product.product_id.lower()

    if product_id == "hubspot":
        return HubSpotAdapter(product)
    elif product_id == "pipedrive":
        return PipedriveAdapter(product)
    elif product_id == "yourcrm":  # Add your adapter
        return YourCRMAdapter(product)
    else:
        raise AdapterNotFoundError(
            f"No adapter available for product '{product.product_id}'. "
            f"Supported products: hubspot, pipedrive, yourcrm"  # Update list
        )
```

#### Step 3: Use Your Adapter

```bash
# Register product
toolkit-engine register \
  --id yourcrm \
  --name "YourCRM" \
  --type crm \
  --base-url "https://api.yourcrm.com/v1" \
  --auth oauth2

# Discover capabilities
toolkit-engine discover --id yourcrm

# Select endpoints (resolve ambiguities)
toolkit-engine select --id yourcrm

# Test with real API
export YOURCRM_ACCESS_TOKEN=your_token_here
toolkit-engine demo-full --id yourcrm
```

**That's it!** The system automatically handles:
- ✅ Discovery and capability extraction
- ✅ Scoring and ranking endpoints
- ✅ Ambiguity detection and resolution
- ✅ Dynamic client generation
- ✅ HTTP requests with authentication and retry logic

### Key Implementation Notes

#### Authentication Patterns

**OAuth2 Bearer Token (HubSpot, Salesforce)**
```python
def build_auth_headers(self, credentials: dict) -> dict:
    if "access_token" not in credentials:
        raise ConfigError("Missing 'access_token' field")
    return {"Authorization": f"Bearer {credentials['access_token']}"}
```

**API Key in Query Parameters (Pipedrive)**
```python
def build_auth_headers(self, credentials: dict) -> dict:
    if "api_token" not in credentials:
        raise ConfigError("Missing 'api_token' field")
    return {}  # Token added to query params by CRM client automatically
```

**Custom API Key Header (Others)**
```python
def build_auth_headers(self, credentials: dict) -> dict:
    if "api_key" not in credentials:
        raise ConfigError("Missing 'api_key' field")
    return {"X-API-Key": credentials["api_key"]}
```

#### Entity Mapping

Map product-specific terminology to standard names:

| Product Path | Standard Entity |
|-------------|----------------|
| `/contacts` | `contacts` |
| `/persons` (Pipedrive) | `contacts` |
| `/companies` | `organisations` |
| `/organizations` | `organisations` |
| `/deals` | `deals` |
| `/opportunities` (Salesforce) | `deals` |

#### Action Detection

Standard CRUD patterns:

| Method | Path Pattern | Action |
|--------|-------------|--------|
| GET | `/resource` | `list` |
| GET | `/resource/{id}` | `get` |
| POST | `/resource` | `create` |
| PUT | `/resource/{id}` | `update` |
| DELETE | `/resource/{id}` | `delete` |

**Note**: ID parameter patterns vary by product: `{id}`, `{contactId}`, `/:id`

#### Error Handling

Always wrap external calls in try-except:

```python
def discover_spec(self) -> dict:
    try:
        response = httpx.get(SPEC_URL, timeout=15.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise DiscoveryError(f"HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        raise DiscoveryError(f"Connection failed: {e}")
    except Exception as e:
        raise DiscoveryError(f"Unexpected error: {e}")
```

### Testing Your Adapter

#### Unit Tests

Create `tests/test_yourcrm_adapter.py`:

```python
import pytest
from toolkit_engine.products.yourcrm import YourCRMAdapter
from toolkit_engine.core.models import ProductDefinition, ProductType, AuthMethod

@pytest.fixture
def yourcrm_product():
    return ProductDefinition(
        product_id="yourcrm",
        name="YourCRM",
        type=ProductType.CRM,
        base_url="https://api.yourcrm.com/v1",
        auth_method=AuthMethod.OAUTH2
    )

def test_product_id(yourcrm_product):
    adapter = YourCRMAdapter(yourcrm_product)
    assert adapter.product_id == "yourcrm"

def test_build_auth_headers_success(yourcrm_product):
    adapter = YourCRMAdapter(yourcrm_product)
    credentials = {"access_token": "test_token_123"}

    headers = adapter.build_auth_headers(credentials)

    assert headers == {"Authorization": "Bearer test_token_123"}

def test_build_auth_headers_missing_token(yourcrm_product):
    adapter = YourCRMAdapter(yourcrm_product)
    credentials = {}  # Missing access_token

    with pytest.raises(ConfigError) as exc:
        adapter.build_auth_headers(credentials)

    assert "access_token" in str(exc.value)
```

#### Integration Tests

Test with real API:

```bash
# Set up test account
export YOURCRM_ACCESS_TOKEN=test_token

# Run full workflow
pytest tests/test_end_to_end.py -v -k yourcrm
```

### Extending to Accounting Products

The same pattern applies to accounting products. Key differences:

**Entity Types:**
- `invoices` instead of `contacts`
- `transactions`, `payments`, `accounts`
- `customers`, `suppliers`

**Example: Xero Adapter Structure**

```python
class XeroAdapter(ProductAdapter):
    @property
    def product_id(self) -> str:
        return "xero"

    def _detect_entity(self, path: str) -> str | None:
        """Xero-specific entity detection."""
        path_lower = path.lower()

        if "/invoices" in path_lower:
            return "invoices"
        elif "/contacts" in path_lower:
            return "customers"  # Xero calls them contacts
        elif "/payments" in path_lower:
            return "payments"
        elif "/accounts" in path_lower:
            return "accounts"

        return None
```

See [design_note.md](design_note.md) for:
- Full Xero accounting adapter example
- Handling invoice-specific operations
- Multi-tenant authentication patterns
- Accounting-specific data structures

### Common Pitfalls

1. **ID Parameter Variations**: Different APIs use `{id}`, `{contactId}`, `/:id` - check all patterns
2. **Auth Field Names**: Match credential field names to product expectations (`access_token` vs `api_token`)
3. **Entity Name Mapping**: Map product terminology to standard names consistently
4. **Pagination**: Some APIs paginate differently - handle in `extract_capabilities()`
5. **Rate Limiting**: Consider adding retry logic if product has strict limits

## Troubleshooting

### "Product not found" error
```bash
# Solution: Register the product first
toolkit-engine register --id PRODUCT_ID --name "Name" --type crm \
  --base-url "https://api.example.com" --auth api_key
```

### "No mapping found" error
```bash
# Solution: Run selection to create mapping
toolkit-engine select --id PRODUCT_ID

# Or use auto-select (for Pipedrive)
python3 auto_select_pipedrive.py
```

### "Capabilities file not found" error
```bash
# Solution: Run discovery first
toolkit-engine discover --id PRODUCT_ID
```

### 401 Unauthorized API errors
- Verify your access token is valid and not expired
- For Pipedrive: Check token in Settings → Personal preferences → API
- For HubSpot: Ensure Private App has correct scopes enabled
- Check token format matches product requirements

### 404 Not Found API errors
- Verify the API base URL is correct
- Some products have region-specific URLs
- Check product's API documentation for correct base URL

## Getting API Credentials

### Pipedrive (Easiest)

1. Sign up at [pipedrive.com](https://www.pipedrive.com) (free trial)
2. Settings → Personal preferences → API
3. Copy your **Personal API token**
4. Use it: `export PIPEDRIVE_API_TOKEN=token`

**Token format**: Plain string (never expires unless revoked)

### HubSpot

1. Create account at [hubspot.com](https://www.hubspot.com)
2. Settings → Integrations → Private Apps
3. Create new app with scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.companies.read`
   - `crm.objects.companies.write`
4. Copy access token
5. Use it: `export HUBSPOT_ACCESS_TOKEN=token`

**Token format**: Starts with `pat-` (permanent unless revoked)

## Project Structure

```
projektrising/
├── toolkit_engine/
│   ├── core/
│   │   ├── models.py           # Data structures (ProductDefinition, Capability)
│   │   ├── registry.py         # Product registration & caching
│   │   ├── config_store.py     # JSON file persistence
│   │   ├── discovery.py        # Discovery orchestration
│   │   └── selection.py        # Scoring & ambiguity detection
│   ├── products/
│   │   ├── base.py            # Abstract ProductAdapter
│   │   ├── hubspot.py         # HubSpot implementation
│   │   └── pipedrive.py       # Pipedrive implementation
│   ├── generator/
│   │   ├── crm_client.py      # Generic HTTP client with CRUD
│   │   └── builder.py         # generate_integration()
│   ├── cli/
│   │   └── main.py            # CLI commands
│   └── demo.py                # End-to-end demo
├── tests/
│   ├── test_models.py
│   ├── test_registry.py
│   ├── test_config_store.py
│   ├── test_discovery.py
│   ├── test_hubspot_adapter.py
│   ├── test_selection.py
│   ├── test_cli_selection.py
│   ├── test_crm_client.py
│   ├── test_builder.py
│   └── test_end_to_end.py
├── README.md                  # This file
├── design_note.md             # Architecture deep-dive
├── ALTERNATIVE_CRMS.md        # CRM comparison guide
└── pyproject.toml            # Project configuration
```

## Requirements

- **Python**: 3.10 or higher
- **Core dependency**: httpx (HTTP client)
- **Dev dependencies**: pytest, pytest-mock (testing)

Install all dependencies:
```bash
pip install -e ".[dev]"
```

## Features

### What Makes This Special

1. **Automatic Discovery** - Fetches and parses OpenAPI specs
2. **Intelligent Ranking** - Scores endpoints by usefulness
3. **Ambiguity Resolution** - Interactive selection when needed
4. **Runtime Generation** - No code generation, dynamic client creation
5. **Multi-Product Support** - Same interface works for HubSpot, Pipedrive, etc.
6. **Production-Ready** - Retry logic, error handling, authentication, tests

### Key Benefits

- **Add CRM in 20 minutes** - Just write adapter, rest is automatic
- **Consistent API** - Same `list_contacts()` for all CRMs
- **Extensible** - Clear patterns for accounting products
- **Well-Tested** - 146 tests with mocks
- **Real-World Proven** - Successfully tested with live Pipedrive API


