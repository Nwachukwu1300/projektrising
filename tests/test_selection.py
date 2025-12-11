"""Tests for Stage 3: Capability selection and mapping."""

import pytest
from toolkit_engine.core.models import Capability
from toolkit_engine.core.selection import (
    score_capabilities,
    group_by_entity_and_action,
    detect_ambiguities,
    build_mapping,
    auto_select_best,
)


@pytest.fixture
def sample_capabilities():
    """Sample capabilities for testing."""
    return [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/crm/v3/objects/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="get",
            http_method="GET",
            path="/crm/v3/objects/contacts/{id}",
        ),
        Capability(
            product_id="test",
            entity_name="deals",
            action="create",
            http_method="POST",
            path="/crm/v3/objects/deals",
        ),
    ]


@pytest.fixture
def ambiguous_capabilities():
    """Capabilities with ambiguities for testing."""
    return [
        # Two list endpoints for contacts
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/crm/v3/objects/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="POST",
            path="/crm/v3/objects/contacts/search",
        ),
        # Single get endpoint
        Capability(
            product_id="test",
            entity_name="contacts",
            action="get",
            http_method="GET",
            path="/crm/v3/objects/contacts/{id}",
        ),
    ]


def test_score_capabilities_priority_entity(sample_capabilities):
    """Test that priority entities get higher scores."""
    scored = score_capabilities(sample_capabilities)

    # All our sample capabilities are priority entities
    for cap in scored:
        assert cap.score is not None
        assert cap.score > 0


def test_score_capabilities_priority_action():
    """Test that priority actions get higher scores."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/api/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="batch",
            http_method="POST",
            path="/api/contacts/batch",
        ),
    ]

    scored = score_capabilities(caps)

    # list is a priority action, batch is deprioritized
    list_score = next(c.score for c in scored if c.action == "list")
    batch_score = next(c.score for c in scored if c.action == "batch")

    assert list_score > batch_score


def test_score_capabilities_deprioritized_terms():
    """Test that paths with deprioritized terms get lower scores."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/crm/v3/objects/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="POST",
            path="/crm/v3/objects/contacts/batch",
        ),
    ]

    scored = score_capabilities(caps)

    # Regular path should score higher than batch path
    regular_score = next(c.score for c in scored if "batch" not in c.path)
    batch_score = next(c.score for c in scored if "batch" in c.path)

    assert regular_score > batch_score


def test_score_capabilities_shorter_paths():
    """Test that shorter paths get slightly higher scores."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/api/v3/crm/objects/contacts",
        ),
    ]

    scored = score_capabilities(caps)

    # Shorter path should have higher score
    short_score = next(c.score for c in scored if c.path == "/contacts")
    long_score = next(c.score for c in scored if "/objects/" in c.path)

    assert short_score > long_score


def test_score_capabilities_preserves_data(sample_capabilities):
    """Test that scoring preserves all other capability data."""
    scored = score_capabilities(sample_capabilities)

    for original, scored_cap in zip(sample_capabilities, scored):
        assert scored_cap.product_id == original.product_id
        assert scored_cap.entity_name == original.entity_name
        assert scored_cap.action == original.action
        assert scored_cap.http_method == original.http_method
        assert scored_cap.path == original.path


def test_group_by_entity_and_action(sample_capabilities):
    """Test grouping capabilities by entity and action."""
    groups = group_by_entity_and_action(sample_capabilities)

    assert "contacts" in groups
    assert "deals" in groups

    assert "list" in groups["contacts"]
    assert "get" in groups["contacts"]
    assert "create" in groups["deals"]

    assert len(groups["contacts"]["list"]) == 1
    assert len(groups["contacts"]["get"]) == 1
    assert len(groups["deals"]["create"]) == 1


def test_group_by_entity_and_action_structure():
    """Test the structure of grouped capabilities."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="POST",
            path="/contacts/search",
        ),
    ]

    groups = group_by_entity_and_action(caps)

    # Should have one entity
    assert len(groups) == 1
    assert "contacts" in groups

    # Should have one action under contacts
    assert len(groups["contacts"]) == 1
    assert "list" in groups["contacts"]

    # Should have both capabilities under list
    assert len(groups["contacts"]["list"]) == 2


def test_detect_ambiguities_no_ambiguity(sample_capabilities):
    """Test ambiguity detection with no ambiguous cases."""
    groups = group_by_entity_and_action(sample_capabilities)
    ambiguities = detect_ambiguities(groups)

    assert len(ambiguities) == 0


def test_detect_ambiguities_with_ambiguity(ambiguous_capabilities):
    """Test ambiguity detection with ambiguous cases."""
    groups = group_by_entity_and_action(ambiguous_capabilities)
    ambiguities = detect_ambiguities(groups)

    assert len(ambiguities) == 1

    ambiguity = ambiguities[0]
    assert ambiguity["entity_name"] == "contacts"
    assert ambiguity["action"] == "list"
    assert len(ambiguity["capabilities"]) == 2


def test_detect_ambiguities_structure():
    """Test structure of detected ambiguities."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="POST",
            path="/contacts/search",
        ),
        Capability(
            product_id="test",
            entity_name="deals",
            action="get",
            http_method="GET",
            path="/deals/{id}",
        ),
        Capability(
            product_id="test",
            entity_name="deals",
            action="get",
            http_method="POST",
            path="/deals/fetch",
        ),
    ]

    groups = group_by_entity_and_action(caps)
    ambiguities = detect_ambiguities(groups)

    # Should detect 2 ambiguous cases
    assert len(ambiguities) == 2

    # Check both entities are represented
    entities = {amb["entity_name"] for amb in ambiguities}
    assert entities == {"contacts", "deals"}


def test_build_mapping_no_selection(sample_capabilities):
    """Test building mapping without selections (defaults to index 0)."""
    groups = group_by_entity_and_action(sample_capabilities)
    mapping = build_mapping(groups, {})

    assert "contacts" in mapping
    assert "deals" in mapping

    assert "list" in mapping["contacts"]
    assert "get" in mapping["contacts"]
    assert "create" in mapping["deals"]

    # Check structure
    assert "http_method" in mapping["contacts"]["list"]
    assert "path" in mapping["contacts"]["list"]


def test_build_mapping_with_selection():
    """Test building mapping with user selections."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/contacts",
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="POST",
            path="/contacts/search",
        ),
    ]

    groups = group_by_entity_and_action(caps)

    # User selects index 1 (the POST endpoint)
    selections = {
        "contacts": {
            "list": 1
        }
    }

    mapping = build_mapping(groups, selections)

    assert mapping["contacts"]["list"]["http_method"] == "POST"
    assert mapping["contacts"]["list"]["path"] == "/contacts/search"


def test_build_mapping_format():
    """Test the exact format of the mapping output."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="get",
            http_method="GET",
            path="/crm/v3/objects/contacts/{contactId}",
        ),
    ]

    groups = group_by_entity_and_action(caps)
    mapping = build_mapping(groups, {})

    expected = {
        "contacts": {
            "get": {
                "http_method": "GET",
                "path": "/crm/v3/objects/contacts/{contactId}"
            }
        }
    }

    assert mapping == expected


def test_auto_select_best_single():
    """Test auto-selecting best from single capability."""
    cap = Capability(
        product_id="test",
        entity_name="contacts",
        action="list",
        http_method="GET",
        path="/contacts",
        score=10.0
    )

    best = auto_select_best([cap])
    assert best == cap


def test_auto_select_best_multiple():
    """Test auto-selecting best from multiple capabilities."""
    caps = [
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/contacts",
            score=5.0
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="POST",
            path="/contacts/search",
            score=15.0
        ),
        Capability(
            product_id="test",
            entity_name="contacts",
            action="list",
            http_method="GET",
            path="/api/contacts",
            score=10.0
        ),
    ]

    best = auto_select_best(caps)
    assert best.score == 15.0
    assert best.path == "/contacts/search"


def test_auto_select_best_empty_list():
    """Test auto-selecting from empty list raises error."""
    with pytest.raises(ValueError, match="Cannot select from empty list"):
        auto_select_best([])


def test_scoring_deterministic(sample_capabilities):
    """Test that scoring is deterministic."""
    scored1 = score_capabilities(sample_capabilities)
    scored2 = score_capabilities(sample_capabilities)

    for cap1, cap2 in zip(scored1, scored2):
        assert cap1.score == cap2.score


def test_grouping_deterministic(sample_capabilities):
    """Test that grouping is deterministic."""
    groups1 = group_by_entity_and_action(sample_capabilities)
    groups2 = group_by_entity_and_action(sample_capabilities)

    assert groups1.keys() == groups2.keys()

    for entity in groups1:
        assert groups1[entity].keys() == groups2[entity].keys()
        for action in groups1[entity]:
            assert len(groups1[entity][action]) == len(groups2[entity][action])
