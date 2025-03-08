import shutil
from pathlib import Path
from typing import Generator, Dict

import git
import pytest


@pytest.fixture(scope="session")
def temp_git_repo(tmp_path_factory) -> Generator[Path, None, None]:
    """Create a temporary Git repository for testing."""
    repo_dir = tmp_path_factory.mktemp("git_repo")
    repo = git.Repo.init(repo_dir)

    # Configure git user for commits
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    yield repo_dir
    shutil.rmtree(repo_dir)


@pytest.fixture
def sample_files(temp_git_repo: Path) -> Dict[str, Path]:
    """Create sample files with different types of changes."""
    files = {}

    # Feature change - New Python file
    feature_file = temp_git_repo / "new_feature.py"
    feature_file.write_text("""def calculate_sum(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b
""")
    files['feature'] = feature_file

    # Bug fix - Python file with a fix
    fix_file = temp_git_repo / "bug_fix.py"
    fix_file.write_text("""def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""")
    files['fix'] = fix_file

    # Documentation change - Markdown file
    docs_file = temp_git_repo / "docs" / "api.md"
    docs_file.parent.mkdir(exist_ok=True)
    docs_file.write_text("""# API Documentation

## Functions

### calculate_sum
Adds two numbers together.

### multiply
Multiplies two numbers.
""")
    files['docs'] = docs_file

    # Test file
    test_file = temp_git_repo / "tests" / "test_math.py"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("""import pytest

def test_calculate_sum():
    assert calculate_sum(2, 3) == 5

def test_multiply():
    assert multiply(2, 3) == 6
""")
    files['test'] = test_file

    # Configuration change
    config_file = temp_git_repo / "config.yml"
    config_file.write_text("""version: 1.0
debug: false
api_key: ${API_KEY}
""")
    files['config'] = config_file

    return files


@pytest.fixture
def git_repo_with_changes(temp_git_repo: Path, sample_files: Dict[str, Path]) -> git.Repo:
    """Create a Git repository with various types of changes."""
    repo = git.Repo(temp_git_repo)

    # Initial commit
    repo.index.add([str(f.relative_to(temp_git_repo)) for f in sample_files.values()])
    repo.index.commit("Initial commit")

    # Make some changes
    sample_files['feature'].write_text(
        sample_files['feature'].read_text() + "\ndef subtract(a: int, b: int) -> int:\n    return a - b\n")
    sample_files['fix'].write_text(
        sample_files['fix'].read_text().replace("raise ValueError", "raise ZeroDivisionError"))
    sample_files['docs'].write_text(
        sample_files['docs'].read_text() + "\n### subtract\nSubtracts second number from first.\n")

    return repo


@pytest.fixture
def mock_g4f_response(monkeypatch):
    """Mock the g4f response for testing."""

    class MockResponse:
        class Choice:
            def __init__(self, content):
                self.message = type('Message', (), {'content': content})()

        def __init__(self, content):
            self.choices = [self.Choice(content)]

    class MockClient:
        @staticmethod
        def chat():
            return type('ChatCompletions', (), {
                'create': lambda **kwargs: MockResponse("feat: add new mathematical operations")
            })()

    monkeypatch.setattr('g4f.client.Client', MockClient)
