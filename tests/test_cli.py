"""Tests for the CLI interface of c4f.

This module contains tests for all command-line arguments and their combinations.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import CLI modules
from c4f.cli import (
    create_argument_parser,
    add_version_argument,
    add_directory_argument,
    add_model_argument,
    add_generation_arguments,
    add_formatting_arguments,
)

# Test data
TEST_ROOT = Path("/test/root")
TEST_MODELS = ["gpt-4-mini", "gpt-4", "gpt-3.5-turbo"]


@pytest.fixture
def parser():
    """Fixture to create a fresh argument parser for each test."""
    return create_argument_parser()

def test_version_argument(parser):
    """Test version argument parsing."""
    add_version_argument(parser)
    
    # Testing version requires catching the SystemExit
    with pytest.raises(SystemExit):
        parser.parse_args(["-v"])

def test_directory_argument(parser):
    """Test directory argument parsing."""
    add_directory_argument(parser)
    
    # Test default value
    args = parser.parse_args([])
    assert args.root == Path.cwd()
    
    # Test custom path
    args = parser.parse_args(["-r", str(TEST_ROOT)])
    assert args.root == TEST_ROOT

def test_model_argument(parser):
    """Test model argument parsing."""
    add_model_argument(parser)
    
    # Test default value
    args = parser.parse_args([])
    assert args.model == "gpt-4-mini"
    
    # Test all valid models
    for model in TEST_MODELS:
        args = parser.parse_args(["-m", model])
        assert args.model == model
    
    # Test invalid model
    with pytest.raises(SystemExit):
        parser.parse_args(["-m", "invalid-model"])

def test_generation_arguments(parser):
    """Test generation-related arguments parsing."""
    add_generation_arguments(parser)
    
    # Test attempts argument
    args = parser.parse_args(["-a", "5"])
    assert args.attempts == 5
    
    # Test timeout argument
    args = parser.parse_args(["-t", "30"])
    assert args.timeout == 30
    
    # Test invalid attempts
    with pytest.raises(SystemExit):
        parser.parse_args(["-a", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["-a", "11"])
    
    # Test invalid timeout
    with pytest.raises(SystemExit):
        parser.parse_args(["-t", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["-t", "61"])

def test_formatting_arguments(parser):
    """Test formatting-related arguments parsing."""
    add_formatting_arguments(parser)
    
    # Test force-brackets argument
    args = parser.parse_args(["-f"])
    assert args.force_brackets is True
    
    # Test defaults
    args = parser.parse_args([])
    assert args.force_brackets is False


def test_all_arguments_combined(parser):
    """Test all arguments combined in different combinations."""
    add_directory_argument(parser)
    add_model_argument(parser)
    add_generation_arguments(parser)
    add_formatting_arguments(parser)
    
    # Test combination 1
    args = parser.parse_args([
        "-r", str(TEST_ROOT),
        "-m", "gpt-4",
        "-a", "5",
        "-t", "30",
        "-f",
    ])
    assert args.root == TEST_ROOT
    assert args.model == "gpt-4"
    assert args.attempts == 5
    assert args.timeout == 30
    assert args.force_brackets is True
    
    # Test combination 2 with long options
    args = parser.parse_args([
        "--root", str(TEST_ROOT),
        "--model", "gpt-3.5-turbo",
        "--attempts", "3",
        "--timeout", "15",
        "--force-brackets",
    ])
    assert args.root == TEST_ROOT
    assert args.model == "gpt-3.5-turbo"
    assert args.attempts == 3
    assert args.timeout == 15
    assert args.force_brackets is True


def test_help_message_raises_system_exit(parser):
    """Test help message raises SystemExit."""
    add_version_argument(parser)
    add_directory_argument(parser)
    add_model_argument(parser)
    
    # Test help flag
    with pytest.raises(SystemExit):
        parser.parse_args(["-h"])

@pytest.mark.parametrize("args,expected", [
    ([], {
        "root": Path.cwd(),
        "model": "gpt-4-mini",
        "attempts": 3,
        "timeout": 10,
        "force_brackets": False,
    }),
    (["-r", "/test", "-m", "gpt-4", "-a", "5", "-t", "20", "-f"], {
        "root": Path("/test"),
        "model": "gpt-4",
        "attempts": 5,
        "timeout": 20,
        "force_brackets": True,
    })
])
def test_argument_defaults_and_values(args, expected):
    """Test argument defaults and values using parametrize."""
    parser = create_argument_parser()
    add_directory_argument(parser)
    add_model_argument(parser)
    add_generation_arguments(parser)
    add_formatting_arguments(parser)

    
    parsed_args = parser.parse_args(args)
    for key, value in expected.items():
        assert getattr(parsed_args, key) == value

@patch("c4f.cli.parse_args")
def test_main_function(mock_parse_args):
    """Test the main function with mocked dependencies."""
    # Create a mock args object
    mock_args = MagicMock()

    mock_args.model = "gpt-4"
    mock_args.root = Path("/test")
    mock_args.attempts = 5
    mock_args.timeout = 20
    mock_args.force_brackets = True
    
    mock_parse_args.return_value = mock_args
    
    # Mock the main module import
    with patch.dict("sys.modules", {"c4f.main": MagicMock()}):
        # Mock the main function
        sys.modules["c4f.main"].main = MagicMock()
        
        # Import our cli module
        from c4f.cli import main
        
        # Call the main function
        main()
        
        # Verify that parse_args was called
        mock_parse_args.assert_called_once()
        
        # Verify that the main function was called
        sys.modules["c4f.main"].main.assert_called_once() 