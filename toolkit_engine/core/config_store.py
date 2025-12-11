"""Configuration and persistence for product definitions."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from .models import ProductDefinition, ConfigError

logger = logging.getLogger(__name__)


def get_base_dir() -> Path:
    """
    Get the base directory for storing configuration.

    The directory is determined by:
    1. Environment variable TOOLKIT_ENGINE_HOME if set
    2. Otherwise, ~/.toolkit_engine

    The directory is created if it does not exist.

    Returns:
        Path to the base directory
    """
    env_home = os.environ.get("TOOLKIT_ENGINE_HOME")
    if env_home:
        base_dir = Path(env_home)
    else:
        base_dir = Path.home() / ".toolkit_engine"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def product_config_path(product_id: str, suffix: str = "config") -> Path:
    """
    Get the path for a product's configuration file.

    Args:
        product_id: Internal key for the product
        suffix: File suffix (default: "config")

    Returns:
        Path to the configuration file
    """
    base_dir = get_base_dir()
    return base_dir / f"{product_id}_{suffix}.json"


def save_json(product_id: str, suffix: str, data: dict) -> Path:
    """
    Save a dictionary as JSON to a product configuration file.

    Args:
        product_id: Internal key for the product
        suffix: File suffix
        data: Dictionary to save

    Returns:
        Path to the saved file
    """
    path = product_config_path(product_id, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved JSON to {path}")
        return path
    except Exception as e:
        raise ConfigError(f"Failed to save JSON to {path}: {e}")


def load_json(product_id: str, suffix: str) -> dict:
    """
    Load a dictionary from a product configuration file.

    Args:
        product_id: Internal key for the product
        suffix: File suffix

    Returns:
        The loaded dictionary

    Raises:
        ConfigError: If the file does not exist or JSON is invalid
    """
    path = product_config_path(product_id, suffix)

    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        with open(path, "r") as f:
            data = json.load(f)
        logger.debug(f"Loaded JSON from {path}")
        return data
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {path}: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to load JSON from {path}: {e}")


def save_product_definition(product: ProductDefinition) -> Path:
    """
    Save a ProductDefinition to disk.

    Args:
        product: ProductDefinition to save

    Returns:
        Path to the saved file
    """
    data = product.to_dict()
    return save_json(product.product_id, "product", data)


def load_product_definition(product_id: str) -> ProductDefinition:
    """
    Load a ProductDefinition from disk.

    Args:
        product_id: Internal key for the product

    Returns:
        The loaded ProductDefinition

    Raises:
        ConfigError: If the file does not exist or is invalid
    """
    data = load_json(product_id, "product")
    try:
        return ProductDefinition.from_dict(data)
    except Exception as e:
        raise ConfigError(f"Failed to parse ProductDefinition for '{product_id}': {e}")
