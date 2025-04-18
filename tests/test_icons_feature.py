"""Tests for the emoji icon features in c4f."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from c4f.config import Config
from c4f.main import (
    FileChange,
    generate_fallback_message,
    get_icon_for_type,
    select_appropriate_icon,
)
from c4f._purifier import Purify, can_display_emojis, get_ascii_icon_for_type, is_non_terminal_output, \
    has_emoji_compatible_terminal, has_utf8_locale, has_windows_utf8_support


class TestIconUtilityFunctions:
    """Tests for the icon utility functions."""

    @patch("sys.stdout.isatty")
    def test_is_non_terminal_output(self, mock_isatty):
        """Test is_non_terminal_output function."""
        # Test when stdout is a terminal
        mock_isatty.return_value = True
        assert is_non_terminal_output() is False

        # Test when stdout is not a terminal
        mock_isatty.return_value = False
        assert is_non_terminal_output() is True

    @patch.dict(os.environ, {"TERM": "xterm-256color"})
    def test_has_emoji_compatible_terminal_supported(self):
        """Test has_emoji_compatible_terminal with supported terminal."""
        assert has_emoji_compatible_terminal() is True

    @patch.dict(os.environ, {"TERM": "dumb"})
    def test_has_emoji_compatible_terminal_unsupported(self):
        """Test has_emoji_compatible_terminal with unsupported terminal."""
        assert has_emoji_compatible_terminal() is False

    @patch.dict(os.environ, {})
    def test_has_emoji_compatible_terminal_no_term(self):
        """Test has_emoji_compatible_terminal with no TERM env var."""
        if "TERM" in os.environ:
            del os.environ["TERM"]
        assert has_emoji_compatible_terminal() is False

    @patch.dict(os.environ, {"LC_ALL": "en_US.UTF-8"})
    def test_has_utf8_locale_supported(self):
        """Test has_utf8_locale with UTF-8 locale."""
        assert has_utf8_locale() is True

    @patch.dict(os.environ, {"LC_ALL": "en_US.ISO8859-1"})
    def test_has_utf8_locale_unsupported(self):
        """Test has_utf8_locale with non-UTF-8 locale."""
        assert has_utf8_locale() is False

    @patch.dict(os.environ, {})
    def test_has_utf8_locale_fallback_checks(self):
        """Test has_utf8_locale with fallback environment variables."""
        if "LC_ALL" in os.environ:
            del os.environ["LC_ALL"]

        # Test LC_CTYPE fallback
        os.environ["LC_CTYPE"] = "en_US.utf8"
        assert has_utf8_locale() is True

        # Test LANG fallback
        del os.environ["LC_CTYPE"]
        os.environ["LANG"] = "C.UTF-8"
        assert has_utf8_locale() is True

        # Test no locale variables set
        del os.environ["LANG"]
        assert has_utf8_locale() is False

    @patch("sys.platform", "win32")
    def test_has_windows_utf8_support_windows(self):
        """Test has_windows_utf8_support on Windows."""
        with patch("ctypes.windll.kernel32.GetConsoleOutputCP", return_value=65001):
            assert has_windows_utf8_support() is True

        with patch("ctypes.windll.kernel32.GetConsoleOutputCP", return_value=437):
            assert has_windows_utf8_support() is False

        with patch("ctypes.windll.kernel32.GetConsoleOutputCP", side_effect=AttributeError):
            assert has_windows_utf8_support() is False

    @patch("sys.platform", "linux")
    def test_has_windows_utf8_support_non_windows(self):
        """Test has_windows_utf8_support on non-Windows platforms."""
        assert has_windows_utf8_support() is False

    @patch("c4f._purifier.is_non_terminal_output")
    @patch("c4f._purifier.has_emoji_compatible_terminal")
    @patch("c4f._purifier.has_utf8_locale")
    @patch("c4f._purifier.has_windows_utf8_support")
    def test_can_display_emojis_all_paths(
        self, mock_non_terminal, mock_locale, mock_terminal, mock_windows,
    ):
        """Test can_display_emojis with all possible paths."""
        # Test non-terminal output
        mock_non_terminal.return_value = True
        assert can_display_emojis() is True
        
        # Test terminal output with compatible terminal
        mock_non_terminal.return_value = False
        mock_terminal.return_value = True
        assert can_display_emojis() is True
        
        # Test terminal output with UTF-8 locale
        mock_terminal.return_value = False
        mock_locale.return_value = True
        assert can_display_emojis() is True

        # Test terminal output with Windows UTF-8 support
        mock_locale.return_value = False
        mock_windows.return_value = True
        assert can_display_emojis() is True
        
        # Test with no emoji support
        mock_windows.return_value = False
        assert can_display_emojis() is False


class TestIconFormatFunctions:
    """Tests for the icon formatting functions."""

    @pytest.mark.parametrize(
        "change_type,expected_icon",
        [
            ("feat", "✨"),
            ("fix", "🐛"),
            ("docs", "📝"),
            ("style", "💄"),
            ("refactor", "♻️"),
            ("perf", "⚡"),
            ("test", "✅"),
            ("build", "👷"),
            ("ci", "🔧"),
            ("chore", "🔨"),
            ("revert", "⏪"),
            ("security", "🔒"),
            ("unknown", "🎯"),  # Default
            (None, "🎯"),  # Handle None
        ],
    )
    def test_get_icon_for_type(self, change_type, expected_icon):
        """Test get_icon_for_type with various change types."""
        assert get_icon_for_type(change_type) == expected_icon

    @pytest.mark.parametrize(
        "change_type,expected_ascii",
        [
            ("feat", "[+]"),
            ("fix", "[!]"),
            ("docs", "[d]"),
            ("style", "[s]"),
            ("refactor", "[r]"),
            ("perf", "[p]"),
            ("test", "[t]"),
            ("build", "[b]"),
            ("ci", "[c]"),
            ("chore", "[.]"),
            ("revert", "[<]"),
            ("security", "[#]"),
            ("unknown", "[*]"),  # Default
            (None, "[*]"),  # Handle None
        ],
    )
    def test_get_ascii_icon_for_type(self, change_type, expected_ascii):
        """Test get_ascii_icon_for_type with various change types."""
        assert get_ascii_icon_for_type(change_type) == expected_ascii

    @pytest.mark.parametrize(
        "message,expected_type",
        [
            ("feat: add new feature", "feat"),
            ("fix(core): resolve bug", "fix"),
            ("docs: update README", "docs"),
            ("style: format code", "style"),
            ("refactor: simplify logic", "refactor"),
            ("perf: optimize algorithm", "perf"),
            ("test: add unit tests", "test"),
            ("build: update dependencies", "build"),
            ("ci: improve pipeline", "ci"),
            ("chore: update version", "chore"),
            ("revert: undo previous commit", "revert"),
            ("security: fix vulnerability", "security"),
            ("✨ feat: add new feature", "feat"),
            ("🐛 fix(core): resolve bug", "fix"),
            ("📝 docs: update README", "docs"),
            ("random text", None),
            ("", None),
        ],
    )
    def test_extract_commit_type(self, message, expected_type):
        """Test extract_commit_type with various commit messages."""
        assert Purify.extract_commit_type(message) == expected_type

    @pytest.mark.parametrize(
        "message,icon_enabled,expected",
        [
            ("✨ feat: new feature", True, "✨ feat: new feature"),
            ("✨ feat: new feature", False, "feat: new feature"),
            ("feat: new feature", True, "feat: new feature"),
            ("feat: new feature", False, "feat: new feature"),
            ("🐛 fix: bug fix", True, "🐛 fix: bug fix"),
            ("🐛 fix: bug fix", False, "fix: bug fix"),
            ("  ✨ feat: with spaces", False, "  feat: with spaces"),
        ],
    )
    def test_purify_icons_basic(self, message, icon_enabled, expected):
        """Test purify_icons with icons enabled/disabled."""
        assert Purify.icons(message, icon_enabled) == expected

    @patch("c4f._purifier.Purify.extract_commit_type")
    @patch("c4f._purifier.can_display_emojis")
    def test_purify_icons_with_ascii_conversion(self, mock_can_display, mock_extract_type):
        """Test purify_icons with ASCII conversion."""
        # Setup
        config = Config(icon=True, ascii_only=True)
        message = "✨ feat: new feature"
        mock_extract_type.return_value = "feat"
        
        # Execute
        result = Purify.icons(message, True, config)
        
        # Verify
        assert "[+] " in result
        assert "✨" not in result
        assert "feat: new feature" in result

    @patch("c4f._purifier.can_display_emojis")
    def test_purify_icons_terminal_capability(self, mock_can_display):
        """Test purify_icons terminal capability check."""
        # Setup
        config = Config(icon=True, ascii_only=False)
        message = "✨ feat: new feature"
        
        # Test with terminal that can't display emojis
        mock_can_display.return_value = False
        result = Purify.icons(message, True, config)
        assert "✨" not in result
        assert "[+]" in result
        
        # Test with terminal that can display emojis
        mock_can_display.return_value = True
        result = Purify.icons(message, True, config)
        assert "✨" in result


class TestSelectIconFunctions:
    """Tests for the icon selection functions."""

    @pytest.mark.parametrize(
        "change_type,config_icon,expected_prefix",
        [
            ("feat", True, "✨ "),  # Icon enabled, can display emojis
            ("feat", False, ""),    # Icon disabled
            (None, True, "🎯 "),    # Default icon
            (None, False, ""),      # Default with icons disabled
        ],
    )
    @patch("c4f.main.can_display_emojis", return_value=True)
    def test_select_appropriate_icon_basic(
        self, mock_can_display, change_type, config_icon, expected_prefix
    ):
        """Test select_appropriate_icon basic functionality."""
        config = Config(icon=config_icon)
        assert select_appropriate_icon(change_type, config) == expected_prefix

    @patch("c4f.main.can_display_emojis", return_value=False)
    def test_select_appropriate_icon_ascii_fallback(self, mock_can_display):
        """Test select_appropriate_icon falls back to ASCII when emojis not supported."""
        config = Config(icon=True)
        assert select_appropriate_icon("feat", config) == "[+] "

    def test_select_appropriate_icon_force_ascii(self):
        """Test select_appropriate_icon with ascii_only flag."""
        config = Config(icon=True, ascii_only=True)
        assert select_appropriate_icon("feat", config) == "[+] "

    def test_select_appropriate_icon_no_config(self):
        """Test select_appropriate_icon with no config."""
        assert select_appropriate_icon("feat", None) == ""


class TestFallbackMessageGeneration:
    """Tests for the fallback message generation with icons."""

    def test_generate_fallback_message_no_icon(self):
        """Test generate_fallback_message without icons."""
        # Setup
        changes = [
            FileChange(Path("file1.py"), "M", "diff content", "feat"),
            FileChange(Path("file2.py"), "A", "diff content", "feat"),
        ]
        config = Config(icon=False)
        
        # Execute
        message = generate_fallback_message(changes, config)
        
        # Verify
        assert message == "feat: update file1.py file2.py"

    @patch("c4f.main.select_appropriate_icon", return_value="✨ ")
    def test_generate_fallback_message_with_unicode_icon(self, mock_select_icon):
        """Test generate_fallback_message with Unicode icon."""
        # Setup
        changes = [
            FileChange(Path("file1.py"), "M", "diff content", "feat"),
            FileChange(Path("file2.py"), "A", "diff content", "feat"),
        ]
        config = Config(icon=True)
        
        # Execute
        message = generate_fallback_message(changes, config)
        
        # Verify
        assert message == "✨ feat: update file1.py file2.py"

    @patch("c4f.main.select_appropriate_icon", return_value="[+] ")
    def test_generate_fallback_message_with_ascii_icon(self, mock_select_icon):
        """Test generate_fallback_message with ASCII icon."""
        # Setup
        changes = [
            FileChange(Path("file1.py"), "M", "diff content", "feat"),
            FileChange(Path("file2.py"), "A", "diff content", "feat"),
        ]
        config = Config(icon=True, ascii_only=True)
        
        # Execute
        message = generate_fallback_message(changes, config)
        
        # Verify
        assert message == "[+] feat: update file1.py file2.py"

    def test_generate_fallback_message_different_types(self):
        """Test generate_fallback_message with different change types."""
        # Setup
        changes = [
            FileChange(Path("file1.py"), "M", "diff content", "fix"),
            FileChange(Path("file2.py"), "A", "diff content", "feat"),
        ]
        config = Config(icon=True)
        
        # The first change type (fix) should be used
        with patch("c4f.main.select_appropriate_icon", return_value="🐛 ") as mock_select:
            message = generate_fallback_message(changes, config)
            mock_select.assert_called_once_with("fix", config)
            assert message == "🐛 fix: update file1.py file2.py" 