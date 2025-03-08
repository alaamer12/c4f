from pathlib import Path

import pytest
from auto_commit import (
    FileChange,
    analyze_file_type,
    check_file_path_patterns,
    check_diff_patterns,
    group_related_changes,
    generate_commit_message,
)


def test_file_change_initialization():
    """Test FileChange dataclass initialization and post-init processing."""
    path = Path("test.py")
    status = "M"
    diff = "- old line\n+ new line\n"

    file_change = FileChange(path=path, status=status, diff=diff)

    assert file_change.path == path
    assert file_change.status == status
    assert file_change.diff == diff
    assert file_change.diff_lines == 2


def test_analyze_file_type_test_file():
    """Test detection of test files."""
    test_paths = [
        Path("tests/test_core.py"),
        Path("src/tests/unit_test.py"),
        Path("app/specs/feature.spec.js"),
    ]

    for path in test_paths:
        assert analyze_file_type(path, "") == "test"


def test_analyze_file_type_documentation():
    """Test detection of documentation files."""
    doc_paths = [
        Path("docs/README.md"),
        Path("API.rst"),
        Path("CHANGELOG.md"),
    ]

    for path in doc_paths:
        assert analyze_file_type(path, "") == "docs"


def test_check_file_path_patterns():
    """Test file path pattern matching."""
    patterns = {
        Path("src/features/new.py"): "feat",
        Path("tests/test_core.py"): "test",
        Path("docs/api.md"): "docs",
        Path(".github/workflows/ci.yml"): "ci",
        Path("Dockerfile"): "build",
    }

    for path, expected_type in patterns.items():
        assert check_file_path_patterns(path) == expected_type


def test_check_diff_patterns():
    """Test diff content pattern matching."""
    patterns = {
        "fix: resolve null pointer exception": "fix",
        "test: add unit tests for core module": "test",
        "perf: optimize database queries": "perf",
        "docs: update API documentation": "docs",
    }

    for diff, expected_type in patterns.items():
        result = check_diff_patterns(diff)
        assert result == expected_type


def test_group_related_changes():
    """Test grouping of related file changes."""
    changes = [
        FileChange(Path("src/feature1.py"), "M", "diff1", type="feat"),
        FileChange(Path("src/feature2.py"), "A", "diff2", type="feat"),
        FileChange(Path("tests/test1.py"), "M", "diff3", type="test"),
        FileChange(Path("docs/api.md"), "M", "diff4", type="docs"),
    ]

    groups = group_related_changes(changes)

    assert len(groups) == 3  # feat, test, and docs groups
    assert any(len(g) == 2 for g in groups)  # feat group should have 2 files
    assert any(len(g) == 1 for g in groups)  # test group should have 1 file
    assert any(len(g) == 1 for g in groups)  # docs group should have 1 file


@pytest.mark.asyncio
async def test_generate_commit_message(mock_g4f_response):
    """Test commit message generation."""
    changes = [
        FileChange(Path("src/feature1.py"), "M", "diff1", type="feat"),
        FileChange(Path("src/feature2.py"), "A", "diff2", type="feat"),
    ]

    message = generate_commit_message(changes)
    assert message is not None
    assert message.startswith("feat")
    assert len(message) > 0


def test_generate_commit_message_fallback():
    """Test fallback commit message generation."""
    changes = [
        FileChange(Path("src/feature1.py"), "M", "diff1", type="feat"),
    ]

    # Mock g4f to raise an exception
    with pytest.patch('g4f.client.Client.chat.completions.create', side_effect=Exception("API Error")):
        message = generate_commit_message(changes)
        assert message == "feat: update feature1.py"
