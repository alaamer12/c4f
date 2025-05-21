"""Contains purification utilities for commit messages.

This module provides the Purify class which contains methods for cleaning up
generated commit messages by removing unwanted content, fixing formatting issues,
and ensuring proper conventional commit format.
"""

import os
import re
import sys
import unicodedata
from typing import Optional

from c4f.config import Config

LOWER_ASCII_BOUND = 32
HIGHER_ASCII_BOUND = 126

__all__ = [
    "Purify",
    "can_display_emojis",
    "get_ascii_icon_for_type",
    "has_emoji_compatible_terminal",
    "has_utf8_locale",
    "has_windows_utf8_support",
    "is_non_terminal_output",
]


def get_ascii_icon_for_type(change_type: Optional[str]) -> str:
    """Get the appropriate ASCII text alternative for emoji icons.

    Args:
        change_type: The type of change (feat, fix, etc.).

    Returns:
        str: The corresponding ASCII alternative for the change type.
    """
    ascii_icons = {
        "feat": "[+]",
        "fix": "[!]",
        "docs": "[d]",
        "style": "[s]",
        "refactor": "[r]",
        "perf": "[p]",
        "test": "[t]",
        "build": "[b]",
        "ci": "[c]",
        "chore": "[.]",
        "revert": "[<]",
        "security": "[#]",
    }
    return ascii_icons.get(str(change_type), "[*]")  # Default icon if type not found


def is_non_terminal_output() -> bool:
    """Check if output is not going to a terminal."""
    return not sys.stdout.isatty()


def has_emoji_compatible_terminal() -> bool:
    """Check if the terminal type is known to support emojis."""
    term = os.environ.get("TERM", "").lower()
    emoji_compatible_terms = ["xterm", "vt100", "vt220", "linux", "screen", "tmux"]
    return any(x in term for x in emoji_compatible_terms)


def has_utf8_locale() -> bool:
    """Check if the system locale is set to UTF-8.

    Returns:
        bool: True if locale is UTF-8, False otherwise.
    """
    locale = os.environ.get(
        "LC_ALL", os.environ.get("LC_CTYPE", os.environ.get("LANG", ""))
    )
    return "utf-8" in locale.lower() or "utf8" in locale.lower()


def has_windows_utf8_support() -> bool:
    """Check if Windows console is configured to support UTF-8.

    Returns:
        bool: True if Windows console supports UTF-8, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # UTF-8 code page is 65001
        codepage = 65001
        return bool(kernel32.GetConsoleOutputCP() == codepage)
    except (ImportError, AttributeError):
        return False


def can_display_emojis() -> bool:
    """Check if the terminal likely supports emoji display.

    This is a best-effort detection that checks the environment
    to determine if emojis are likely to display correctly.

    Returns:
        bool: True if emojis should display correctly, False otherwise.
    """
    # TODO: Broken tests  # noqa: FIX002, TD002, TD003
    if is_non_terminal_output():
        return True

    if has_emoji_compatible_terminal():
        return True

    if has_utf8_locale():
        return True

    return has_windows_utf8_support()  # Default Return


# noinspection RegExpAnonymousGroup
class Purify:
    """A class for cleaning up and formatting commit messages.

    This class provides methods for various purification operations on commit messages,
    such as removing code blocks, fixing formatting issues, handling emoji icons, etc.
    """

    @staticmethod
    def batrick(message: str) -> str:
        """Remove code block formatting (backticks) from a message.

        Handles different code block formats including those with language specifiers.

        Args:
            message: The commit message to clean.

        Returns:
            str: The message without code block formatting.
        """
        if message.startswith("```") and message.endswith("```"):
            # Check if there's a language specifier like ```git or ```commit
            lines = message.split("\n")
            if len(lines) > 2:  # noqa: PLR2004
                # If first line has just the opening backticks with potential language specifier
                if lines[0].startswith("```") and len(lines[0]) <= 10:  # noqa: PLR2004
                    message = "\n".join(lines[1:-1])
                else:
                    message = message[3:-3]
            else:
                message = message[3:-3]

        return message

    @classmethod
    def commit_message_introduction(cls, message: str) -> str:
        """Remove common introductory phrases from commit messages.

        Removes prefixes like "commit message:" that are often added by AI models.

        Args:
            message: The commit message to clean.

        Returns:
            str: The message without introductory phrases.
        """
        prefixes_to_remove = cls._generate_introduction_prefixes()
        return cls._remove_matching_prefix(message, prefixes_to_remove)

    @classmethod
    def _generate_introduction_prefixes(cls) -> list[str]:
        """Generate a comprehensive list of introductory prefixes to remove.

        Returns:
            A list of prefix strings that should be removed from commit messages.
        """
        prefixes_to_remove = []

        # Generate combinations of base phrases and intro phrases
        prefixes_to_remove.extend(cls._generate_combined_prefixes())

        # Add additional standalone prefixes
        prefixes_to_remove.extend(
            [
                "proposed commit:",
                "recommended commit:",
                "for this commit:",
                "as a commit message:",
                "the commit message is:",
            ]
        )

        return prefixes_to_remove

    @classmethod
    def _generate_combined_prefixes(cls) -> list[str]:
        """Generate combinations of base phrases and introductory phrases.

        Returns:
            A list of combined prefix strings.
        """
        base_phrases = [
            "commit message",
            "commit",
            "git commit message",
            "suggested commit message",
        ]
        intro_phrases = [
            "here's a",
            "here is the",
            "here is a",
            "i've created a",
            "i have created a",
        ]

        combined_prefixes = []

        # Add base phrases with colons
        for base in base_phrases:
            combined_prefixes.append(f"{base}:")

            # Add variations with intro phrases
            for intro in intro_phrases:
                combined_prefixes.append(f"{intro} {base}:")

        return combined_prefixes

    @staticmethod
    def _remove_matching_prefix(message: str, prefixes: list[str]) -> str:
        """Remove the first matching prefix from a message.

        Args:
            message: The message to process.
            prefixes: List of prefixes to check for and remove.

        Returns:
            The message with any matching prefix removed.
        """
        message_lower = message.lower()

        for prefix in prefixes:
            if message_lower.startswith(prefix):
                return message[len(prefix) :].strip()

        return message

    @staticmethod
    def explanatory_message(message: str) -> str:
        """Remove explanatory sections from commit messages.

        Removes sections that start with markers like "explanation:" or "note:".

        Args:
            message: The commit message to clean.

        Returns:
            str: The message without explanatory sections.
        """
        explanatory_markers = [
            "explanation:",
            "explanation of changes:",
            "note:",
            "notes:",
            "this commit message",
            "i hope this helps",
            "please let me know",
        ]

        for marker in explanatory_markers:
            if marker in message.lower():
                parts = message.lower().split(marker)
                message = parts[0].strip()

        return message

    @staticmethod
    def htmlxml(message: str) -> str:
        """Remove HTML/XML tags from a message."""
        return re.sub(r"<[^>]+>", "", message)

    @staticmethod
    def disclaimers(message: str) -> str:
        """Remove trailing disclaimers from a message.

        Stops processing lines once it encounters a disclaimer phrase, keeping only
        the content before it.

        Args:
            message: The commit message to clean.

        Returns:
            str: The message without trailing disclaimers.
        """
        lines = message.strip().split("\n")
        filtered_lines = []
        for line in lines:
            if any(
                x in line.lower()
                for x in [
                    "let me know if",
                    "please review",
                    "is this helpful",
                    "hope this",
                    "i've followed",
                ]
            ):
                break
            filtered_lines.append(line)

        return "\n".join(filtered_lines).strip()

    @classmethod
    def format(cls, message: str, config: Optional[Config] = None) -> str:
        """Fix conventional commit format issues where type and scope are combined.

        Examples:
        - "fixversion: message" → "fix(version): message" (if force_brackets=True)
        - "fixversion: message" → "fix version: message" (if force_brackets=False)
        - "featprocessor: message" → "feat(processor): message" (if force_brackets=True)
        - "featprocessor: message" → "feat processor: message" (if force_brackets=False)

        Args:
            message: The commit message to format.
            config: Configuration object with settings for the commit message generator.

        Returns:
            str: The properly formatted commit message.
        """
        if not cls._is_valid_for_format_correction(message):
            return message

        first_part = cls._extract_first_part(message)

        if cls._has_proper_scope_formatting(first_part):
            return message

        commit_type, scope = cls._find_combined_type_and_scope(first_part)
        if not commit_type:
            return message

        remaining_message = cls._extract_remaining_message(message)
        force_brackets = cls._should_force_brackets(config)

        return cls._format_commit_message(
            commit_type, scope, remaining_message, force_brackets
        )

    @staticmethod
    def _is_valid_for_format_correction(message: str) -> bool:
        """Check if the message is valid for format correction.

        Args:
            message: The commit message to check.

        Returns:
            bool: True if the message is valid for correction, False otherwise.
        """
        return bool(message and " " in message)

    @staticmethod
    def _extract_first_part(message: str) -> str:
        """Extract the first part of the message before the colon.

        Args:
            message: The commit message.

        Returns:
            str: The first part of the message.
        """
        return message.split(":", 1)[0].strip()

    @staticmethod
    def _has_proper_scope_formatting(first_part: str) -> bool:
        """Check if the first part already has proper scope formatting.

        Args:
            first_part: The first part of the commit message.

        Returns:
            bool: True if the first part has proper scope formatting, False otherwise.
        """
        return "(" in first_part and ")" in first_part

    @staticmethod
    def _find_combined_type_and_scope(first_part: str) -> tuple[Optional[str], str]:
        """Find a combined commit type and scope in the first part.

        Args:
            first_part: The first part of the commit message.

        Returns:
            tuple: A tuple containing the commit type and scope if found, or (None, "") if not found.
        """
        commit_types = [
            "feat",
            "fix",
            "docs",
            "style",
            "refactor",
            "perf",
            "test",
            "build",
            "ci",
            "chore",
            "revert",
            "security",
        ]

        for commit_type in commit_types:
            if first_part.lower().startswith(commit_type) and len(first_part) > len(
                commit_type
            ):
                scope = first_part[len(commit_type) :]
                return commit_type, scope

        return None, ""

    @staticmethod
    def _extract_remaining_message(message: str) -> str:
        """Extract the remaining part of the message after the colon.

        Args:
            message: The commit message.

        Returns:
            str: The remaining part of the message.
        """
        if ":" in message:
            return message.split(":", 1)[1]
        return ""

    @staticmethod
    def _should_force_brackets(config: Optional[Config]) -> bool:
        """Determine if brackets should be forced based on config.

        Args:
            config: Configuration object with settings for the commit message generator.

        Returns:
            bool: True if brackets should be forced, False otherwise.
        """
        return config.force_brackets if config else False

    @staticmethod
    def _format_commit_message(
        commit_type: str, scope: str, remaining_message: str, force_brackets: bool
    ) -> str:
        """Format the commit message with the given type, scope, and remaining message.

        Args:
            commit_type: The commit type (feat, fix, etc.).
            scope: The scope of the commit.
            remaining_message: The remaining part of the message.
            force_brackets: Whether to force brackets around the scope.

        Returns:
            str: The formatted commit message.
        """
        if force_brackets:
            # Use parentheses for scope
            return f"{commit_type}({scope}):{remaining_message}"
        # Use space separation
        return f"{commit_type} {scope}:{remaining_message}"

    @staticmethod
    def text(message: str) -> str:
        """Clean up broken textgraphy and corrupt characters while preserving valid icons.

        This function:
        - Removes control characters (except tabs and newlines)
        - Normalizes Unicode to consistent forms
        - Removes zero-width characters and other invisible formatting
        - Replaces broken/corrupt characters

        Args:
            message: The commit message to clean.

        Returns:
            str: The message with broken characters removed or fixed.
        """
        # Skip processing if message is empty
        if not message:
            return message

        # Apply text cleaning steps in sequence
        message = Purify._normalize_unicode(message)
        message = Purify._filter_characters(message)
        message = Purify._normalize_whitespace(message)
        return Purify._remove_zero_width_chars(message)  # Final step

    @staticmethod
    def _normalize_unicode(message: str) -> str:
        """Normalize Unicode to consistent forms."""
        return unicodedata.normalize("NFC", message)

    @staticmethod
    def _filter_characters(message: str) -> str:
        """Filter out control and broken characters while preserving important ones.

        Args:
            message: The message to filter.

        Returns:
            str: Message with only preserved characters.
        """
        return "".join(char for char in message if Purify._should_preserve_char(char))

    @staticmethod
    def _should_preserve_char(char: str) -> bool:
        """Determine if a character should be preserved in the output.

        Args:
            char: The character to check.

        Returns:
            bool: True if the character should be preserved, False otherwise.
        """

        if not char:
            return True

        # Final check for punctuation and symbols
        return (
            Purify._is_empty_or_whitespace_control(char)
            or Purify._is_printable_ascii(char)
            or Purify._is_in_preserve_ranges(char)
            or Purify._is_punctuation_or_symbol(char)
        )

    @staticmethod
    def _is_empty_or_whitespace_control(char: str) -> bool:
        """Check if character is empty or a preserved whitespace control character."""
        return not char or char in "\n\t"

    @staticmethod
    def _is_printable_ascii(char: str) -> bool:
        """Check if character is in the printable ASCII range.

        Args:
            char: The character to check.

        Returns:
            bool: True if character is printable ASCII.
        """
        if not char.isascii():
            return False

        code_point = ord(char)
        return LOWER_ASCII_BOUND <= code_point <= HIGHER_ASCII_BOUND

    @staticmethod
    def _is_in_preserve_ranges(char: str) -> bool:
        """Check if character is in one of the preserved Unicode ranges.

        Args:
            char: The character to check.

        Returns:
            bool: True if character is in a preserved range.
        """
        code_point = ord(char)
        preserve_ranges = Purify._get_preserve_ranges()

        return any(start <= code_point <= end for start, end in preserve_ranges)

    @staticmethod
    def _is_punctuation_or_symbol(char: str) -> bool:
        """Check if character is punctuation or a symbol."""
        return unicodedata.category(char)[0] in "PS"  # Punctuation, Symbols

    @staticmethod
    def _get_preserve_ranges() -> list[tuple[int, int]]:
        """Get the Unicode ranges that should be preserved.

        Returns:
            list: List of (start, end) tuples defining Unicode ranges to preserve.
        """
        return [
            # Emoji ranges
            (0x1F300, 0x1F6FF),  # Misc symbols and pictographs
            (0x2600, 0x26FF),  # Misc symbols
            (0x2700, 0x27BF),  # Dingbats
            (0x1F900, 0x1F9FF),  # Supplemental symbols and pictographs
            (0x1F1E6, 0x1F1FF),  # Regional indicator symbols (flags)
            # ASCII art and icon-like ranges
            (0x2500, 0x257F),  # Box drawing characters
            (0x2580, 0x259F),  # Block elements
            (0x2190, 0x21FF),  # Arrows
            (0x25A0, 0x25FF),  # Geometric shapes
        ]

    @staticmethod
    def _normalize_whitespace(message: str) -> str:
        """Normalize whitespace in the message."""
        # Replace sequences of whitespace (except newlines) with a single space
        return re.sub(r"[^\S\n]+", " ", message)

    @staticmethod
    def _remove_zero_width_chars(message: str) -> str:
        """Remove zero-width spaces and joiners from the message."""
        # Remove zero-width spaces and joiners
        return re.sub(r"[\u200B-\u200F\u202A-\u202E\u2060-\u2064\uFEFF]", "", message)

    @classmethod
    def message(
        cls, message: Optional[str], config: Optional[Config] = None
    ) -> Optional[str]:
        """Clean up the message from the chatbot to ensure it's a proper commit message.

        Args:
            message: The commit message to clean up.
            config: Configuration object with settings for the commit message generator.

        Returns:
            The cleaned commit message, or None if input was None.
        """
        if not message:
            return None

        message = cls._remove_impurities(message, config)

        # Normalize whitespace and remove excess blank lines
        return re.sub(r"\n{3,}", "\n\n", message)

    @classmethod
    def _remove_impurities(cls, message: str, config: Optional[Config]) -> str:
        """Remove impurities from the commit message.

        Applies multiple purification steps to clean up the message:
        - Removes code blocks with backticks
        - Removes introductions like "commit message:"
        - Removes explanatory text
        - Removes HTML/XML tags
        - Removes trailing disclaimers
        - Fixes conventional commit format issues
        - Cleans up broken textgraphy and characters
        - Normalizes whitespace

        Args:
            message: The commit message to clean up.
            config: Configuration object with settings for the commit message generator.

        Returns:
            The cleaned commit message.
        """

        # Remove code blocks with backticks
        message = cls.batrick(message)

        # Remove any "commit message:" or similar prefixes
        message = cls.commit_message_introduction(message)

        # Remove any explanatory text after the commit message
        message = cls.explanatory_message(message)

        # Remove any HTML/XML tags
        message = cls.htmlxml(message)

        # Remove any trailing disclaimers or instructions
        message = cls.disclaimers(message)

        # Fix conventional commit format issues
        message = cls.format(message, config)

        # Clean up broken textgraphy and characters
        return cls.text(message)

    @classmethod
    def icons(cls, message: str, icon: bool, config: Optional[Config] = None) -> str:
        """Handle emoji icons in the commit message based on configuration.

        Args:
            message: The commit message to process.
            icon: Whether icons are enabled.
            config: Configuration object with additional settings.

        Returns:
            The message with icons removed or replaced as appropriate.
        """
        if not icon:
            return cls._remove_emoji_icons(message)

        if cls._should_use_ascii_icons(config):
            return cls._replace_with_ascii_icons(message)

        return message

    @classmethod
    def _remove_emoji_icons(cls, message: str) -> str:
        """Remove emoji icons from the beginning of a commit message."""
        emoji_pattern = cls._get_emoji_pattern()
        return re.sub(emoji_pattern, r"\1", message)

    @classmethod
    def _get_emoji_pattern(cls) -> str:
        """Get the regex pattern for emoji icons."""
        return r"^(\s*)([\u2700-\u27BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\U0001F1E0-\U0001F1FF])\s+"

    @classmethod
    def _should_use_ascii_icons(cls, config: Optional[Config]) -> bool:
        """Determine if ASCII icons should be used instead of emoji icons."""
        if not config:
            return False

        return (
            hasattr(config, "ascii_only") and config.ascii_only
        ) or not can_display_emojis()

    @classmethod
    def _replace_with_ascii_icons(cls, message: str) -> str:
        """Replace emoji icons with ASCII alternatives based on commit type.

        Args:
            message: The commit message to process.

        Returns:
            str: The message with emoji icons replaced by ASCII alternatives.
        """
        # Extract the commit type from the message for accurate ASCII replacement
        commit_type = cls.extract_commit_type(message)

        # Remove any emojis from the message
        no_emoji = cls._remove_emoji_icons(message)

        # Add appropriate ASCII alternative if we found a commit type
        if commit_type:
            return f"{get_ascii_icon_for_type(commit_type)} {no_emoji}"

        return no_emoji

    @staticmethod
    def extract_commit_type(message: str) -> Optional[str]:
        """Extract the commit type from a commit message.

        Args:
            message: The commit message to analyze.

        Returns:
            The extracted commit type, or None if no type could be found.
        """
        # Skip if message is empty
        if not message:
            return None

        # Get valid commit types and clean message
        commit_types = Purify._get_valid_commit_types()
        clean_msg = Purify._remove_emojis_from_message(message)

        # Try different extraction methods in order
        commit_type = Purify._extract_type_with_scope(clean_msg, commit_types)
        if commit_type:
            return commit_type

        return Purify._extract_type_without_scope(clean_msg, commit_types)

    @staticmethod
    def _get_valid_commit_types() -> list[str]:
        """Get the list of valid conventional commit types."""
        return [
            "feat",
            "fix",
            "docs",
            "style",
            "refactor",
            "perf",
            "test",
            "build",
            "ci",
            "chore",
            "revert",
            "security",
        ]

    @staticmethod
    def _remove_emojis_from_message(message: str) -> str:
        """Remove emoji characters from the beginning of a message.

        Args:
            message: The message to process.

        Returns:
            The message with leading emojis removed.
        """
        return re.sub(
            r"^(\s*)([\u2700-\u27BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\U0001F1E0-\U0001F1FF])\s+",
            r"\1",
            message,
        )

    @staticmethod
    def _extract_type_with_scope(message: str, valid_types: list[str]) -> Optional[str]:
        """Extract commit type from a message with potential scope format.

        Looks for patterns like "feat(scope):" in the message.

        Args:
            message: The message to analyze.
            valid_types: List of valid commit types to check against.

        Returns:
            The extracted commit type if found and valid, otherwise None.
        """
        match = re.match(r"^(\w+)(\([\w-]*\))?:", message.lower())
        if match and match.group(1).lower() in valid_types:
            return match.group(1).lower()
        return None

    @staticmethod
    def _extract_type_without_scope(
        message: str, valid_types: list[str]
    ) -> Optional[str]:
        """Extract commit type from a message without scope format.

        Checks if the message starts with a valid type followed by a colon.

        Args:
            message: The message to analyze.
            valid_types: List of valid commit types to check against.

        Returns:
            The extracted commit type if found, otherwise None.
        """
        lower_message = message.lower()
        for commit_type in valid_types:
            if lower_message.startswith((f"{commit_type}:", f"{commit_type} :")):
                return commit_type
        return None
