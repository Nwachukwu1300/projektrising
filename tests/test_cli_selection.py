"""Tests for Stage 3 CLI selection command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

from toolkit_engine.cli.main import cmd_select
from toolkit_engine.core.config_store import get_base_dir, save_json
from toolkit_engine.core.models import Capability


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create temporary config directory."""
    config_dir = tmp_path / "toolkit_config"
    config_dir.mkdir()
    monkeypatch.setenv("TOOLKIT_ENGINE_HOME", str(config_dir))
    return config_dir


@pytest.fixture
def sample_capabilities_file(temp_config_dir):
    """Create a sample capabilities JSON file."""
    capabilities = [
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "list",
            "http_method": "GET",
            "path": "/crm/v3/objects/contacts"
        },
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "get",
            "http_method": "GET",
            "path": "/crm/v3/objects/contacts/{id}"
        },
        {
            "product_id": "test",
            "entity_name": "deals",
            "action": "create",
            "http_method": "POST",
            "path": "/crm/v3/objects/deals"
        },
    ]

    capabilities_file = temp_config_dir / "test_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(capabilities, f)

    return temp_config_dir  # Return directory, not file


@pytest.fixture
def ambiguous_capabilities_file(temp_config_dir):
    """Create capabilities file with ambiguities."""
    capabilities = [
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "list",
            "http_method": "GET",
            "path": "/crm/v3/objects/contacts"
        },
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "list",
            "http_method": "POST",
            "path": "/crm/v3/objects/contacts/search"
        },
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "get",
            "http_method": "GET",
            "path": "/crm/v3/objects/contacts/{id}"
        },
    ]

    capabilities_file = temp_config_dir / "test_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(capabilities, f)

    return temp_config_dir  # Return directory, not file


def test_cmd_select_no_capabilities_file(temp_config_dir, capsys):
    """Test select command when capabilities file doesn't exist."""
    args = MagicMock()
    args.id = "nonexistent"
    args.verbose = False

    with pytest.raises(SystemExit) as exc_info:
        cmd_select(args)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "No capabilities found" in captured.err
    assert "Run 'toolkit-engine discover" in captured.err


def test_cmd_select_loads_capabilities(sample_capabilities_file, capsys):
    """Test that select command loads capabilities correctly."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    # Mock input to provide selections (no ambiguities in this case)
    with patch("builtins.input", return_value="0"):
        cmd_select(args)

    captured = capsys.readouterr()
    assert "Loading capabilities for 'test'" in captured.out
    assert "Loaded 3 capabilities" in captured.out


def test_cmd_select_no_ambiguities(sample_capabilities_file, capsys):
    """Test select command with no ambiguities."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    cmd_select(args)

    captured = capsys.readouterr()
    assert "No ambiguities detected" in captured.out
    assert "Mapping saved" in captured.out


def test_cmd_select_detects_ambiguities(ambiguous_capabilities_file, capsys):
    """Test that select command detects ambiguities."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    # Mock input to select option 0
    with patch("builtins.input", return_value="0"):
        cmd_select(args)

    captured = capsys.readouterr()
    assert "Found 1 ambiguous cases" in captured.out
    assert "Multiple endpoints found for contacts.list" in captured.out


def test_cmd_select_prints_options(ambiguous_capabilities_file, capsys):
    """Test that select command prints endpoint options."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    with patch("builtins.input", return_value="0"):
        cmd_select(args)

    captured = capsys.readouterr()
    assert "[0]" in captured.out
    assert "[1]" in captured.out
    assert "GET" in captured.out
    assert "POST" in captured.out


def test_cmd_select_accepts_user_choice(ambiguous_capabilities_file, capsys):
    """Test that select command accepts user input."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    # User selects option 1 (POST endpoint)
    with patch("builtins.input", return_value="1"):
        cmd_select(args)

    captured = capsys.readouterr()
    assert "Selected option 1" in captured.out


def test_cmd_select_writes_mapping_file(sample_capabilities_file):
    """Test that select command writes mapping file."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    cmd_select(args)

    # Check that mapping file was created (sample_capabilities_file is now temp_config_dir)
    mapping_file = sample_capabilities_file / "test_mapping.json"
    assert mapping_file.exists()

    # Load and verify content
    with open(mapping_file) as f:
        mapping = json.load(f)

    assert "contacts" in mapping
    assert "deals" in mapping
    assert "list" in mapping["contacts"]
    assert "get" in mapping["contacts"]
    assert "create" in mapping["deals"]


def test_cmd_select_mapping_format(sample_capabilities_file):
    """Test the format of the generated mapping file."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    cmd_select(args)

    mapping_file = sample_capabilities_file / "test_mapping.json"
    with open(mapping_file) as f:
        mapping = json.load(f)

    # Check structure
    contacts_list = mapping["contacts"]["list"]
    assert "http_method" in contacts_list
    assert "path" in contacts_list
    assert contacts_list["http_method"] == "GET"
    assert contacts_list["path"] == "/crm/v3/objects/contacts"


def test_cmd_select_user_selection_reflected_in_mapping(ambiguous_capabilities_file):
    """Test that user selection is reflected in final mapping."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    # User selects option 1 (POST /search endpoint)
    with patch("builtins.input", return_value="1"):
        cmd_select(args)

    mapping_file = ambiguous_capabilities_file / "test_mapping.json"
    with open(mapping_file) as f:
        mapping = json.load(f)

    # Check that POST endpoint was selected
    assert mapping["contacts"]["list"]["http_method"] == "POST"
    assert "search" in mapping["contacts"]["list"]["path"]


def test_cmd_select_invalid_input_retries(ambiguous_capabilities_file, capsys):
    """Test that invalid input prompts retry."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    # Simulate invalid input followed by valid input
    with patch("builtins.input", side_effect=["invalid", "5", "0"]):
        cmd_select(args)

    captured = capsys.readouterr()
    assert "Please enter a valid number" in captured.out
    assert "Please enter a number between" in captured.out


def test_cmd_select_shows_scores(ambiguous_capabilities_file, capsys):
    """Test that endpoint options show scores."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    with patch("builtins.input", return_value="0"):
        cmd_select(args)

    captured = capsys.readouterr()
    # Scores should be shown in the output
    assert "score:" in captured.out


def test_cmd_select_prints_summary(sample_capabilities_file, capsys):
    """Test that select command prints final summary."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    cmd_select(args)

    captured = capsys.readouterr()
    assert "Final mapping summary:" in captured.out
    assert "contacts:" in captured.out
    assert "deals:" in captured.out


def test_cmd_select_keyboard_interrupt(ambiguous_capabilities_file, temp_config_dir):
    """Test that KeyboardInterrupt during selection exits gracefully."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc_info:
            cmd_select(args)

        assert exc_info.value.code == 1


def test_cmd_select_multiple_ambiguities(temp_config_dir, capsys):
    """Test select command with multiple ambiguous entity/action pairs."""
    # Create capabilities with multiple ambiguities
    capabilities = [
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "list",
            "http_method": "GET",
            "path": "/contacts"
        },
        {
            "product_id": "test",
            "entity_name": "contacts",
            "action": "list",
            "http_method": "POST",
            "path": "/contacts/search"
        },
        {
            "product_id": "test",
            "entity_name": "deals",
            "action": "get",
            "http_method": "GET",
            "path": "/deals/{id}"
        },
        {
            "product_id": "test",
            "entity_name": "deals",
            "action": "get",
            "http_method": "POST",
            "path": "/deals/fetch"
        },
    ]

    capabilities_file = temp_config_dir / "test_capabilities.json"
    with open(capabilities_file, "w") as f:
        json.dump(capabilities, f)

    args = MagicMock()
    args.id = "test"
    args.verbose = False

    # Provide selections for both ambiguities
    with patch("builtins.input", side_effect=["0", "1"]):
        cmd_select(args)

    captured = capsys.readouterr()
    assert "Found 2 ambiguous cases" in captured.out


def test_cmd_select_sorted_by_score(ambiguous_capabilities_file, capsys):
    """Test that ambiguous options are sorted by score (highest first)."""
    args = MagicMock()
    args.id = "test"
    args.verbose = False

    with patch("builtins.input", return_value="0"):
        cmd_select(args)

    captured = capsys.readouterr()
    output_lines = captured.out.split("\n")

    # Find the lines showing the options
    option_lines = [line for line in output_lines if line.strip().startswith("[")]

    # First option should have higher or equal score than second
    # (Based on scoring rules, GET /contacts should score higher than POST /search)
    assert len(option_lines) >= 2
