"""Main CLI entry point for the Toolkit Integration Engine."""

import argparse
import logging
import sys
from pathlib import Path

from toolkit_engine.core import (
    ProductType,
    AuthMethod,
    register_product,
    get_product,
    list_products,
    save_product_definition,
    load_product_definition,
    get_base_dir,
    discover_capabilities,
    ProductNotFoundError,
    ConfigError,
    AdapterNotFoundError,
)
from toolkit_engine.core.selection import (
    score_capabilities,
    group_by_entity_and_action,
    detect_ambiguities,
    build_mapping,
)
from toolkit_engine.core.config_store import save_json, load_json
from toolkit_engine.products.hubspot import DiscoveryError
from toolkit_engine.generator import generate_integration, APIError
from toolkit_engine.demo import run_demo

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def cmd_register(args):
    """Handle the register command."""
    try:
        # Map string inputs to enums
        try:
            product_type = ProductType(args.type)
        except ValueError:
            print(f"Error: Invalid product type '{args.type}'. Must be 'crm' or 'accounting'.", file=sys.stderr)
            sys.exit(1)

        try:
            auth_method = AuthMethod(args.auth)
        except ValueError:
            print(f"Error: Invalid auth method '{args.auth}'. Must be 'api_key' or 'oauth2'.", file=sys.stderr)
            sys.exit(1)

        # Set default auth metadata based on auth method
        auth_metadata = {}
        if auth_method == AuthMethod.API_KEY:
            auth_metadata = {
                "api_key_header": "Authorization",
                "api_key_prefix": "Bearer ",
            }
        elif auth_method == AuthMethod.OAUTH2:
            auth_metadata = {
                "token_url": "",
                "scopes": [],
            }

        # Register the product
        product = register_product(
            product_id=args.id,
            product_type=product_type,
            name=args.name,
            api_base_url=args.base_url,
            auth_method=auth_method,
            auth_metadata=auth_metadata,
        )

        # Save to disk
        path = save_product_definition(product)
        print(f"Successfully registered product '{product.product_id}' ({product.name})")
        print(f"Configuration saved to: {path}")

    except Exception as e:
        print(f"Error registering product: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """Handle the list command."""
    try:
        # Load all saved product definitions from disk
        base_dir = get_base_dir()
        product_files = list(base_dir.glob("*_product.json"))

        if not product_files:
            print("No products registered.")
            return

        # Load each product and register it in memory
        for product_file in product_files:
            product_id = product_file.stem.replace("_product", "")
            try:
                product = load_product_definition(product_id)
                register_product(
                    product_id=product.product_id,
                    product_type=product.type,
                    name=product.name,
                    api_base_url=product.api_base_url,
                    auth_method=product.auth_method,
                    auth_metadata=product.auth_metadata,
                )
            except ConfigError as e:
                logger.warning(f"Failed to load product '{product_id}': {e}")
                continue

        # List all registered products
        products = list_products()

        if not products:
            print("No products registered.")
            return

        print(f"Registered products ({len(products)}):")
        print()
        for product in products:
            print(f"  ID:       {product.product_id}")
            print(f"  Name:     {product.name}")
            print(f"  Type:     {product.type.value}")
            print(f"  Base URL: {product.api_base_url}")
            print(f"  Auth:     {product.auth_method.value}")
            print()

    except Exception as e:
        print(f"Error listing products: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_discover(args):
    """Handle the discover command."""
    try:
        product_id = args.id

        # Load product definition from disk first
        try:
            product = load_product_definition(product_id)
            # Register it in memory
            register_product(
                product_id=product.product_id,
                product_type=product.type,
                name=product.name,
                api_base_url=product.api_base_url,
                auth_method=product.auth_method,
                auth_metadata=product.auth_metadata,
            )
            print(f"Loaded product: {product.name}")
        except ConfigError:
            print(f"Error: Product '{product_id}' not found. Register it first with 'toolkit-engine register'.", file=sys.stderr)
            sys.exit(1)

        # Discover capabilities
        print(f"Discovering API capabilities for '{product_id}'...")
        print()

        try:
            capabilities = discover_capabilities(product_id)
        except AdapterNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except DiscoveryError as e:
            print(f"Error during discovery: {e}", file=sys.stderr)
            sys.exit(1)

        # Print summary
        print(f"✓ Discovery complete!")
        print()
        print(f"Total capabilities discovered: {len(capabilities)}")
        print()

        # Group by entity
        entities = {}
        for cap in capabilities:
            if cap.entity_name not in entities:
                entities[cap.entity_name] = []
            entities[cap.entity_name].append(cap)

        # Print breakdown by entity
        print("Capabilities by entity:")
        print()
        for entity, caps in sorted(entities.items()):
            print(f"  {entity} ({len(caps)} capabilities)")
            # Show sample actions
            action_samples = {}
            for cap in caps:
                action_key = f"{cap.action}"
                if action_key not in action_samples:
                    action_samples[action_key] = cap

            for action, cap in sorted(action_samples.items()):
                print(f"    - {action:8s} {cap.http_method:6s} {cap.path}")

            print()

    except ProductNotFoundError:
        print(f"Error: Product '{args.id}' not found in registry.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during discovery: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def cmd_select(args):
    """Handle the select command - interactive capability selection."""
    try:
        product_id = args.id

        # Load capabilities from Stage 2 discovery file
        base_dir = get_base_dir()
        capabilities_file = base_dir / f"{product_id}_capabilities.json"

        if not capabilities_file.exists():
            print(f"Error: No capabilities found for '{product_id}'.", file=sys.stderr)
            print(f"Run 'toolkit-engine discover --id {product_id}' first.", file=sys.stderr)
            sys.exit(1)

        print(f"Loading capabilities for '{product_id}'...")
        with open(capabilities_file) as f:
            import json
            capabilities_data = json.load(f)

        # Convert dict data back to Capability objects
        from toolkit_engine.core.models import Capability
        capabilities = []

        # Handle the wrapper structure from discovery
        caps_list = capabilities_data.get("capabilities", capabilities_data)
        if not isinstance(caps_list, list):
            caps_list = [capabilities_data]

        for cap_dict in caps_list:
            capabilities.append(Capability(
                product_id=cap_dict.get("product_id", product_id),
                entity_name=cap_dict["entity_name"],
                action=cap_dict["action"],
                http_method=cap_dict["http_method"],
                path=cap_dict["path"],
                request_schema=cap_dict.get("request_schema"),
                response_schema=cap_dict.get("response_schema"),
                score=cap_dict.get("score"),
            ))

        print(f"Loaded {len(capabilities)} capabilities")
        print()

        # Step 1: Score capabilities
        print("Scoring capabilities...")
        scored_capabilities = score_capabilities(capabilities)
        print()

        # Step 2: Group by entity and action
        print("Grouping by entity and action...")
        groups = group_by_entity_and_action(scored_capabilities)
        print()

        # Step 3: Detect ambiguities
        ambiguities = detect_ambiguities(groups)

        if not ambiguities:
            print("No ambiguities detected. All entity/action pairs have single endpoints.")
            print()
        else:
            print(f"Found {len(ambiguities)} ambiguous cases requiring user selection:")
            print()

        # Step 4: Interactive user selection for ambiguities
        selections = {}

        for ambiguity in ambiguities:
            entity_name = ambiguity["entity_name"]
            action = ambiguity["action"]
            caps = ambiguity["capabilities"]

            # Sort by score descending for better UX
            caps_sorted = sorted(caps, key=lambda c: c.score or 0.0, reverse=True)

            print(f"Multiple endpoints found for {entity_name}.{action}:")
            print()

            for idx, cap in enumerate(caps_sorted):
                score_str = f"(score: {cap.score:.2f})" if cap.score else ""
                print(f"  [{idx}] {cap.http_method:6s} {cap.path} {score_str}")

            print()

            # Get user input
            while True:
                try:
                    choice = input(f"Select endpoint for {entity_name}.{action} [0-{len(caps_sorted)-1}]: ").strip()
                    selected_idx = int(choice)

                    if 0 <= selected_idx < len(caps_sorted):
                        # Store selection
                        if entity_name not in selections:
                            selections[entity_name] = {}
                        selections[entity_name][action] = selected_idx
                        print(f"✓ Selected option {selected_idx}")
                        print()
                        break
                    else:
                        print(f"Please enter a number between 0 and {len(caps_sorted)-1}")
                except ValueError:
                    print("Please enter a valid number")
                except KeyboardInterrupt:
                    print("\n\nSelection cancelled.")
                    sys.exit(1)

            # Update the capabilities list in the group to match sorted order
            # This ensures build_mapping uses the right indices
            groups[entity_name][action] = caps_sorted

        # Step 5: Build final mapping
        print("Building final mapping...")
        mapping = build_mapping(groups, selections)
        print()

        # Step 6: Save mapping to file
        mapping_file = base_dir / f"{product_id}_mapping.json"
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

        print(f"✓ Mapping saved to: {mapping_file}")
        print()

        # Print summary
        print("Final mapping summary:")
        print()
        for entity_name, actions in sorted(mapping.items()):
            print(f"  {entity_name}:")
            for action, endpoint in sorted(actions.items()):
                print(f"    {action:10s} {endpoint['http_method']:6s} {endpoint['path']}")
            print()

    except Exception as e:
        print(f"Error during selection: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def cmd_demo_client(args):
    """Handle the demo-client command - demonstrate CRM client usage."""
    try:
        product_id = args.id

        # Get credentials from command line argument
        # Format: "access_token=YOUR_TOKEN" or "api_key=YOUR_KEY"
        credentials = {}
        if args.credentials:
            for cred_pair in args.credentials.split(","):
                if "=" in cred_pair:
                    key, value = cred_pair.split("=", 1)
                    credentials[key.strip()] = value.strip()

        if not credentials:
            print("Error: No credentials provided.", file=sys.stderr)
            print("Use --credentials 'access_token=YOUR_TOKEN' or similar.", file=sys.stderr)
            sys.exit(1)

        print(f"Generating CRM client for '{product_id}'...")
        print()

        # Generate the integration
        try:
            client = generate_integration(product_id, credentials)
        except ProductNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except ConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"✓ Client created successfully!")
        print()

        # Demonstrate listing contacts
        print("Fetching contacts...")
        try:
            contacts = client.list_contacts()
            print(f"✓ Retrieved {len(contacts)} contacts")
            print()

            # Show first 3 contacts
            if contacts:
                print("Sample contacts:")
                for contact in contacts[:3]:
                    contact_id = contact.get("id") or contact.get("vid") or "unknown"
                    print(f"  - ID: {contact_id}")
                    # Try to get name or email
                    if "properties" in contact:
                        props = contact["properties"]
                        firstname = props.get("firstname") or props.get("first_name")
                        lastname = props.get("lastname") or props.get("last_name")
                        email = props.get("email")
                        if firstname or lastname:
                            print(f"    Name: {firstname} {lastname}".strip())
                        if email:
                            print(f"    Email: {email}")
                print()
        except APIError as e:
            print(f"Error listing contacts: {e}", file=sys.stderr)
            if e.status_code:
                print(f"HTTP Status: {e.status_code}", file=sys.stderr)

        # Clean up
        client.close()
        print("✓ Demo complete!")

    except Exception as e:
        print(f"Error during demo: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def cmd_demo_full(args):
    """Handle the demo-full command - complete end-to-end workflow."""
    try:
        product_id = args.id

        # Get credentials from --token flag or environment variable
        token = args.token
        if not token:
            # Try environment variable
            import os
            env_var = f"{product_id.upper()}_API_TOKEN"
            token = os.getenv(env_var)

            if not token:
                # Also try ACCESS_TOKEN variant
                env_var_alt = f"{product_id.upper()}_ACCESS_TOKEN"
                token = os.getenv(env_var_alt)
                env_var = env_var_alt

            if not token:
                print(f"Error: No token provided.", file=sys.stderr)
                print(f"Either use --token flag or set environment variable:", file=sys.stderr)
                print(f"  {product_id.upper()}_API_TOKEN or {product_id.upper()}_ACCESS_TOKEN", file=sys.stderr)
                sys.exit(1)

        # Build credentials dict based on product
        # Different products use different credential field names
        from toolkit_engine.core.config_store import get_base_dir, load_product_definition
        try:
            product_def = load_product_definition(product_id)
            auth_method = product_def.auth_method.value

            # Map auth methods to credential field names
            if auth_method == "api_key":
                credentials = {"api_token": token}  # Most API key products use "api_token"
            elif auth_method == "oauth2":
                credentials = {"access_token": token}  # OAuth2 uses "access_token"
            else:
                # Default to access_token
                credentials = {"access_token": token}
        except:
            # If we can't load product def, default to access_token
            credentials = {"access_token": token}

        # Run the demo
        run_demo(product_id, credentials)

    except (ProductNotFoundError, ConfigError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during demo: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="toolkit-engine",
        description="Toolkit Integration Engine CLI",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new product")
    register_parser.add_argument("--id", required=True, help="Product ID (e.g., 'hubspot')")
    register_parser.add_argument("--name", required=True, help="Human-readable name")
    register_parser.add_argument(
        "--type",
        required=True,
        choices=["crm", "accounting"],
        help="Product type",
    )
    register_parser.add_argument("--base-url", required=True, help="API base URL")
    register_parser.add_argument(
        "--auth",
        required=True,
        choices=["api_key", "oauth2"],
        help="Authentication method",
    )
    register_parser.set_defaults(func=cmd_register)

    # List command
    list_parser = subparsers.add_parser("list", help="List registered products")
    list_parser.set_defaults(func=cmd_list)

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover API capabilities for a product")
    discover_parser.add_argument("--id", required=True, help="Product ID (e.g., 'hubspot')")
    discover_parser.set_defaults(func=cmd_discover)

    # Select command
    select_parser = subparsers.add_parser("select", help="Interactively select endpoints from discovered capabilities")
    select_parser.add_argument("--id", required=True, help="Product ID (e.g., 'hubspot')")
    select_parser.set_defaults(func=cmd_select)

    # Demo-client command
    demo_parser = subparsers.add_parser("demo-client", help="Demonstrate CRM client usage")
    demo_parser.add_argument("--id", required=True, help="Product ID (e.g., 'hubspot')")
    demo_parser.add_argument("--credentials", required=True, help="Credentials in format 'key=value,key2=value2'")
    demo_parser.set_defaults(func=cmd_demo_client)

    # Demo-full command (Stage 5)
    demo_full_parser = subparsers.add_parser("demo-full", help="Run complete end-to-end workflow demo")
    demo_full_parser.add_argument("--id", required=True, help="Product ID (e.g., 'hubspot')")
    demo_full_parser.add_argument("--token", help="Access token (or set PRODUCT_ACCESS_TOKEN env var)")
    demo_full_parser.set_defaults(func=cmd_demo_full)

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
