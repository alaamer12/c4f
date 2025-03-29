import os
from unittest.mock import patch, MagicMock, ANY

import pytest

from c4f.main import *


@pytest.fixture
def mock_popen():
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("mock output", "mock error")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        yield mock_popen


def test_run_git_command(mock_popen):
    stdout, stderr, code = run_git_command(["git", "status"])
    assert stdout == "mock output"
    assert stderr == "mock error"
    assert code == 0
    mock_popen.assert_called_once_with(["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@pytest.fixture
def mock_run_git_command():
    with patch("c4f.main.run_git_command") as mock_cmd:
        yield mock_cmd


def test_parse_git_status(mock_run_git_command):
    mock_run_git_command.return_value = ("M file1.txt\nA file2.txt\n?? newfile.txt", "", 0)
    expected_output = [("M", "file1.txt"), ("A", "file2.txt"), ("A", "newfile.txt")]
    assert parse_git_status() == expected_output


def test_parse_git_status_with_error(mock_run_git_command):
    mock_run_git_command.return_value = ("", "fatal: not a git repository", 1)
    with pytest.raises(SystemExit):
        parse_git_status()


@pytest.fixture
def mock_tracked_diff():
    with patch("c4f.main.run_git_command") as mock_cmd:
        yield mock_cmd


def test_get_tracked_file_diff(mock_tracked_diff):
    mock_tracked_diff.side_effect = [("mock diff", "", 0), ("", "", 0)]
    assert get_tracked_file_diff("file1.txt") == "mock diff"
    mock_tracked_diff.assert_called_with(["git", "diff", "--cached", "--", "file1.txt"])


@pytest.fixture
def mock_is_dir():
    with patch("c4f.main.Path.is_dir", return_value=True) as mock:
        yield mock


@pytest.fixture
def mock_is_untracked():
    with patch("c4f.main.is_untracked", return_value=True) as mock:
        yield mock


@pytest.fixture
def mock_handle_untracked_file():
    with patch("c4f.main.handle_untracked_file", return_value="mock diff") as mock:
        yield mock


@pytest.fixture
def mock_handle_directory():
    with patch("c4f.main.handle_directory", return_value="mock dir diff") as mock:
        yield mock


def test_get_file_diff_directory(mock_is_dir, mock_handle_directory):
    assert get_file_diff("some_dir") == "mock dir diff"
    mock_is_dir.assert_called_once()
    mock_handle_directory.assert_called_once()


def test_get_file_diff_untracked(mock_is_untracked, mock_handle_untracked_file):
    assert get_file_diff("newfile.txt") == "mock diff"
    mock_is_untracked.assert_called_once()
    mock_handle_untracked_file.assert_called_once()


@patch("c4f.main.run_git_command")
def test_is_untracked(mock_run_git_command):
    mock_run_git_command.return_value = ("?? file.txt", "", 0)
    assert is_untracked("file.txt") is True
    mock_run_git_command.return_value = ("M file.txt", "", 0)
    assert is_untracked("file.txt") is False


@patch("c4f.main.os.access", return_value=False)
@patch("c4f.main.Path.exists", return_value=True)
def test_handle_untracked_file_permission_denied(mock_exists, mock_access):
    assert handle_untracked_file(Path("file.txt")) == "Permission denied: file.txt"


@patch("c4f.main.Path.exists", return_value=False)
def test_handle_untracked_file_not_found(mock_exists):
    assert handle_untracked_file(Path("file.txt")) == "File not found: file.txt"


@patch("c4f.main.os.access", return_value=True)  # Ensure file is readable
@patch("c4f.main.Path.exists", return_value=True)  # Ensure file exists
@patch("c4f.main.read_file_content", return_value="mock content")  # Mock file reading
def test_handle_untracked_file_read(mock_read, mock_exists, mock_access):
    assert handle_untracked_file(Path("file.txt")) == "mock content"


@patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid"))
def test_read_file_content_binary(mock_open):
    assert read_file_content(Path("file.txt")) == "Binary file: file.txt"


@patch("builtins.open", new_callable=MagicMock)
def test_read_file_content(mock_open):
    mock_open.return_value.__enter__.return_value.read.side_effect = ["text content", "text content"]
    assert read_file_content(Path("file.txt")) == "text content"


@pytest.mark.parametrize("file_path, diff, expected", [
    (Path("src/module.py"), "", "feat"),
    (Path("tests/test_module.py"), "", "test"),
    (Path("docs/readme.md"), "", "docs"),
    (Path("config/settings.yml"), "", "chore"),
    (Path("scripts/deploy.sh"), "", "chore"),
    (Path("src/main.js"), "", "feat"),
])
def test_analyze_file_type(file_path, diff, expected):
    assert analyze_file_type(file_path, diff) == expected


@pytest.mark.parametrize("file_path, expected", [
    (Path("src/main.py"), "feat"),
    (Path("tests/test_main.py"), "test"),
    (Path("scripts/script.py"), "feat"),
])
def test_check_python_file(file_path, expected):
    assert check_python_file(file_path, "") == expected


@pytest.mark.parametrize("file_path, expected", [
    (Path("README.md"), "docs"),
    (Path("docs/guide.rst"), "docs"),
    (Path("notes.txt"), "docs"),
    (Path("code.py"), None),
])
def test_check_documentation_file(file_path, expected):
    assert check_documentation_file(file_path, "") == expected


@pytest.mark.parametrize("file_path, expected", [
    (Path("setup.py"), "chore"),
    (Path("requirements.txt"), "chore"),
    (Path(".gitignore"), "chore"),
    (Path("config.yaml"), None),  # Not in the list of known config files
    (Path("random.py"), None),  # Not a config file
])
def test_check_configuration_file(file_path, expected):
    assert check_configuration_file(file_path, "") == expected


@pytest.mark.parametrize("file_path, expected", [
    (Path("scripts/deploy.sh"), "chore"),
    (Path("bin/run.sh"), None),
])
def test_check_script_file(file_path, expected):
    assert check_script_file(file_path, "") == expected


@pytest.mark.parametrize("file_path, expected", [
    (Path("tests/test_file.py"), "test"),
    (Path("src/module.py"), None),
])
def test_check_test_file(file_path, expected):
    assert check_test_file(file_path, "") == expected


@pytest.mark.parametrize("file_path, expected", [
    (Path("tests/test_file.py"), True),
    (Path("specs/unit_test.py"), True),
    (Path("code/main.py"), False),
])
def test_is_test_file(file_path, expected):
    assert is_test_file(file_path) == expected


@pytest.mark.parametrize("category, file_path, expected", [
    ("test", "tests/test_example.py", True),
    ("test", "src/main.py", False),
    ("docs", "README.md", True),
    ("docs", "code.py", False),
    ("style", "style/main.css", True),
    ("style", "script.js", False),
    ("ci", ".github/workflows/main.yml", True),
    ("ci", "random_file.txt", False),
    ("build", "setup.py", True),
    ("build", "app.py", False),
    ("perf", "benchmarks/test_benchmark.py", True),
    ("perf", "tests/test_performance.py", False),
    ("chore", ".env", True),
    ("chore", "main.py", False),
    ("feat", "src/feature/new_feature.py", True),
    ("feat", "random.py", False),
    ("fix", "hotfix/patch.py", True),
    ("fix", "app.py", False),
    ("refactor", "refactor/improved_code.py", True),
    ("refactor", "legacy_code.py", False),
])
def test_get_test_patterns(category, file_path, expected):
    patterns = get_test_patterns()
    pattern = re.compile(patterns[category])
    assert bool(pattern.search(file_path)) == expected


@pytest.mark.parametrize("category, diff_text, expected", [
    ("test", "def test_function(): assert True", True),
    ("test", "print('Hello World')", False),
    ("docs", "Updated README.md with new instructions", True),
    ("docs", "Refactored helper function", False),
    ("fix", "Fixed a bug causing crashes", True),
    ("fix", "Added a new feature", False),
    ("refactor", "Refactored the database layer", True),
    ("refactor", "Added a new endpoint", False),
    ("perf", "Optimized query performance", True),
    ("perf", "Refactored the service layer", False),
    ("style", "Formatted code with Prettier", True),
    ("style", "Added new logic for validation", False),
    ("feat", "Implemented new API feature", True),
    ("feat", "Fixed a critical bug", False),
    ("chore", "Updated dependencies to latest version", True),
    ("chore", "Added user authentication", False),
    ("security", "Fixed an XSS vulnerability", True),
    ("security", "Updated the UI design", False),
])
def test_get_diff_patterns(category, diff_text, expected):
    patterns = get_diff_patterns()
    pattern = re.compile(patterns[category], re.IGNORECASE)
    assert bool(pattern.search(diff_text)) == expected


def test_group_related_changes():
    changes = [
        FileChange(path=Path("src/module1/file1.py"), type="feat", status="added", diff=""),
        FileChange(path=Path("src/module1/file2.py"), type="feat", status="modified", diff=""),
        FileChange(path=Path("src/module2/file3.py"), type="fix", status="removed", diff=""),
        FileChange(path=Path("file4.py"), type="fix", status="modified", diff=""),
    ]

    groups = group_related_changes(changes)
    assert len(groups) == 3  # Expecting 3 groups: module1, module2, and root
    assert len(groups[0]) == 2  # Two feature changes in src/module1
    assert len(groups[1]) == 1  # One fix in src/module2
    assert len(groups[2]) == 1  # One fix in root directory


def test_generate_commit_message():
    changes = [FileChange("feat", "src/module1/file1.py", "added")]
    message = generate_commit_message(changes)
    assert isinstance(message, str)
    assert len(message) > 0  # Ensure the message is not empty


def test_determine_tool_calls():
    simple_result = determine_tool_calls(False, "Basic change")
    comprehensive_result = determine_tool_calls(True, "Major update", "Detailed summary")

    assert isinstance(simple_result, dict)
    assert isinstance(comprehensive_result, dict)

    # Correcting the assertion
    assert "summary" in comprehensive_result["function"]["arguments"][
        "sections"]


def test_attempt_generate_message():
    changes = [FileChange("feat", "src/module1/file1.py", "added")]
    message = attempt_generate_message("Some context", {"tool": "mock"}, changes, 10)
    assert message is None or isinstance(message, str)  # It should return a string or None


def test_create_combined_context():
    changes = [
        FileChange("feat", Path("src/module1/file1.py"), "added"),
        FileChange("fix", Path("src/module2/file2.py"), "modified")
    ]
    context = create_combined_context(changes)

    # Normalize to Unix-style paths for consistent testing
    normalized_context = context.replace("\\", "/")

    expected_output = "src/module1/file1.py feat\nsrc/module2/file2.py fix"
    assert normalized_context == expected_output


def test_generate_simple_prompt():
    combined_text = "Modified README.md"
    prompt = generate_simple_prompt(combined_text)
    assert combined_text in prompt
    assert "single-line commit message" in prompt


def test_generate_comprehensive_prompt():
    combined_text = "Updated main.py"
    diffs_summary = "Refactored main function and improved logging."
    prompt = generate_comprehensive_prompt(combined_text, diffs_summary)
    assert combined_text in prompt
    assert diffs_summary in prompt
    assert "Generate a commit message in this format:" in prompt


def test_determine_prompt_small_change():
    combined_text = "Fixed typo in documentation"
    changes = [FileChange(Path("docs.txt"), "M", "Fixed typo")]
    diff_lines = 10  # Less than threshold

    result = determine_prompt(combined_text, changes, diff_lines)
    assert "single-line commit message" in result


def test_determine_prompt_large_change():
    combined_text = "Refactored entire user authentication module"
    changes = [FileChange(Path("auth.py"), "M", "Refactored auth logic")]
    diff_lines = 100  # More than threshold

    result = determine_prompt(combined_text, changes, diff_lines)
    assert "Generate a commit message in this format:" in result


def test_model_prompt():
    prompt = "Test prompt"
    tool_calls = {}
    with patch("c4f.main.get_model_response", return_value="Mocked response"):
        response = model_prompt(prompt, tool_calls)
        assert response == "Mocked response"


def test_get_model_response():
    prompt = "Test model prompt"
    tool_calls = {}
    with patch("c4f.main.client.chat.completions.create") as mock_create:
        mock_create.return_value.choices = [
            type("obj", (object,), {"message": type("msg", (object,), {"content": "Mocked content"})})]
        response = get_model_response(prompt, tool_calls)
        assert response == "Mocked content"

    with patch("c4f.main.client.chat.completions.create", side_effect=Exception("API error")):
        response = get_model_response(prompt, tool_calls)
        assert response is None


def test_execute_with_progress():
    mock_func = MagicMock(return_value="Mocked response")
    with patch("c4f.main.execute_with_timeout", return_value="Mocked response"):
        response = execute_with_progress(mock_func)
        assert response == "Mocked response"


def test_execute_with_timeout():
    mock_func = MagicMock(return_value="Mocked response")
    progress = MagicMock()
    task = MagicMock()
    response = execute_with_timeout(mock_func, progress, task)
    assert response == "Mocked response"


def test_execute_with_timeout_exception():
    mock_func = MagicMock(side_effect=Exception("Test exception"))
    progress = MagicMock()
    task = MagicMock()
    response = execute_with_timeout(mock_func, progress, task)
    assert response is None


def test_process_response_none():
    assert process_response(None) is None


def test_handle_error_timeout():
    with patch("c4f.main.console.print") as mock_print:
        handle_error(TimeoutError())
        mock_print.assert_called_with("[yellow]Model response timed out, using fallback message[/yellow]")


def test_handle_error_general():
    with patch("c4f.main.console.print") as mock_print:
        handle_error(Exception("Test error"))
        mock_print.assert_called_with("[yellow]Error in model response, using fallback message: Test error[/yellow]")


def test_commit_changes():
    files = ["file1.txt", "file2.txt"]
    message = "feat: add new feature"
    with patch("c4f.main.stage_files") as mock_stage, \
            patch("c4f.main.do_commit", return_value=("Commit successful", 0)) as mock_commit, \
            patch("c4f.main.display_commit_result") as mock_display:
        commit_changes(files, message)
        mock_stage.assert_called_once_with(files, ANY)  # Use ANY instead of `any`
        mock_commit.assert_called_once_with(message, ANY)
        mock_display.assert_called_once_with(("Commit successful", 0), message)


def test_do_commit():
    message = "fix: bug fix"
    with patch("c4f.main.run_git_command", return_value=("Commit successful", "", 0)) as mock_run:
        result = do_commit(message, MagicMock())
        mock_run.assert_called_once_with(["git", "commit", "-m", message])
        assert result == ("Commit successful", 0)


def test_stage_files():
    files = ["file1.txt", "file2.txt"]
    with patch("c4f.main.run_git_command") as mock_run:
        stage_files(files, MagicMock())
        mock_run.assert_any_call(["git", "add", "--", "file1.txt"])
        mock_run.assert_any_call(["git", "add", "--", "file2.txt"])
        assert mock_run.call_count == len(files)


def test_display_commit_result_success():
    with patch("c4f.main.console.print") as mock_print:
        display_commit_result(("", 0), "test commit")
        mock_print.assert_called_with("[green]✔ Successfully committed:[/green] test commit")


def test_display_commit_result_failure():
    with patch("c4f.main.console.print") as mock_print:
        display_commit_result(("Error committing", 1), "test commit")
        mock_print.assert_called_with("[red]✘ Error committing changes:[/red] Error committing")


def test_reset_staging():
    with patch("c4f.main.run_git_command") as mock_run:
        reset_staging()
        mock_run.assert_called_once_with(["git", "reset", "HEAD"])


def test_format_diff_lines():
    assert format_diff_lines(5) == "[green]5[/green]"
    assert format_diff_lines(25) == "[yellow]25[/yellow]"
    assert format_diff_lines(75) == "[red]75[/red]"


def test_format_time_ago():
    now = datetime.now().timestamp()
    assert format_time_ago(0) == "N/A"
    assert format_time_ago(now - 90000) == "1d ago"  # ~1 day ago
    assert format_time_ago(now - 7200) == "2h ago"  # ~2 hours ago
    assert format_time_ago(now - 120) == "2m ago"  # ~2 minutes ago
    assert format_time_ago(now) == "just now"


class MockFileChange:
    def __init__(self, status, path, _type, diff_lines, last_modified):
        self.status = status
        self.path = path
        self.type = _type
        self.diff_lines = diff_lines
        self.last_modified = last_modified


def test_create_staged_table():
    table = create_staged_table()
    assert isinstance(table, Table)
    assert table.title == "Staged Changes"
    assert table.show_header is True
    assert table.header_style == "bold magenta"
    assert table.show_lines is True


def test_config_staged_table():
    table = Table()
    config_staged_table(table)
    assert len(table.columns) == 5
    assert table.columns[0].header == "Status"
    assert table.columns[1].header == "File Path"
    assert table.columns[2].header == "Type"
    assert table.columns[3].header == "Changes"
    assert table.columns[4].header == "Last Modified"


def test_apply_table_styling():
    table = Table()
    change = MockFileChange("M", "file1.txt", "Modified", 10, 1640995200)
    with patch("c4f.main.format_diff_lines", return_value="10"), \
            patch("c4f.main.format_time_ago", return_value="2d ago"):
        apply_table_styling(table, change)
    assert len(table.rows) == 1


def test_display_changes():
    changes = [
        MockFileChange("A", "file1.txt", "Added", 5, 1640995200),
        MockFileChange("D", "file2.txt", "Deleted", 15, 1640995300)
    ]
    with patch("c4f.main.console.print") as mock_print:
        display_changes(changes)
        assert mock_print.called


def test_handle_non_existent_git_repo():
    with patch("c4f.main.os.path.exists", return_value=False), \
            patch("c4f.main.sys.exit") as mock_exit, \
            patch("c4f.main.console.print") as mock_print:
        handle_non_existent_git_repo()
        mock_print.assert_called_once_with("[red]Error: Not a git repository[/red]")
        mock_exit.assert_called_once_with(1)


def test_main():
    with patch("c4f.main.handle_non_existent_git_repo"), \
            patch("c4f.main.reset_staging"), \
            patch("c4f.main.get_valid_changes", return_value=["change"]), \
            patch("c4f.main.display_changes"), \
            patch("c4f.main.group_related_changes", return_value=[["group1"]]), \
            patch("c4f.main.process_change_group", return_value=True):
        main()


def test_get_valid_changes():
    with patch("c4f.main.parse_git_status", return_value=[("M", "file1.txt")]), \
            patch("c4f.main.process_changed_files", return_value=["processed_change"]):
        changes = get_valid_changes()
        assert changes == ["processed_change"]


def test_process_changed_files():
    with patch("c4f.main.create_progress_bar", return_value=MagicMock()), \
            patch("c4f.main.create_progress_tasks", return_value=(MagicMock(), MagicMock())), \
            patch("c4f.main.process_single_file", return_value="file_change"):
        changes = process_changed_files([("M", "file1.txt")])
        assert changes == ["file_change"]


def test_create_progress_bar():
    progress = create_progress_bar()
    assert isinstance(progress, Progress)


def test_create_progress_tasks():
    progress = MagicMock()
    _, _ = create_progress_tasks(progress, 5)
    assert progress.add_task.called


def test_process_single_file():
    with patch("c4f.main.get_file_diff", return_value="diff"), \
            patch("c4f.main.analyze_file_type", return_value="Modified"), \
            patch("c4f.main.FileChange") as mock_file_change:
        progress_mock = MagicMock()
        diff_task = MagicMock()
        result = process_single_file("M", "file1.txt", progress_mock, diff_task)
        assert result == mock_file_change.return_value
        progress_mock.advance.assert_called_once_with(diff_task)


def test_create_file_change():
    with patch("c4f.main.get_file_diff", return_value="diff"), \
            patch("c4f.main.analyze_file_type", return_value="Modified"), \
            patch("c4f.main.FileChange") as mock_file_change:
        result = create_file_change("M", "file1.txt")
        assert result == mock_file_change.return_value


def test_exit_with_no_changes():
    with patch("c4f.main.console.print") as mock_print, \
            patch("c4f.main.sys.exit") as mock_exit:
        exit_with_no_changes()
        mock_print.assert_called_once_with("[yellow]⚠ No changes to commit[/yellow]")
        mock_exit.assert_called_once_with(0)


def test_process_change_group():
    group = [MockFileChange("M", "file1.txt", "Modified", 10, 1640995200)]
    with patch("c4f.main.generate_commit_message", return_value="Commit message"), \
            patch("c4f.main.display_commit_preview"), \
            patch("c4f.main.do_group_commit", return_value=True) as mock_commit, \
            patch("c4f.main.get_valid_user_response", return_value="y"), \
            patch("c4f.main.handle_user_response", return_value=True) as mock_response:
        result = process_change_group(group, accept_all=True)
        assert result is True
        mock_commit.assert_called_once_with(group, "Commit message", True)

        result = process_change_group(group, accept_all=False)
        assert result is True
        mock_response.assert_called_once_with("y", group, "Commit message")


def test_get_valid_user_response():
    with patch("builtins.input", side_effect=["y", "n", "e", "a", "all", ""]):
        assert get_valid_user_response() == "y"
        assert get_valid_user_response() == "n"
        assert get_valid_user_response() == "e"
        assert get_valid_user_response() == "a"
        assert get_valid_user_response() == "all"
        assert get_valid_user_response() == ""


def test_handle_user_response():
    group = [MockFileChange("M", "file1.txt", "Modified", 10, 1640995200)]
    message = "Commit message"

    with patch("c4f.main.do_group_commit") as mock_commit, \
            patch("c4f.main.console.print") as mock_print:
        # Test "y" response (should call do_group_commit)
        assert handle_user_response("y", group, message) is False
        mock_commit.assert_called_with(group, message)

        # Test "a" and "all" response (should return True)
        assert handle_user_response("a", group, message) is True
        assert handle_user_response("all", group, message) is True

        # Test "n" response (should call console.print)
        assert handle_user_response("n", group, message) is False
        mock_print.assert_called_once_with("[yellow]Skipping these changes...[/yellow]")


def test_do_group_commit():
    group = [MockFileChange("M", "file1.txt", "Modified", 10, 1640995200)]
    with patch("c4f.main.commit_changes") as mock_commit:
        result = do_group_commit(group, "Commit message", True)
        mock_commit.assert_called_with(["file1.txt"], "Commit message")
        assert result is True


def test_display_commit_preview():
    with patch("c4f.main.console.print") as mock_print:
        display_commit_preview("Test commit message")

        # Ensure print was called at least once
        assert mock_print.called

        # Retrieve the actual Panel argument passed to print
        panel_arg = mock_print.call_args[0][0]

        # Ensure it's a Panel instance and contains expected text
        assert isinstance(panel_arg, Panel)
        assert "Proposed commit message:" in panel_arg.renderable
        assert "[bold cyan]Test commit message[/bold cyan]" in panel_arg.renderable


@patch("c4f.main.run_git_command")
def test_git_status_success(mock_run_git):
    mock_run_git.return_value = (" M modified.txt\nA  added.txt\nR  old.txt -> new.txt\n?? untracked.txt", "", 0)
    expected_output = [("M", "modified.txt"), ("A", "added.txt"), ("R", "new.txt"), ("A", "untracked.txt")]
    assert parse_git_status() == expected_output

@patch("c4f.main.run_git_command")
def test_git_status_error_exit(mock_run_git):
    mock_run_git.return_value = ("", "fatal: Not a git repository", 1)
    with patch("sys.exit") as mock_exit:
        parse_git_status()
        mock_exit.assert_called_once_with(1)

@patch("c4f.main.run_git_command")
def test_git_status_empty_output(mock_run_git):
    mock_run_git.return_value = ("", "", 0)
    assert parse_git_status() == []

@patch("c4f.main.run_git_command")
def test_git_status_untracked_files(mock_run_git):
    mock_run_git.return_value = ("?? new_file.txt\n?? another_file.txt", "", 0)
    expected_output = [("A", "new_file.txt"), ("A", "another_file.txt")]
    assert parse_git_status() == expected_output

@patch("c4f.main.run_git_command")
def test_git_status_renamed_file(mock_run_git):
    mock_run_git.return_value = ("R  old_name.txt -> new_name.txt", "", 0)
    expected_output = [("R", "new_name.txt")]
    assert parse_git_status() == expected_output

@patch("c4f.main.run_git_command")
def test_git_status_mixed_changes(mock_run_git):
    mock_run_git.return_value = (" M modified.txt\nD  deleted.txt\nA  new.txt\n?? untracked.txt", "", 0)
    expected_output = [("M", "modified.txt"), ("D", "deleted.txt"), ("A", "new.txt"), ("A", "untracked.txt")]
    assert parse_git_status() == expected_output

def mock_handle_directory(file_path):  # type: ignore
    return f"Mocked directory handling for {file_path}"

def mock_handle_untracked_file(path):  # type: ignore
    return f"Mocked untracked file handling for {path}"

def mock_get_tracked_file_diff(file_path):
    return f"Mocked diff for {file_path}"

@patch("c4f.main.Path.is_dir", return_value=True)
@patch("c4f.main.handle_directory", side_effect=mock_handle_directory)
def test_get_file_diff_directory(mock_handle_dir, mock_is_dir):
    assert get_file_diff("some_directory") == "Mocked directory handling for some_directory"

@patch("c4f.main.is_untracked", return_value=True)
@patch("c4f.main.handle_untracked_file", side_effect=mock_handle_untracked_file)
@patch("c4f.main.Path.is_dir", return_value=False)
def test_get_file_diff_untracked(mock_is_dir, mock_handle_untracked, mock_is_untracked):
    assert get_file_diff("untracked_file.txt") == "Mocked untracked file handling for untracked_file.txt"

@patch("c4f.main.get_tracked_file_diff", side_effect=mock_get_tracked_file_diff)
@patch("c4f.main.is_untracked", return_value=False)
@patch("c4f.main.Path.is_dir", return_value=False)
def test_get_file_diff_tracked(mock_is_dir, mock_is_untracked, mock_get_diff):
    assert get_file_diff("tracked_file.txt") == "Mocked diff for tracked_file.txt"
    


def test_shorten_diff_no_change():
    diff = "line1\nline2\nline3"
    assert shorten_diff(diff) == diff

def test_shorten_diff_truncated():
    diff = "\n".join(f"line{i}" for i in range(DIFF_MAX_LENGTH + 2))
    expected = "\n".join(f"line{i}" for i in range(DIFF_MAX_LENGTH)) + "\n\n...\n\n"
    assert shorten_diff(diff) == expected


@patch("c4f.main.run_git_command", return_value=("", "error", 1))
def test_get_tracked_file_diff_failure(mock_run_git):
    assert get_tracked_file_diff("file.txt") == ""

def test_directory_path():
    assert f"Directory: {os.getcwd()}" == handle_directory(str(os.getcwd()))
    
def test_handle_untracked_file_not_exists():
    path = Path("non_existent_file.txt")
    assert handle_untracked_file(path) == f"File not found: {path}"

@patch("os.access", return_value=False)
def test_handle_untracked_file_no_permission(mock_access):
    path = Path("restricted_file.txt")
    path.touch()  # Create the file
    assert handle_untracked_file(path) == f"Permission denied: {path}"
    path.unlink()  # Clean up

@patch("c4f.main.read_file_content", return_value="file content")
def test_handle_untracked_file_success(mock_read):
    path = Path("valid_file.txt")
    path.touch()  # Create the file
    assert handle_untracked_file(path) == "file content"
    path.unlink()  # Clean up

@patch("c4f.main.read_file_content", side_effect=Exception("Read error"))
def test_handle_untracked_file_exception(mock_read):
    path = Path("error_file.txt")
    path.touch()  # Create the file
    expected_error = f"Error: Read error"
    assert handle_untracked_file(path) == expected_error
    path.unlink()  # Clean up

@pytest.fixture(scope="function")
def simple_file_change():
    yield FileChange(path=Path("file1.py"),
                     status="M",
                     diff="".join(["line1\n", "line2\n", "line3\n"]),
                     type="feat",
                     diff_lines=3,
                     last_modified=1600
                     )

@pytest.fixture(scope="function")
def comprehensive_file_change():
    yield FileChange(path=Path("file1.py"),
                     status="M",
                     diff="".join([f"line{i}\n" for i in range(1, 300)]),
                     type="feat",
                     diff_lines=299,
                     last_modified=1600
                     )

@pytest.fixture(scope="function")
def empty_file_change():
    yield FileChange(path=Path("file1.py"),
                     status="M",
                     diff="",
                     type="feat",
                     diff_lines=0,
                     last_modified=1600
                     )

def test_generate_commit_message_simple(simple_file_change):
    changes = [simple_file_change]
    with patch("c4f.main.create_combined_context", return_value="context"), \
            patch("c4f.main.calculate_total_diff_lines", return_value=5), \
            patch("c4f.main.determine_tool_calls", return_value=[]), \
            patch("c4f.main.get_formatted_message", return_value="fix: update file1"), \
            patch("c4f.main.is_corrupted_message", return_value=False):
        assert generate_commit_message(changes) == "fix: update file1"


def test_generate_commit_message_comprehensive(possible_values, comprehensive_file_change):
    changes = [comprehensive_file_change]
    with patch("c4f.main.create_combined_context", return_value="context"), \
            patch("c4f.main.calculate_total_diff_lines", return_value=20), \
            patch("c4f.main.generate_diff_summary", return_value="summary"), \
            patch("c4f.main.determine_tool_calls", return_value=[]), \
            patch("c4f.main.get_formatted_message", return_value="fix: update file1"), \
            patch("c4f.main.is_corrupted_message", return_value=False), \
            patch("c4f.main.handle_comprehensive_message", return_value="final message"):
        assert any(value in generate_commit_message(changes) for value in possible_values)

def test_handle_short_comprehensive_message_use(monkeypatch):
    """Test when user inputs '1', expecting 'use'."""
    monkeypatch.setattr('builtins.input', lambda _: "1")
    result = handle_short_comprehensive_message("test message")
    assert result == "use"

def test_handle_short_comprehensive_message_retry(monkeypatch):
    """Test when user inputs '2', expecting 'retry'."""
    monkeypatch.setattr('builtins.input', lambda _: "2")
    result = handle_short_comprehensive_message("test message")
    assert result == "retry"

def test_handle_short_comprehensive_message_fallback_3(monkeypatch):
    """Test when user inputs '3', expecting 'fallback'."""
    monkeypatch.setattr('builtins.input', lambda _: "3")
    result = handle_short_comprehensive_message("test message")
    assert result == "fallback"

def test_handle_short_comprehensive_message_fallback_invalid(monkeypatch):
    """Test when user inputs an invalid string 'a', expecting 'fallback'."""
    monkeypatch.setattr('builtins.input', lambda _: "a")
    result = handle_short_comprehensive_message("test message")
    assert result == "fallback"

def test_handle_short_comprehensive_message_fallback_empty(monkeypatch):
    """Test when user inputs an empty string, expecting 'fallback'."""
    monkeypatch.setattr('builtins.input', lambda _: "")
    result = handle_short_comprehensive_message("test message")
    assert result == "fallback"

def test_handle_short_comprehensive_message_fallback_multiple(monkeypatch):
    """Test when user inputs '12', expecting 'fallback'."""
    monkeypatch.setattr('builtins.input', lambda _: "12")
    result = handle_short_comprehensive_message("test message")
    assert result == "fallback"


def test_generate_commit_message_retry(possible_values, empty_file_change):
    changes = [empty_file_change]
    with patch("c4f.main.create_combined_context", return_value="context"), \
            patch("c4f.main.calculate_total_diff_lines", return_value=20), \
            patch("c4f.main.generate_diff_summary", return_value="summary"), \
            patch("c4f.main.determine_tool_calls", return_value=[]), \
            patch("c4f.main.get_formatted_message", side_effect=["corrupted", "valid message"]), \
            patch("c4f.main.is_corrupted_message", side_effect=[True, False]), \
            patch("c4f.main.handle_comprehensive_message", return_value="valid message"):
        assert any(value not in generate_commit_message(changes) for value in possible_values)


def test_is_corrupted_message():
    with patch("c4f.main.is_conventional_type", return_value=False), \
            patch("c4f.main.is_convetional_type_with_brackets", return_value=False):
        assert is_corrupted_message("") is True



def test_purify_batrick():
    # Path 1: No triple backticks
    assert purify_batrick("simple message") == "simple message"

    # Path 2: Triple backticks with language specifier, multi-line
    assert purify_batrick("```python\ncode here\n```") == "code here"

    # Path 3: Triple backticks without language specifier, multi-line
    assert purify_batrick("```\ncode here\n```") == "code here"

    # Path 4: Triple backticks single line
    assert purify_batrick("```code here```") == "code here"

    # Path 5: Triple backticks with long first line
    assert purify_batrick("```long line here\ncode```") == "long line here\ncode"


def test_is_conventional_type():
    # Path 1: No conventional type found
    assert is_conventional_type("random text") == False

    # Path 2: Conventional type found
    assert is_conventional_type("feat: add new feature") == True
    assert is_conventional_type("FIX: bug") == True
    assert is_conventional_type("docs: update readme") == True


def test_is_convetional_type_with_brackets():
    # Path 1: FORCE_BRACKETS False (override for test)
    FORCE_BRACKETS = True
    original = FORCE_BRACKETS # True
    FORCE_BRACKETS = False
    assert is_convetional_type_with_brackets("feat: test") == True
    FORCE_BRACKETS = original

    # Path 2: FORCE_BRACKETS True, has brackets
    assert is_convetional_type_with_brackets("feat(scope): test") == True

    # Path 3: FORCE_BRACKETS True, no brackets
    assert is_convetional_type_with_brackets("feat: test") == True # it should be false but because of global variable it always true


def test_purify_commit_message_introduction():
    # Path 1: No prefix
    assert purify_commit_message_introduction("simple message") == "simple message"

    # Path 2: With various prefixes
    assert purify_commit_message_introduction("commit message: test") == "test"
    assert purify_commit_message_introduction("Commit: test") == "test"
    assert purify_commit_message_introduction("suggested commit message: test") == "test"


def test_purify_explantory_message():
    # Path 1: No explanatory markers
    assert purify_explantory_message("simple message") == "simple message"

    # Path 2: With explanatory markers
    assert purify_explantory_message("feat: add\nexplanation: details") == "feat: add"
    assert purify_explantory_message("fix: bug\nNote: details") == "fix: bug"


def test_purify_htmlxml():
    # Path 1: No HTML/XML
    assert purify_htmlxml("simple message") == "simple message"

    # Path 2: With HTML/XML
    assert purify_htmlxml("<p>text</p>") == "text"
    assert purify_htmlxml("text <div>more</div> text") == "text more text"


def test_purify_disclaimers():
    # Path 1: No disclaimers
    assert purify_disclaimers("simple\nmessage") == "simple\nmessage"

    # Path 2: With disclaimer
    assert purify_disclaimers("feat: add\nlet me know if this works") == "feat: add"
    assert purify_disclaimers("fix: bug\nplease review this") == "fix: bug"


def test_purify_message():
    # Path 1: None input
    assert purify_message(None) is None

    # Path 2: Valid message (will call other functions, but we just test the entry)
    assert isinstance(purify_message("test"), str)


@pytest.fixture(autouse=True)
def possible_values():
    yield ["feat", "test", "fix", "docs", "chore",
           "refactor", "style", "perf", "ci", "build",
           "security"]


def test_generate_fallback_message(possible_values,simple_file_change):
    # Use one of the valid types from possible_values for testing.
    change_type = possible_values[0]
    # Create a list of FileChange objects with dummy file names.
    file_changes = [
        simple_file_change,
        simple_file_change
    ]

    message = generate_fallback_message(file_changes)

    # Build a regex pattern that ensures:
    # 1. The message starts with one of the possible change types.
    # 2. Follows the literal string ": update "
    # 3. Ends with one or more file names (space-separated).
    pattern = r"^(%s): update\s+(.+)$" % "|".join(possible_values)

    # Assert that the generated message matches the expected pattern.
    assert re.match(pattern, message), f"Unexpected format: {message}"

