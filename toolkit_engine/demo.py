"""
Stage 5: End-to-End Demo

Provides a complete workflow demonstration that ties together
all stages of the Toolkit Integration Engine.
"""

import logging
from typing import Any

from .core import (
    get_product,
    load_product_definition,
    discover_capabilities,
    get_base_dir,
    ProductNotFoundError,
    ConfigError,
)
from .generator import generate_integration, APIError

logger = logging.getLogger(__name__)

# Suppress httpx INFO logs for cleaner output
logging.getLogger("httpx").setLevel(logging.WARNING)


def run_demo(product_id: str, credentials: dict[str, Any]) -> None:
    """
    Run end-to-end demo of the Toolkit Integration Engine.

    This function demonstrates the complete workflow:
    1. Load product definition
    2. Ensure capabilities are discovered
    3. Ensure mapping exists
    4. Generate integration client
    5. Demonstrate API calls

    Args:
        product_id: Product identifier (e.g., 'hubspot')
        credentials: Authentication credentials dict

    Raises:
        ProductNotFoundError: If product not registered
        ConfigError: If required files are missing
        APIError: If API calls fail
    """
    print(f"Starting demo for '{product_id}'...")
    print()

    # Step 1: Load product definition
    print("Step 1: Loading product definition...")
    try:
        # Try in-memory registry first
        try:
            product_def = get_product(product_id)
        except ProductNotFoundError:
            # Fall back to loading from disk
            product_def = load_product_definition(product_id)

        print(f"✓ Loaded: {product_def.name}")
        print(f"  Type: {product_def.type.value}")
        print(f"  Auth: {product_def.auth_method.value}")
        print(f"  Base URL: {product_def.api_base_url}")
        print()

    except (ProductNotFoundError, ConfigError) as e:
        print(f"✗ Error: {e}")
        print()
        print("Please register the product first:")
        print(f"  toolkit-engine register --id {product_id} --name 'Product Name' --type crm --base-url https://api.example.com --auth oauth2")
        raise

    # Step 2: Ensure capabilities file exists
    print("Step 2: Checking for capabilities...")
    base_dir = get_base_dir()
    capabilities_file = base_dir / f"{product_id}_capabilities.json"

    if not capabilities_file.exists():
        print(f"✗ Capabilities file not found: {capabilities_file}")
        print("  Running discovery automatically...")
        print()

        try:
            capabilities = discover_capabilities(product_id)
            print(f"✓ Discovered {len(capabilities)} capabilities")
            print()
        except Exception as e:
            print(f"✗ Discovery failed: {e}")
            print()
            print("You may need to create a mapping file manually.")
            print(f"See documentation for mapping format.")
            raise ConfigError(f"Could not discover capabilities: {e}")
    else:
        print(f"✓ Capabilities file exists")
        print()

    # Step 3: Ensure mapping file exists
    print("Step 3: Checking for endpoint mapping...")
    mapping_file = base_dir / f"{product_id}_mapping.json"

    if not mapping_file.exists():
        print(f"✗ Mapping file not found: {mapping_file}")
        print()
        print("Please run the selection command to choose endpoints:")
        print(f"  toolkit-engine select --id {product_id}")
        print()
        raise ConfigError(
            f"No mapping found for '{product_id}'. "
            f"Run 'toolkit-engine select --id {product_id}' to create it."
        )

    print(f"✓ Mapping file exists")
    print()

    # Step 4: Generate integration client
    print("Step 4: Generating CRM client...")
    try:
        client = generate_integration(product_id, credentials)
        print("✓ Client created successfully")
        print()
    except Exception as e:
        print(f"✗ Client generation failed: {e}")
        raise

    # Step 5: Demonstrate API calls
    print("Step 5: Demonstrating API calls...")
    print()

    try:
        # List contacts
        print("Fetching contacts...")
        contacts = client.list_contacts()

        print(f"✓ Retrieved {len(contacts)} contacts")

        if contacts:
            first_contact = contacts[0]

            # Try to extract ID
            contact_id = (
                first_contact.get("id")
                or first_contact.get("vid")
                or first_contact.get("contact_id")
                or "unknown"
            )

            # Try to extract name and email
            name = None
            email = None

            # Check if data is in properties (HubSpot style)
            if "properties" in first_contact:
                props = first_contact["properties"]
                firstname = props.get("firstname") or props.get("first_name") or props.get("firstName")
                lastname = props.get("lastname") or props.get("last_name") or props.get("lastName")
                if firstname or lastname:
                    name = f"{firstname or ''} {lastname or ''}".strip()
                email = props.get("email") or props.get("e_mail")
            else:
                # Direct fields (Pipedrive style)
                name = first_contact.get("name")
                email_data = first_contact.get("email") or first_contact.get("primary_email")
                # Pipedrive returns email as list of dicts, extract value
                if isinstance(email_data, list) and email_data:
                    email = email_data[0].get("value") if isinstance(email_data[0], dict) else email_data[0]
                else:
                    email = email_data

            # Print sample contact info
            print(f"  Sample: ID={contact_id}", end="")
            if name:
                print(f", Name={name}", end="")
            if email:
                print(f", Email={email}", end="")
            print()

        print()

        # Test get_contact
        if contacts and len(contacts) > 0:
            try:
                contact_id = (
                    contacts[0].get("id")
                    or contacts[0].get("vid")
                    or contacts[0].get("contact_id")
                )

                if contact_id:
                    single_contact = client.get_contact(str(contact_id))
                    print(f"✓ get_contact() working")
                    print()
            except Exception:
                pass  # Silently skip if not available

    except APIError as e:
        print(f"✗ API Error: {e}")
        if e.status_code:
            print(f"  HTTP Status: {e.status_code}")

        print()
        print("Common issues:")
        print("  - Invalid or expired access token")
        print("  - Insufficient permissions (check scopes)")
        print("  - Rate limiting")
        raise

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise

    finally:
        # Clean up
        client.close()

    # Success!
    print("=" * 50)
    print("✓ Demo completed successfully!")
    print("=" * 50)
    print()
    print("The Toolkit Integration Engine is working correctly.")
    print("You can now use this client in your applications:")
    print()
    print("  from toolkit_engine.generator import generate_integration")
    print()
    print(f"  client = generate_integration('{product_id}', credentials)")
    print("  contacts = client.list_contacts()")
    print("  client.close()")
    print()
