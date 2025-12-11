"""
Stage 3: Capability Selection and Mapping

This module provides functionality for:
- Scoring capabilities based on relevance
- Grouping capabilities by entity and action
- Detecting ambiguities (multiple endpoints for same entity/action)
- Building clean mappings for code generation
"""

from typing import Any
from .models import Capability


# Scoring weights
PRIORITY_ENTITIES = {"contacts", "organisations", "deals", "companies"}
PRIORITY_ACTIONS = {"list", "get", "create", "update", "delete"}
DEPRIORITIZED_TERMS = {"batch", "search", "merge", "archive", "gdpr"}


def score_capabilities(capabilities: list[Capability]) -> list[Capability]:
    """
    Score each capability based on relevance.

    Scoring rules:
    - Priority entities (contacts, organisations, deals) get +10 points
    - Priority actions (list, get, create, update, delete) get +8 points
    - Paths containing deprioritized terms (batch, search, etc.) get -5 points
    - Shorter paths get slightly higher scores (inverse of path segment count)

    Args:
        capabilities: List of Capability objects to score

    Returns:
        List of Capability objects with updated score field
    """
    scored_capabilities = []

    for cap in capabilities:
        score = 0.0

        # Priority entity bonus
        entity_lower = cap.entity_name.lower() if cap.entity_name else ""
        if entity_lower in PRIORITY_ENTITIES:
            score += 10.0

        # Priority action bonus
        action_lower = cap.action.lower() if cap.action else ""
        if action_lower in PRIORITY_ACTIONS:
            score += 8.0

        # Deprioritize certain terms in path
        path_lower = cap.path.lower()
        for term in DEPRIORITIZED_TERMS:
            if term in path_lower:
                score -= 5.0

        # Shorter paths get slight bonus (inverse of segment count)
        # /crm/v3/contacts gets higher score than /crm/v3/objects/contacts/batch
        path_segments = len([s for s in cap.path.split("/") if s])
        if path_segments > 0:
            score += 10.0 / path_segments

        # Create new capability with score
        scored_cap = Capability(
            product_id=cap.product_id,
            entity_name=cap.entity_name,
            action=cap.action,
            http_method=cap.http_method,
            path=cap.path,
            request_schema=cap.request_schema,
            response_schema=cap.response_schema,
            score=score
        )
        scored_capabilities.append(scored_cap)

    return scored_capabilities


def group_by_entity_and_action(
    capabilities: list[Capability]
) -> dict[str, dict[str, list[Capability]]]:
    """
    Group capabilities by entity and action.

    Args:
        capabilities: List of Capability objects

    Returns:
        Nested dict: { entity_name: { action: [Capability, ...] } }

    Example:
        {
            "contacts": {
                "list": [Capability(...)],
                "get": [Capability(...), Capability(...)]
            },
            "deals": {
                "create": [Capability(...)]
            }
        }
    """
    groups: dict[str, dict[str, list[Capability]]] = {}

    for cap in capabilities:
        entity = cap.entity_name or "unknown"
        action = cap.action or "unknown"

        if entity not in groups:
            groups[entity] = {}

        if action not in groups[entity]:
            groups[entity][action] = []

        groups[entity][action].append(cap)

    return groups


def detect_ambiguities(
    groups: dict[str, dict[str, list[Capability]]]
) -> list[dict[str, Any]]:
    """
    Detect ambiguous cases where multiple capabilities exist for same entity/action.

    Args:
        groups: Grouped capabilities from group_by_entity_and_action()

    Returns:
        List of ambiguity items, each containing:
        - entity_name: str
        - action: str
        - capabilities: list[Capability]

    Example:
        [
            {
                "entity_name": "contacts",
                "action": "list",
                "capabilities": [Capability(...), Capability(...)]
            }
        ]
    """
    ambiguities = []

    for entity_name, actions_dict in groups.items():
        for action, caps in actions_dict.items():
            # Ambiguity exists if more than one capability for same entity/action
            if len(caps) > 1:
                ambiguities.append({
                    "entity_name": entity_name,
                    "action": action,
                    "capabilities": caps
                })

    return ambiguities


def build_mapping(
    groups: dict[str, dict[str, list[Capability]]],
    selections: dict[str, dict[str, int]]
) -> dict[str, dict[str, dict[str, str]]]:
    """
    Build final mapping from groups and user selections.

    Args:
        groups: Grouped capabilities
        selections: User selections in format {entity: {action: index}}
                   For ambiguous cases, index indicates which capability to use.
                   For non-ambiguous cases, index is 0.

    Returns:
        Clean mapping dict:
        {
            "contacts": {
                "list": {"http_method": "GET", "path": "/crm/v3/objects/contacts"},
                "get": {"http_method": "GET", "path": "/crm/v3/objects/contacts/{id}"}
            }
        }
    """
    mapping: dict[str, dict[str, dict[str, str]]] = {}

    for entity_name, actions_dict in groups.items():
        mapping[entity_name] = {}

        for action, caps in actions_dict.items():
            # Get user selection index (default to 0 if not specified)
            selected_index = 0
            if entity_name in selections and action in selections[entity_name]:
                selected_index = selections[entity_name][action]

            # Ensure index is valid
            if 0 <= selected_index < len(caps):
                selected_cap = caps[selected_index]
                mapping[entity_name][action] = {
                    "http_method": selected_cap.http_method,
                    "path": selected_cap.path
                }

    return mapping


def auto_select_best(
    capabilities: list[Capability]
) -> Capability:
    """
    Automatically select the best capability from a list based on score.

    Args:
        capabilities: List of capabilities (should already be scored)

    Returns:
        The capability with the highest score
    """
    if not capabilities:
        raise ValueError("Cannot select from empty list")

    # Sort by score descending, return highest
    sorted_caps = sorted(capabilities, key=lambda c: c.score or 0.0, reverse=True)
    return sorted_caps[0]
