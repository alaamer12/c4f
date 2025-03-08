import os
from pathlib import Path

from auto_commit import (
    run_git_command,
    parse_git_status,
    get_file_diff,
    commit_changes,
    stage_files,
    reset_staging,
)
from rich.progress import Progress


def test_run_git_command(temp_git_repo):
    """Test running Git commands."""
    os.chdir(temp_git_repo)

    # Test valid command
    stdout, stderr, code = run_git_command(["git", "status"])
    assert code == 0
    assert stdout.strip()
    assert not stderr

    # Test invalid command
    stdout, stderr, code = run_git_command(["git", "invalid-command"])
    assert code != 0
    assert stderr


def test_parse_git_status(git_repo_with_changes):
    """Test parsing Git status output."""
    os.chdir(git_repo_with_changes.working_dir)

    # Make some changes to test different statuses
    (Path(git_repo_with_changes.working_dir) / "new_file.txt").write_text("new content")
    (Path(git_repo_with_changes.working_dir) / "new_feature.py").write_text("modified content")

    changes = parse_git_status()

    assert changes
    assert any(status == "??" for status, _ in changes)  # Untracked file
    assert any(status == "M" for status, _ in changes)  # Modified file


def test_get_file_diff(git_repo_with_changes):
    """Test getting file diffs."""
    os.chdir(git_repo_with_changes.working_dir)

    # Create a new file with content
    test_file = Path(git_repo_with_changes.working_dir) / "test_diff.txt"
    test_file.write_text("initial content")

    # Stage and commit the file
    git_repo_with_changes.index.add([str(test_file)])
    git_repo_with_changes.index.commit("Add test file")

    # Modify the file
    test_file.write_text("modified content")

    # Get the diff
    diff = get_file_diff(str(test_file))

    assert diff
    assert "-initial content" in diff
    assert "+modified content" in diff


def test_commit_changes(git_repo_with_changes):
    """Test committing changes."""
    os.chdir(git_repo_with_changes.working_dir)

    # Create and modify a test file
    test_file = Path(git_repo_with_changes.working_dir) / "commit_test.txt"
    test_file.write_text("test content")

    # Commit the changes
    files = [str(test_file)]
    message = "test: add commit test file"

    commit_changes(files, message)

    # Verify the commit
    latest_commit = git_repo_with_changes.head.commit
    assert latest_commit.message == message
    assert "commit_test.txt" in latest_commit.stats.files


def test_stage_files(git_repo_with_changes, capsys):
    """Test staging files."""
    os.chdir(git_repo_with_changes.working_dir)

    # Create test files
    files = []
    for i in range(3):
        file_path = Path(git_repo_with_changes.working_dir) / f"stage_test_{i}.txt"
        file_path.write_text(f"test content {i}")
        files.append(str(file_path))

    # Create a progress bar for testing
    with Progress() as progress:
        stage_files(files, progress)

    # Verify files are staged
    status = git_repo_with_changes.git.status(porcelain=True)
    for file in files:
        assert Path(file).name in status


def test_reset_staging(git_repo_with_changes):
    """Test resetting staged changes."""
    os.chdir(git_repo_with_changes.working_dir)

    # Create and stage a test file
    test_file = Path(git_repo_with_changes.working_dir) / "reset_test.txt"
    test_file.write_text("test content")
    git_repo_with_changes.index.add([str(test_file)])

    # Verify file is staged
    status_before = git_repo_with_changes.git.status(porcelain=True)
    assert "reset_test.txt" in status_before

    # Reset staging
    reset_staging()

    # Verify file is unstaged
    status_after = git_repo_with_changes.git.status(porcelain=True)
    assert "?? reset_test.txt" in status_after  # File should be untracked after reset
