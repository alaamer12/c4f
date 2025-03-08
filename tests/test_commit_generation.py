from pathlib import Path

import pytest
from auto_commit import (
    FileChange,
    generate_commit_message,
    create_combined_context,
    calculate_total_diff_lines,
    generate_diff_summary,
    determine_prompt,
    generate_simple_prompt,
    generate_comprehensive_prompt,
)


@pytest.fixture
def sample_changes():
    """Create sample file changes for testing."""
    return [
        FileChange(
            path=Path("src/feature.py"),
            status="M",
            diff="@@ -1,4 +1,6 @@\n def old_function():\n     pass\n+def new_function():\n+    return True",
            type="feat"
        ),
        FileChange(
            path=Path("tests/test_feature.py"),
            status="A",
            diff="@@ -0,0 +1,5 @@\n+def test_new_function():\n+    assert new_function() is True",
            type="test"
        )
    ]


def test_create_combined_context(sample_changes):
    """Test creation of combined context from changes."""
    context = create_combined_context(sample_changes)

    assert "src/feature.py" in context
    assert "tests/test_feature.py" in context
    assert "Modified" in context
    assert "Added" in context


def test_calculate_total_diff_lines(sample_changes):
    """Test calculation of total diff lines."""
    total_lines = calculate_total_diff_lines(sample_changes)

    # Count actual lines in the diffs
    expected_lines = sum(len(change.diff.strip().splitlines()) for change in sample_changes)
    assert total_lines == expected_lines


def test_generate_diff_summary(sample_changes):
    """Test generation of diff summary."""
    summary = generate_diff_summary(sample_changes)

    assert "src/feature.py" in summary
    assert "tests/test_feature.py" in summary
    assert "Status: M" in summary
    assert "Status: A" in summary
    assert "def new_function()" in summary
    assert "def test_new_function()" in summary


@pytest.mark.parametrize("diff_lines,expected_type", [
    (30, "simple"),
    (100, "comprehensive")
])
def test_determine_prompt(sample_changes, diff_lines, expected_type):
    """Test prompt determination based on diff size."""
    prompt = determine_prompt(
        combined_text="Sample changes",
        changes=sample_changes,
        diff_lines=diff_lines
    )

    if expected_type == "simple":
        assert "brief" in prompt.lower()
        assert "single-line" in prompt.lower()
    else:
        assert "detailed" in prompt.lower()
        assert "bullet points" in prompt.lower()


def test_generate_simple_prompt():
    """Test generation of simple commit message prompt."""
    context = "Modified src/feature.py: Added new function"
    prompt = generate_simple_prompt(context)

    assert "conventional commit" in prompt.lower()
    assert "brief" in prompt.lower()
    assert context in prompt


def test_generate_comprehensive_prompt():
    """Test generation of comprehensive commit message prompt."""
    context = "Modified multiple files"
    diffs = "Detailed changes in files..."
    prompt = generate_comprehensive_prompt(context, diffs)

    assert "conventional" in prompt.lower()
    assert "detailed" in prompt.lower()
    assert "bullet points" in prompt.lower()
    assert context in prompt
    assert diffs in prompt


@pytest.mark.asyncio
async def test_generate_commit_message_small_change(mock_g4f_response):
    """Test commit message generation for small changes."""
    changes = [
        FileChange(
            path=Path("src/small_change.py"),
            status="M",
            diff="@@ -1 +1 @@\n-old\n+new",
            type="fix"
        )
    ]

    message = generate_commit_message(changes)
    assert message is not None
    assert message.startswith(("fix:", "feat:"))  # Should be conventional commit format


@pytest.mark.asyncio
async def test_generate_commit_message_large_change(mock_g4f_response):
    """Test commit message generation for large changes."""
    # Create a large diff
    large_diff = "\n".join([f"line {i}" for i in range(100)])
    changes = [
        FileChange(
            path=Path("src/large_change.py"),
            status="M",
            diff=large_diff,
            type="feat"
        )
    ]

    message = generate_commit_message(changes)
    assert message is not None
    assert message.startswith(("feat:", "fix:"))
    assert len(message.splitlines()) > 1  # Should be multi-line for large changes


def test_generate_commit_message_with_breaking_change(mock_g4f_response):
    """Test commit message generation with breaking changes."""
    breaking_diff = """@@ -1,5 +1,5 @@
-def old_api(param1, param2):
+def new_api(param1):
     # Breaking change: removed param2
     pass"""

    changes = [
        FileChange(
            path=Path("src/api.py"),
            status="M",
            diff=breaking_diff,
            type="feat"
        )
    ]

    message = generate_commit_message(changes)
    assert message is not None
    assert "BREAKING CHANGE" in message.upper()


def test_generate_commit_message_error_handling():
    """Test error handling in commit message generation."""
    changes = [
        FileChange(
            path=Path("src/error.py"),
            status="M",
            diff="some changes",
            type="fix"
        )
    ]

    # Mock g4f to simulate an error
    with pytest.patch('g4f.client.Client.chat.completions.create', side_effect=Exception("API Error")):
        message = generate_commit_message(changes)
        assert message is not None
        assert message.startswith("fix: update error.py")  # Should use fallback format
