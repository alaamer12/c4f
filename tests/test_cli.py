"""Tests for the CLI interface of c4f.

This module contains tests for all command-line arguments and their combinations.
"""

import argparse
import locale
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import g4f # type: ignore
import pytest
from rich.panel import Panel
from rich.text import Text

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
    _create_patched_popen_init,
    _ensure_utf8_encoding,
    _ensure_utf8_environment,
    patch_subprocess_for_windows,
    fix_windows_encoding,
    _configure_stdout_stderr_encoding,
    _set_environment_encoding,
    _configure_locale_encoding,
    create_banner_text,
    style_banner_lines,
    determine_box_style,
    create_banner_panel,
    get_rich_banner,
    ColoredHelpFormatter,
    get_banner_description,
    get_epilog_text,
    display_banner,
    Colors,
    BANNER_ASCII,
    main,
    create_config_from_args
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

# Tests for encoding utility functions
def test_ensure_utf8_encoding():
    """Test _ensure_utf8_encoding with various kwargs combinations."""
    # Test with text=True
    kwargs = {"text": True}
    result = _ensure_utf8_encoding(kwargs)
    assert result["encoding"] == "utf-8"
    assert result["errors"] == "replace"
    
    # Test with universal_newlines=True
    kwargs = {"universal_newlines": True}
    result = _ensure_utf8_encoding(kwargs)
    assert result["encoding"] == "utf-8"
    assert result["errors"] == "replace"
    
    # Test with encoding already set
    kwargs = {"encoding": "latin-1", "text": True}
    result = _ensure_utf8_encoding(kwargs)
    assert result["encoding"] == "latin-1"  # Should not change existing encoding
    
    # Test with neither text nor universal_newlines
    kwargs = {"shell": True}
    result = _ensure_utf8_encoding(kwargs)
    assert "encoding" not in result  # Should not add encoding if not needed

def test_ensure_utf8_environment():
    """Test _ensure_utf8_environment with various kwargs combinations."""
    # Test with no env
    with patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=True):
        kwargs = {}
        result = _ensure_utf8_environment(kwargs)
        assert "env" in result
        assert result["env"]["PYTHONIOENCODING"] == "utf-8"
        assert result["env"]["EXISTING_VAR"] == "value"
    
    # Test with env=None
    kwargs = {"env": None}
    result = _ensure_utf8_environment(kwargs)
    assert kwargs == {"env": None}  # Should not modify when env is explicitly None
    
    # Test with existing env
    custom_env = {"MY_VAR": "custom_value"}
    kwargs = {"env": custom_env}
    result = _ensure_utf8_environment(kwargs)
    assert result["env"]["PYTHONIOENCODING"] == "utf-8"
    assert result["env"]["MY_VAR"] == "custom_value"

def test_create_patched_popen_init():
    """Test the _create_patched_popen_init function."""
    # Create a mock for the original init
    original_init = MagicMock()
    
    # Create the patched init
    patched_init = _create_patched_popen_init(original_init)
    
    # Create a mock instance and test kwargs
    instance = MagicMock()
    test_kwargs = {"text": True, "shell": True}
    
    # Call the patched init
    patched_init(instance, "command", **test_kwargs)
    
    # Verify original_init was called with transformed kwargs
    expected_kwargs = {
        "text": True, 
        "shell": True, 
        "encoding": "utf-8", 
        "errors": "replace",
        "env": {"PYTHONIOENCODING": "utf-8"}
    }
    
    # The original_init should have been called with the instance, command and modified kwargs
    original_init.assert_called_once()
    _, args, kwargs = original_init.mock_calls[0]
    assert args[0] == instance
    assert args[1] == "command"
    assert kwargs["text"] == expected_kwargs["text"]
    assert kwargs["shell"] == expected_kwargs["shell"]
    assert kwargs["encoding"] == expected_kwargs["encoding"]
    assert kwargs["errors"] == expected_kwargs["errors"]
    assert "PYTHONIOENCODING" in kwargs["env"]


def test_patch_subprocess_for_windows_replaces_init():
    import subprocess

    # 1) grab the real one
    original_init = subprocess.Popen.__init__

    # 2) apply your patch
    patch_subprocess_for_windows()

    # 3) now the attribute on the class should be different
    assert subprocess.Popen.__init__ is not original_init


@patch("sys.platform", "win32")
@patch("c4f.cli._configure_stdout_stderr_encoding")
@patch("c4f.cli._set_environment_encoding")
@patch("c4f.cli.patch_subprocess_for_windows")
@patch("c4f.cli._configure_locale_encoding")
def test_fix_windows_encoding_on_windows(mock_locale, mock_patch, mock_env, mock_stderr):
    """Test fix_windows_encoding when platform is Windows."""
    fix_windows_encoding()
    
    # Verify all functions were called
    mock_stderr.assert_called_once()
    mock_env.assert_called_once()
    mock_patch.assert_called_once()
    mock_locale.assert_called_once()

@patch("sys.platform", "linux")
@patch("c4f.cli._configure_stdout_stderr_encoding")
def test_fix_windows_encoding_not_on_windows(mock_stderr):
    """Test fix_windows_encoding when platform is not Windows."""
    fix_windows_encoding()
    
    # Verify no functions were called
    mock_stderr.assert_not_called()


@patch("sys.stderr.reconfigure", create=True)
@patch("sys.stdout.reconfigure", create=True)
def test_configure_stdout_stderr_encoding_with_reconfigure(
    mock_stdout_reconfigure,
    mock_stderr_reconfigure,
):
    """Test _configure_stdout_stderr_encoding uses reconfigure when available."""
    # Call the function under test
    _configure_stdout_stderr_encoding()

    # Verify reconfigure was called on both streams
    mock_stdout_reconfigure.assert_called_once_with(
        encoding="utf-8", errors="backslashreplace"
    )
    mock_stderr_reconfigure.assert_called_once_with(
        encoding="utf-8", errors="backslashreplace"
    )


def test_set_environment_encoding():
    """Test _set_environment_encoding sets PYTHONIOENCODING."""
    original_env = os.environ.get("PYTHONIOENCODING")
    
    try:
        # Clear the environment variable if it exists
        if "PYTHONIOENCODING" in os.environ:
            del os.environ["PYTHONIOENCODING"]
        
        # Call the function
        _set_environment_encoding()
        
        # Verify environment variable was set
        assert os.environ["PYTHONIOENCODING"] == "utf-8"
    
    finally:
        # Restore original environment
        if original_env:
            os.environ["PYTHONIOENCODING"] = original_env
        elif "PYTHONIOENCODING" in os.environ:
            del os.environ["PYTHONIOENCODING"]

@patch("locale.setlocale")
def test_configure_locale_encoding_success(mock_setlocale):
    """Test _configure_locale_encoding tries UTF-8 locale first."""
    # Call the function
    _configure_locale_encoding()
    
    # Verify setlocale was called with UTF-8
    mock_setlocale.assert_called_once_with(locale.LC_ALL, '.UTF-8')

@patch("locale.setlocale")
def test_configure_locale_encoding_fallback(mock_setlocale):
    """Test _configure_locale_encoding falls back to default locale on error."""
    # Make first call raise an error
    mock_setlocale.side_effect = [locale.Error, None]
    
    # Call the function
    _configure_locale_encoding()
    
    # Verify setlocale was called twice
    assert mock_setlocale.call_count == 2
    mock_setlocale.assert_has_calls([
        call(locale.LC_ALL, '.UTF-8'),
        call(locale.LC_ALL, '')
    ])

@patch("locale.setlocale")
def test_configure_locale_encoding_all_errors(mock_setlocale):
    """Test _configure_locale_encoding handles all errors gracefully."""
    # Make all calls raise errors
    mock_setlocale.side_effect = locale.Error
    
    # Call the function - should not raise any exceptions
    _configure_locale_encoding()
    
    # Verify setlocale was called twice
    assert mock_setlocale.call_count == 2

# Tests for banner functions
def test_create_banner_text():
    """Test that create_banner_text returns properly styled Text object."""
    banner = create_banner_text()
    
    # Verify it's a Text object with the BANNER_ASCII content
    assert isinstance(banner, Text)
    assert banner.plain == BANNER_ASCII

def test_style_banner_lines():
    """Test style_banner_lines styles the title line differently."""
    # Create a mock Text object with the BANNER_ASCII content
    banner_text = Text(BANNER_ASCII)
    
    # Style the banner lines
    styled_banner = style_banner_lines(banner_text)
    
    # Verify result is a Text object
    assert isinstance(styled_banner, Text)
    
    # The title line should be styled with bold green
    # (Hard to test exact styling, but we can verify it contains the title text)
    assert "Commit For Free - AI-Powered Git Commit Message Generator" in styled_banner.plain

@patch("sys.platform", "win32")
def test_determine_box_style_windows():
    """Test determine_box_style returns 'ascii' on Windows."""
    assert determine_box_style() == "ascii"

@patch("sys.platform", "linux")
def test_determine_box_style_linux():
    """Test determine_box_style returns 'rounded' on non-Windows platforms."""
    assert determine_box_style() == "rounded"

def test_create_banner_panel():
    """Test create_banner_panel creates a Panel with styled banner."""
    # Create a mock styled banner
    styled_banner = Text("Test Banner")
    box_style = "ascii"
    
    # Create the panel
    panel = create_banner_panel(styled_banner, box_style)
    
    # Verify result is a Panel
    assert isinstance(panel, Panel)
    assert panel.border_style == "cyan"
    assert panel.title == "C4F"

@patch("c4f.cli.create_banner_text", return_value=Text("Test Banner"))
@patch("c4f.cli.style_banner_lines", return_value=Text("Styled Banner"))
@patch("c4f.cli.determine_box_style", return_value="test_box_style")
def test_get_rich_banner(mock_box, mock_style, mock_create):
    """Test get_rich_banner creates a panel with styled banner."""
    # Call the function
    panel = get_rich_banner()
    
    # Verify all component functions were called
    mock_create.assert_called_once()
    mock_style.assert_called_once()
    mock_box.assert_called_once()
    
    # Verify result is a Panel
    assert isinstance(panel, Panel)
    assert panel.border_style == "cyan"
    assert panel.title == "C4F"

# Tests for ColoredHelpFormatter
def test_colored_help_formatter_init():
    """Test ColoredHelpFormatter initialization."""
    formatter = ColoredHelpFormatter("test_prog")
    assert formatter.color is True
    
    # Test with color=False
    formatter = ColoredHelpFormatter("test_prog", color=False)
    assert formatter.color is False

def test_format_action_with_color():
    """Test _format_action with color enabled."""
    formatter = ColoredHelpFormatter("test_prog")
    
    # Create a mock action
    action = MagicMock()
    action.option_strings = ["-h", "--help"]
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_action", 
                     return_value="  -h, --help  Show help\nusage: test\noptions:"):
        result = formatter._format_action(action)
        
        # Verify colors were added
        assert f"{Colors.BOLD}{Colors.GREEN}usage:{Colors.ENDC}" in result
        assert f"{Colors.BOLD}{Colors.BLUE}options:{Colors.ENDC}" in result
        assert f"{Colors.BOLD}{Colors.YELLOW}-h{Colors.ENDC}" in result

def test_format_action_without_color():
    """Test _format_action with color disabled."""
    formatter = ColoredHelpFormatter("test_prog", color=False)
    
    # Create a mock action
    action = MagicMock()
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_action", 
                     return_value="  -h, --help  Show help"):
        result = formatter._format_action(action)
        
        # Verify no colors were added
        assert result == "  -h, --help  Show help"

def test_format_usage_with_color():
    """Test _format_usage with color enabled."""
    formatter = ColoredHelpFormatter("test_prog")
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_usage", 
                     return_value="usage: test_prog [options]"):
        result = formatter._format_usage(None, None, None, None)
        
        # Verify colors were added
        assert f"{Colors.BOLD}{Colors.GREEN}usage:{Colors.ENDC}" in result

def test_format_usage_without_color():
    """Test _format_usage with color disabled."""
    formatter = ColoredHelpFormatter("test_prog", color=False)
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_usage", 
                     return_value="usage: test_prog [options]"):
        result = formatter._format_usage(None, None, None, None)
        
        # Verify no colors were added
        assert result == "usage: test_prog [options]"

def test_format_action_invocation_with_color():
    """Test _format_action_invocation with color enabled."""
    formatter = ColoredHelpFormatter("test_prog")
    
    # Create a mock action
    action = MagicMock()
    action.option_strings = ["-t", "--test"]
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_action_invocation", 
                     return_value="-t, --test"):
        result = formatter._format_action_invocation(action)
        
        # Simply verify that colors were added and the original text is preserved
        assert Colors.BOLD in result
        assert Colors.YELLOW in result
        assert Colors.ENDC in result
        assert "-t" in result.replace(Colors.BOLD, "").replace(Colors.YELLOW, "").replace(Colors.ENDC, "")
        assert "--test" in result.replace(Colors.BOLD, "").replace(Colors.YELLOW, "").replace(Colors.ENDC, "")

def test_format_action_invocation_without_color():
    """Test _format_action_invocation with color disabled."""
    formatter = ColoredHelpFormatter("test_prog", color=False)
    
    # Create a mock action
    action = MagicMock()
    action.option_strings = ["-t", "--test"]
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_action_invocation", 
                     return_value="-t, --test"):
        result = formatter._format_action_invocation(action)
        
        # Verify no colors were added
        assert result == "-t, --test"

def test_format_action_invocation_without_options():
    """Test _format_action_invocation with an action that has no option strings."""
    formatter = ColoredHelpFormatter("test_prog")
    
    # Create a mock action with no option strings (like a positional argument)
    action = MagicMock()
    action.option_strings = []
    
    # Mock the super method to return a known string
    with patch.object(argparse.RawDescriptionHelpFormatter, "_format_action_invocation", 
                     return_value="arg"):
        result = formatter._format_action_invocation(action)
        
        # Verify the result is unchanged
        assert result == "arg"

# Tests for banner and epilog text functions
def test_get_banner_description_with_color():
    """Test get_banner_description with color enabled."""
    result = get_banner_description(color=True)
    
    # Verify it contains the banner and color codes
    assert BANNER_ASCII.strip() in result.replace(Colors.BOLD, "").replace(Colors.BLUE, "").replace(Colors.GREEN, "").replace(Colors.ENDC, "")
    assert Colors.BOLD in result
    assert Colors.BLUE in result
    assert Colors.GREEN in result
    assert Colors.ENDC in result

def test_get_banner_description_without_color():
    """Test get_banner_description with color disabled."""
    result = get_banner_description(color=False)
    
    # Verify it contains the banner without color codes
    assert BANNER_ASCII in result
    assert Colors.BOLD not in result
    assert Colors.BLUE not in result
    assert Colors.GREEN not in result
    assert Colors.ENDC not in result



def test_get_epilog_text_with_color():
    """Test get_epilog_text with color enabled."""
    result = get_epilog_text(color=True)
    
    # Verify it contains the URL and color codes
    assert "https://github.com/alaamer12/c4f" in result
    assert Colors.GREEN in result
    assert Colors.ENDC in result

def test_get_epilog_text_without_color():
    """Test get_epilog_text with color disabled."""
    result = get_epilog_text(color=False)
    
    # Verify it contains the URL without color codes
    assert "https://github.com/alaamer12/c4f" in result
    assert Colors.GREEN not in result
    assert Colors.ENDC not in result

# Tests for display_banner and update_global_settings
@patch("builtins.print")
def test_display_banner_success(mock_print):
    """Test display_banner successfully prints colored banner."""
    display_banner()
    
    # Verify print was called with a string containing color codes
    mock_print.assert_called_once()
    args = mock_print.call_args[0][0]
    assert Colors.BOLD in args
    assert Colors.BLUE in args
    assert Colors.GREEN in args
    assert Colors.ENDC in args

@patch("builtins.print")
def test_display_banner_unicode_error(mock_print):
    """Test display_banner handles UnicodeEncodeError gracefully."""
    # Create a side effect function that raises UnicodeEncodeError first time, then returns None
    called = [False]
    def side_effect(*args, **kwargs):
        if not called[0]:
            called[0] = True
            raise UnicodeEncodeError('utf-8', b'test', 0, 1, 'Test error')
        return None
    
    mock_print.side_effect = side_effect
    
    display_banner()
    
    # Verify print was called twice (once for colored, once for plain)
    assert mock_print.call_count == 2
    
    # Second call should be with the fallback message "C4F - Commit For Free"
    mock_print.assert_has_calls([
        call(mock_print.call_args_list[0][0][0]),  # First call with any args
        call("   C4F - Commit For Free")  # Actual fallback message
    ])

@patch("builtins.print")
def test_display_banner_general_exception(mock_print):
    """Test display_banner handles general exceptions gracefully."""
    # Make the colored version raise a general exception
    mock_print.side_effect = [Exception("Test error"), None]
    
    display_banner()
    
    # Verify print was called twice (once for colored, once for fallback)
    assert mock_print.call_count == 2
    # Second call should be with the fallback message
    assert mock_print.call_args[0][0] == "   C4F - Commit For Free"


def test_create_config_from_args():
    """Test create_config_from_args creates a Config object with correct values."""
    # Create a mock args object
    args = argparse.Namespace(
        force_brackets=True,
        timeout=30,
        attempts=5,
        model="gpt-4"
    )

    # Create config from args
    config = create_config_from_args(args)

    # Check that the config was created with correct values
    assert config.force_brackets is True
    assert config.fallback_timeout == 30
    assert config.attempt == 5
    assert config.model == g4f.models.gpt_4o  # Check for the model object, not the string


def test_main():
    """Test main entry point function without parameters."""
    with patch("c4f.cli.display_banner") as mock_display_banner, \
         patch("c4f.cli.parse_args") as mock_parse_args, \
         patch("c4f.cli.create_config_from_args") as mock_create_config, \
         patch("c4f.cli.run_main") as mock_run_main:
        
        # Configure the mock return values
        mock_args = MagicMock()
        mock_config = MagicMock()
        mock_parse_args.return_value = mock_args
        mock_create_config.return_value = mock_config
        
        # Call the function
        main()
        
        # Verify all expected functions were called with correct arguments
        mock_display_banner.assert_called_once()
        mock_parse_args.assert_called_once()
        mock_create_config.assert_called_once_with(mock_args)
        mock_run_main.assert_called_once_with(mock_config)

@pytest.mark.parametrize("help_flag", ['-h', '--help', '-v', '--version'])
def test_main_with_help_flags(help_flag):
    """Test main function with help/version flags."""
    with patch("c4f.cli.sys.argv", [help_flag]), \
         patch("c4f.cli.display_banner") as mock_display_banner, \
         patch("c4f.cli.parse_args") as mock_parse_args, \
         patch("c4f.cli.create_config_from_args") as mock_create_config, \
         patch("c4f.cli.run_main") as mock_run_main:
        
        # Configure the mock return values
        mock_args = MagicMock()
        mock_config = MagicMock()
        mock_parse_args.return_value = mock_args
        mock_create_config.return_value = mock_config
        
        # Call the function
        main()
        
        # Verify banner was not displayed (help flags present)
        mock_display_banner.assert_not_called()
        mock_parse_args.assert_called_once()
        mock_create_config.assert_called_once_with(mock_args)
        mock_run_main.assert_called_once_with(mock_config)

@pytest.mark.parametrize("cli_args,expected_display_banner", [
    # Test no arguments (default behavior)
    ([], True),
    # Test with individual arguments
    (["-r", "/test/path"], True),
    (["-m", "gpt-4"], True),
    (["-a", "5"], True),
    (["-t", "20"], True),
    (["-f"], True),
    # Test help/version flags (should not display banner)
    (["-h"], False),
    (["--help"], False),
    (["-v"], False),
    (["--version"], False),
    # Test combinations of arguments
    (["-r", "/test/path", "-m", "gpt-4"], True),
    (["-r", "/test/path", "-a", "5", "-t", "20"], True),
    (["-m", "gpt-4", "-f"], True),
    (["-r", "/test/path", "-m", "gpt-4", "-a", "5", "-t", "20", "-f"], True),
    # Test long form arguments
    (["--root", "/test/path"], True),
    (["--model", "gpt-3.5-turbo"], True),
    (["--attempts", "2"], True),
    (["--timeout", "15"], True),
    (["--force-brackets"], True),
])
def test_main_with_various_arguments(cli_args, expected_display_banner):
    """Test main function with various command line arguments."""
    # Create a full argv list with the program name at the beginning
    argv = ["c4f"] + cli_args
    
    with patch("c4f.cli.sys.argv", argv), \
         patch("c4f.cli.display_banner") as mock_display_banner, \
         patch("c4f.cli.parse_args") as mock_parse_args, \
         patch("c4f.cli.create_config_from_args") as mock_create_config, \
         patch("c4f.cli.run_main") as mock_run_main:
        
        # Configure the mock return values
        mock_args = MagicMock()
        mock_config = MagicMock()
        mock_parse_args.return_value = mock_args
        mock_create_config.return_value = mock_config
        
        # Call the function
        main()
        
        # Verify display_banner was called or not based on expectation
        if expected_display_banner:
            mock_display_banner.assert_called_once()
        else:
            mock_display_banner.assert_not_called()
            
        mock_parse_args.assert_called_once()
        mock_create_config.assert_called_once_with(mock_args)
        mock_run_main.assert_called_once_with(mock_config)

@pytest.mark.parametrize("test_name,exceptions,expectation", [
    ("parse_args_exception",
     {"parse_args": Exception("Parse error")},
     {"display_banner": True, "create_config": False, "run_main": False}),
    
    ("create_config_exception",
     {"create_config": Exception("Config error")},
     {"display_banner": True, "parse_args": True, "run_main": False}),
    
    ("run_main_exception",
     {"run_main": Exception("Main error")},
     {"display_banner": True, "parse_args": True, "create_config": True}),
])
def test_main_exception_handling(test_name, exceptions, expectation):
    """Test main function exception handling for various components."""
    with patch("c4f.cli.display_banner") as mock_display_banner, \
         patch("c4f.cli.parse_args") as mock_parse_args, \
         patch("c4f.cli.create_config_from_args") as mock_create_config, \
         patch("c4f.cli.run_main") as mock_run_main:
        
        # Configure mocks to raise exceptions if specified
        mock_args = MagicMock()
        mock_config = MagicMock()
        mock_parse_args.return_value = mock_args
        mock_create_config.return_value = mock_config
        
        if "display_banner" in exceptions:
            mock_display_banner.side_effect = exceptions["display_banner"]
        if "parse_args" in exceptions:
            mock_parse_args.side_effect = exceptions["parse_args"]
        if "create_config" in exceptions:
            mock_create_config.side_effect = exceptions["create_config"]
        if "run_main" in exceptions:
            mock_run_main.side_effect = exceptions["run_main"]
        
        # Call the function - should not raise exceptions outside
        with pytest.raises(Exception) as exc_info:
            main()
        
        # Verify the specific exception message
        for name, exception in exceptions.items():
            if isinstance(exception, Exception):
                assert str(exception) in str(exc_info.value)
                
        # Verify call expectations
        if expectation.get("display_banner", False):
            mock_display_banner.assert_called_once()
        if expectation.get("parse_args", False):
            mock_parse_args.assert_called_once()
        if expectation.get("create_config", False):
            mock_create_config.assert_called_once_with(mock_args)
        if expectation.get("run_main", False):
            mock_run_main.assert_called_once_with(mock_config)