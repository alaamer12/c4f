"""
Auto-Commit: An Intelligent Git Commit Message Generator

This module provides an automated solution for generating meaningful Git commit messages
based on the changes in your repository. It analyzes file changes, categorizes them by type,
and generates descriptive commit messages using AI assistance.
"""

import concurrent.futures
import os
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from concurrent.futures import TimeoutError
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Union, Literal, Dict, Any, Final, Callable

import g4f  # type: ignore
from g4f.client import Client  # type: ignore
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

console = Console()
client = Client()

MODEL_TYPE = Union[g4f.Model, g4f.models, str]

# ROOT = Path(__file__).parent
FORCE_BRACKETS = False
if FORCE_BRACKETS:
    warnings.warn("Forcing brackets can lead to longer commit message generation and failures.", UserWarning)

PROMPT_THRESHOLD: Final[int] = 80  # lines
FALLBACK_TIMEOUT: Final[int] = 10  # secs
MIN_COMPREHENSIVE_LENGTH: Final[int] = 50  # minimum length for comprehensive commit messages
ATTEMPT: Final[int] = 3  # number of attempts
DIFF_MAX_LENGTH: Final[int] = 100
MODEL: Final[MODEL_TYPE] = g4f.models.gpt_4o_mini

__dir__ = ["main", "FORCE_BRACKETS", "FALLBACK_TIMEOUT", "ATTEMPT", "MODEL"]

@dataclass
class FileChange:
    path: Path
    status: Literal["M", "A", "D", "R"]
    diff: str
    type: Optional[str] = None  # 'feat', 'fix', 'docs', etc.
    diff_lines: int = 0
    last_modified: float = 0.0

    def __post_init__(self):
        self.diff_lines = len(self.diff.strip().splitlines())
        self.last_modified = os.path.getmtime(self.path) if os.path.exists(self.path) else 0.0


def run_git_command(command: List[str]) -> Tuple[str, str, int]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode


def get_root_git_workspace() -> Path:
    return Path(__file__).parent


def parse_git_status() -> List[Tuple[str, str]]:
    stdout, stderr, code = run_git_command(["git", "status", "--porcelain"])
    if code != 0:
        console.print(f"[red]Error getting git status:[/red] {stderr}", style="bold red")
        sys.exit(1)

    changes = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        status, file_path = line[:2].strip(), line[2:].strip()
        # Handle untracked files (marked as '??')
        if status == "??":
            status = "A"  # Treat untracked as new/added files
        elif status == "R":
            file_path = file_path.split(" -> ")[1]
        changes.append((status, file_path))
    return changes


def get_file_diff(file_path: str) -> str:
    console.print(f"Getting diff for {file_path}...", style="blue")
    path = Path(file_path)

    if path.is_dir():
        return handle_directory(file_path)

    if is_untracked(file_path):
        return handle_untracked_file(path)

    return get_tracked_file_diff(file_path)


def shorten_diff(diff: str) -> str:
    lines = diff.strip().splitlines()

    if len(lines) > DIFF_MAX_LENGTH:
        lines = lines[:DIFF_MAX_LENGTH] + ["\n...\n\n"]

    return "\n".join(lines)


def get_tracked_file_diff(file_path: str) -> str:
    stdout, _, code = run_git_command(["git", "diff", "--cached", "--", file_path])
    if code == 0 and stdout:
        return stdout
    stdout, _, code = run_git_command(["git", "diff", "--", file_path])
    return stdout if code == 0 else ""


def handle_directory(file_path: str) -> str:
    return f"Directory: {file_path}"


def is_untracked(file_path: str) -> bool:
    stdout, _, code = run_git_command(["git", "status", "--porcelain", file_path])
    return code == 0 and stdout.startswith("??")


def handle_untracked_file(path: Path) -> str:
    if not path.exists():
        return f"File not found: {path}"
    if not os.access(path, os.R_OK):
        return f"Permission denied: {path}"

    try:
        return read_file_content(path)
    except Exception as e:
        console.print(f"[red]Error reading file {path}:[/red] {e}", style="bold red")
        return f"Error: {str(e)}"


def read_file_content(path: Path) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(1024)
            if '\0' in content:
                return f"Binary file: {path}"
            f.seek(0)
            return f.read()
    except UnicodeDecodeError:
        return f"Binary file: {path}"


def analyze_file_type(file_path: Path, diff: str) -> str:
    """Determine the type of change based on file path and diff content."""
    file_type_checks: list[Callable[[Path, str], Optional[str]]] = [
        check_python_file,
        check_documentation_file,
        check_configuration_file,
        check_script_file,
        check_test_file,
        check_file_path_patterns,
        check_diff_patterns,
    ]

    for _check in file_type_checks:
        result = _check(file_path, diff)
        if result:
            return result

    return "feat"  # Default case if no other type matches


def check_python_file(file_path: Path, _: str) -> Optional[str]:
    if file_path.suffix == '.py':
        return 'test' if 'test' in str(file_path).lower() else 'feat'
    return None


def check_documentation_file(file_path: Path, _: str) -> Optional[str]:
    if file_path.suffix in ['.md', '.rst', '.txt']:
        return 'docs'
    return None


def check_configuration_file(file_path: Path, _: str) -> Optional[str]:
    config_files = ['.gitignore', 'requirements.txt', 'setup.py', 'setup.cfg', 'pyproject.toml']
    if file_path.name in config_files:
        return 'chore'
    return None


def check_script_file(file_path: Path, _: str) -> Optional[str]:
    return 'chore' if "scripts" in file_path.parts else None


def check_test_file(file_path: Path, _: str) -> Optional[str]:
    return 'test' if is_test_file(file_path) else None


def is_test_file(file_path: Path) -> bool:
    """Check if the file is in a dedicated test directory."""
    test_indicators = ("tests", "test", "spec", "specs", "pytest", "unittest", "mocks", "fixtures")
    return any(part.lower() in test_indicators for part in file_path.parts)


def check_file_path_patterns(file_path: Path, _: str) -> Optional[str]:
    """Check file name patterns to determine file type."""
    # Enhanced patterns based on conventional commits and industry standards
    type_patterns = get_test_patterns()
    return check_patterns(str(file_path), type_patterns)


def check_diff_patterns(diff: Path, _: str) -> Optional[str]:
    """Check diff content patterns to determine file type."""
    # Enhanced patterns for detecting commit types from diff content
    diff_patterns = get_diff_patterns()
    return check_patterns(str(diff).lower(), diff_patterns)


def get_test_patterns() -> dict[str, str]:
    return {
        "test": r"^tests?/|^testing/|^__tests?__/|^test_.*\.py$|^.*_test\.py$|^.*\.spec\.[jt]s$|^.*\.test\.[jt]s$",
        "docs": r"^docs?/|\.md$|\.rst$|\.adoc$|\.txt$|^(README|CHANGELOG|CONTRIBUTING|HISTORY|AUTHORS|SECURITY)(\.[^/]+)?$|^(COPYING|LICENSE)(\.[^/]+)?$|^(api|docs|documentation)/|.*\.docstring$|^jsdoc/|^typedoc/",
        "style": r"\.(css|scss|sass|less|styl)$|^styles?/|^themes?/|\.editorconfig$|\.prettierrc|\.eslintrc|\.flake8$|\.style\.yapf$|\.isort\.cfg$|setup\.cfg$|^\.stylelintrc|^\.prettierrc|^\.prettier\.config\.[jt]s$",
        "ci": r"^\.github/workflows/|^\.gitlab-ci|\.travis\.yml$|^\.circleci/|^\.azure-pipelines|^\.jenkins|^\.github/actions/|\.pre-commit-config\.yaml$|^\.gitlab/|^\.buildkite/|^\.drone\.yml$|^\.appveyor\.yml$",
        "build": r"^pyproject\.toml$|^setup\.(py|cfg)$|^requirements/|^requirements.*\.txt$|^poetry\.lock$|^Pipfile(\.lock)?$|^package(-lock)?\.json$|^yarn\.lock$|^Makefile$|^Dockerfile$|^docker-compose\.ya?ml$|^MANIFEST\.in$|^rollup\.config\.[jt]s$|^webpack\.config\.[jt]s$|^babel\.config\.[jt]s$|^tsconfig\.json$|^vite\.config\.[jt]s$|^\.babelrc$|^\.npmrc$",
        "perf": r"^benchmarks?/|^performance/|\.*.profile$|^profiling/|^\.?cache/|^\.?benchmark/",
        "chore": r"^\.env(\.|$)|\.(ini|cfg|conf|json|ya?ml|toml|properties)$|^config/|^settings/|^\.git.*$|^\.husky/|^\.vscode/|^\.idea/|^\.editorconfig$|^\.env\.example$|^\.nvmrc$",
        "feat": r"^src/|^app/|^lib/|^modules/|^feature/|^features/|^api/|^services/|^controllers/|^routes/|^middleware/|^models/|^schemas/|^types/|^utils/|^helpers/|^core/|^internal/|^pkg/|^cmd/",
        "fix": r"^hotfix/|^bugfix/|^patch/|^fix/",
        "refactor": r"^refactor/|^refactoring/|^redesign/",
        "security": r"^security/|^auth/|^authentication/|^authorization/|^access control/|^permission/|^privilege/|^validation/|^sanitization/|^encryption/|^decryption/|^hashing/|^cipher/|^token/|^session/|^xss/|^sql injection/|^csrf/|^cors/|^firewall/|^waf/|^pen test/|^penetration test/|^audit/|^scan/|^detect/|^protect/|^prevent/|^mitigate/|^remedy/|^fix/|^patch/|^update/|^secure/|^harden/|^fortify/|^safeguard/|^shield/|^guard/|^block/|^filter/|^screen/|^check/|^verify/|^validate/|^confirm/|^ensure/|^ensure/|^trustworthy/|^reliable/|^robust/|^resilient/|^immune/|^impervious/|^invulnerable"
    }


def get_diff_patterns() -> dict[str, str]:
    return {
        "test": r"\bdef test_|\bclass Test|\@pytest|\bunittest|\@test\b|\bit\(['\"]\w+['\"]|describe\(['\"]\w+['\"]|\bexpect\(|\bshould\b|\.spec\.|\.test\.|mock|stub|spy|assert|verify",
        "fix": r"\bfix|\bbug|\bissue|\berror|\bcrash|resolve|closes?\s+#\d+|\bpatch|\bsolve|\baddress|\bfailing|\bbroken|\bregression",
        "refactor": r"\brefactor|\bclean|\bmove|\brename|\brestructure|\brewrite|\bimprove|\bsimplify|\boptimize|\breorganize|\benhance|\bupdate|\bmodernize|\bsimplify|\streamline",
        "perf": r"\boptimiz|\bperformance|\bspeed|\bmemory|\bcpu|\bruntime|\bcache|\bfaster|\bslower|\blatency|\bthroughput|\bresponse time|\befficiency|\bbenchmark|\bprofile|\bmeasure|\bmetric|\bmonitoring",
        "style": r"\bstyle|\bformat|\blint|\bprettier|\beslint|\bindent|\bspacing|\bwhitespace|\btabs|\bspaces|\bsemicolons|\bcommas|\bbraces|\bparens|\bquotes|\bsyntax|\btypo|\bspelling|\bgrammar|\bpunctuation",
        "feat": r"\badd|\bnew|\bfeature|\bimplement|\bsupport|\bintroduce|\benable|\bcreate|\ballow|\bfunctionality",
        "docs": r"\bupdate(d)?\s*README\.md|\bupdate(d)? readme|\bdocument|\bcomment|\bexplain|\bclari|\bupdate changelog|\bupdate license|\bupdate contribution|\bjsdoc|\btypedoc|\bdocstring|\bjavadoc|\bapidoc|\bswagger|\bopenapi|\bdocs",
        "security": r"\bsecurity|\bvulnerability|\bcve|\bauth|\bauthentication|\bauthorization|\baccess control|\bpermission|\bprivilege|\bvalidation|\bsanitization|\bencryption|\bdecryption|\bhashing|\bcipher|\btoken|\bsession|\bxss|\bsql injection|\bcsrf|\bcors|\bfirewall|\bwaf|\bpen test|\bpenetration test|\baudit|\bscan|\bdetect|\bprotect|\bprevent|\bmitigate|\bremedy|\bfix|\bpatch|\bupdate (?!UI|design)|\bsecure|\bharden|\bfortify|\bsafeguard|\bshield|\bguard|\bblock|\bfilter|\bscreen|\bcheck|\bverify|\bvalidate|\bconfirm|\bensure|\btrustworthy|\breliable|\brobust|\bresilient|\bimmune|\bimpervious|\binvulnerable",
        "chore": r"\bchore|\bupdate dependencies|\bupgrade|\bdowngrade|\bpackage|\bbump version|\brelease|\btag|\bversion|\bdeployment|\bci|\bcd|\bpipeline|\bworkflow|\bautomation|\bscripting|\bconfiguration|\bsetup|\bmaintenance|\bcleanup|\bupkeep|\borganize|\btrack|\bmonitor",
    }


def check_patterns(text: str, patterns: dict) -> Optional[str]:
    """Check if text matches any pattern in the given dictionary."""
    for type_name, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            return type_name
    return None


def group_related_changes(changes: List[FileChange]) -> List[List[FileChange]]:
    groups = defaultdict(list)
    for change in changes:
        key = f"{change.type}_{change.path.parent}" if change.path.parent.name != '.' else change.type
        groups[key].append(change)
    return list(groups.values())


def generate_commit_message(changes: List[FileChange]) -> str:
    combined_context = create_combined_context(changes)
    total_diff_lines = calculate_total_diff_lines(changes)
    is_comprehensive = total_diff_lines >= PROMPT_THRESHOLD
    diffs_summary = generate_diff_summary(changes) if is_comprehensive else ""

    tool_calls = determine_tool_calls(is_comprehensive, combined_context, diffs_summary)

    for _ in range(ATTEMPT):
        message = get_formatted_message(combined_context, tool_calls, changes, total_diff_lines)

        if is_corrupted_message(message):
            continue

        if is_comprehensive:
            result = handle_comprehensive_message(message, changes)
            if result in ["retry", "r"]:
                continue
            if result:
                return result
        else:
            return message

    return generate_fallback_message(changes)


def is_corrupted_message(message: str) -> bool:
    return (not message
            or not is_conventional_type(message)
            or not is_conventional_type_with_brackets(message)
            )


def get_formatted_message(combined_context, tool_calls, changes, total_diff_lines):
    # Attempt to get Message
    message = attempt_generate_message(combined_context, tool_calls, changes, total_diff_lines)

    # Purify Message
    message = purify_message(message)

    return message


def purify_batrick(message: str) -> str:
    if message.startswith("```") and message.endswith("```"):
        # Check if there's a language specifier like ```git or ```commit
        lines = message.split("\n")
        if len(lines) > 2:
            # If first line has just the opening backticks with potential language specifier
            if lines[0].startswith("```") and len(lines[0]) <= 10:
                message = "\n".join(lines[1:-1])
            else:
                message = message[3:-3]
        else:
            message = message[3:-3]

    return message


def is_conventional_type(message: str) -> bool:
    if not any(x in message.lower() for x in
                ["feat", "test", "fix", "docs", "chore",
                "refactor", "style", "perf", "ci", "build",
                "security"
                ]
               ):
        return False
    return True


def is_conventional_type_with_brackets(message: str) -> bool:
    if not FORCE_BRACKETS:
        return True

    first_word: str = message.split()[0]
    if "(" not in first_word and ")" not in first_word:
        return False

    return True


def purify_commit_message_introduction(message: str) -> str:
    prefixes_to_remove = [
        "commit message:", "commit:", "git commit message:",
        "suggested commit message:", "here's a commit message:",
        "here is the commit message:", "here is a commit message:"
    ]

    for prefix in prefixes_to_remove:
        if message.lower().startswith(prefix):
            message = message[len(prefix):].strip()

    return message


def purify_explantory_message(message: str) -> str:
    explanatory_markers = [
        "explanation:", "explanation of changes:", "note:", "notes:",
        "this commit message", "i hope this helps", "please let me know"
    ]

    for marker in explanatory_markers:
        if marker in message.lower():
            parts = message.lower().split(marker)
            message = parts[0].strip()

    return message


def purify_htmlxml(message: str) -> str:
    return re.sub(r'<[^>]+>', '', message)


def purify_disclaimers(message: str) -> str:
    lines = message.strip().split('\n')
    filtered_lines = []
    for line in lines:
        if any(x in line.lower() for x in
               ["let me know if", "please review", "is this helpful", "hope this", "i've followed"]):
            break
        filtered_lines.append(line)

    return '\n'.join(filtered_lines).strip()


def purify_message(message: Optional[str]) -> Optional[str]:
    """Clean up the message from the chatbot to ensure it's a proper commit message."""
    if not message:
        return None

    # Remove code blocks with backticks
    message = purify_batrick(message)

    # Remove any "commit message:" or similar prefixes
    message = purify_commit_message_introduction(message)

    # Remove any explanatory text after the commit message
    message = purify_explantory_message(message)

    # Remove any HTML/XML tags
    message = purify_htmlxml(message)

    # Remove any trailing disclaimers or instructions
    message = purify_disclaimers(message)

    # Normalize whitespace and remove excess blank lines
    message = re.sub(r'\n{3,}', '\n\n', message)

    return message


def determine_tool_calls(is_comprehensive: bool, combined_text: str, diffs_summary: str = "") -> Dict[str, Any]:
    if is_comprehensive:
        return create_comprehensive_tool_call(combined_text, diffs_summary)
    else:
        return create_simple_tool_call(combined_text)


def create_simple_tool_call(combined_text: str) -> Dict[str, Any]:
    return {
        "function": {
            "name": "generate_commit",
            "arguments": {
                "files": combined_text,
                "style": "conventional",
                "format": "inline",
                "max_length": 72,
                "include_scope": True,
                "strict_conventional": True
            }
        },
        "type": "function"
    }


def create_comprehensive_tool_call(combined_text: str, diffs_summary: str) -> Dict[str, Any]:
    return {
        "function": {
            "name": "generate_commit",
            "arguments": {
                "files": combined_text,
                "diffs": diffs_summary,
                "style": "conventional",
                "format": "detailed",
                "max_first_line": 72,
                "include_scope": True,
                "include_breaking": True,
                "include_references": True,
                "sections": [
                    "summary",
                    "changes",
                    "breaking",
                    "references"
                ],
                "strict_conventional": True
            }
        },
        "type": "function"
    }


def attempt_generate_message(combined_context: str, tool_calls: Dict[str, Any], changes: List[FileChange],
                             total_diff_lines: int) -> Optional[str]:
    prompt = determine_prompt(combined_context, changes, total_diff_lines)
    return model_prompt(prompt, tool_calls)


def handle_comprehensive_message(message: Optional[str], changes: List[FileChange]) -> (
        Optional)[Union[str, Literal["retry"]]]:
    if not message:
        return None

    if len(message) < MIN_COMPREHENSIVE_LENGTH:
        action = handle_short_comprehensive_message(message).strip().lower()
        while action not in ["use", 'u', 'retry', 'r', 'fallback', 'f']:
            action = input("\nChoose an option between the options above: or leave it empty to use: ").strip()
        if action in ["use", 'u', ""]:
            return message
        elif action in ["retry", 'r']:
            return "retry"
        elif action in ["fallback", 'f']:
            return generate_fallback_message(changes)
    return message


def create_combined_context(changes: List[FileChange]) -> str:
    return "\n".join([f"{change.status} {change.path}" for change in changes])


def calculate_total_diff_lines(changes: List[FileChange]) -> int:
    return sum(change.diff_lines for change in changes)


def handle_short_comprehensive_message(model_message: str) -> str:
    console.print("\n[yellow]Warning: Generated commit message seems too brief for a large change.[/yellow]")
    console.print(f"Generated message: [cyan]{model_message}[/cyan]\n")

    table = Table(show_header=False, style="blue")
    table.add_row("[1] Use this message anyway")
    table.add_row("[2] Try generating again")
    table.add_row("[3] Use auto-generated message")
    console.print(table)

    choice = input("\nChoose an option (1-3): ").strip()

    if choice == "1":
        return "use"
    elif choice == "2":
        return "retry"
    else:
        return "fallback"


def generate_fallback_message(changes: List[FileChange]) -> str:
    return f"{changes[0].type}: update {' '.join(str(c.path.name) for c in changes)}"


def generate_diff_summary(changes):
    return "\n".join([
        shorten_diff(f"File [{i + 1}]: {change.path}\nStatus: {change.status}\nChanges:\n{change.diff}\n")
        for i, change in enumerate(changes)
    ])


def determine_prompt(combined_text: str, changes: List[FileChange], diff_lines: int) -> str:
    # For small changes (less than 50 lines), use a simple inline commit message
    if diff_lines < PROMPT_THRESHOLD:
        return generate_simple_prompt(combined_text)

    # For larger changes, create a comprehensive commit message with details
    diffs_summary = generate_diff_summary(changes)

    return generate_comprehensive_prompt(combined_text, diffs_summary)


def generate_simple_prompt(combined_text):
    force_brackets_line = "Please use brackets with conventional commits [e.g. feat(main): ...]" if FORCE_BRACKETS else ""
    return f"""
        Analyze these file changes and generate a conventional commit message:
        {combined_text}
        Respond with only a single-line commit message following conventional commits format.
        Keep it brief and focused on the main change.
        {force_brackets_line}
        """


def generate_comprehensive_prompt(combined_text, diffs_summary):
    force_brackets_line = "Please use brackets with conventional commits [e.g. feat(main): ...]" if FORCE_BRACKETS else ""
    return f"""
    Analyze these file changes and generate a detailed conventional commit message:

    Changed Files:
    {combined_text}

    Detailed Changes:
    {diffs_summary}

    Generate a commit message in this format:
    <type>[optional scope]: <description>

    [optional body]
    - Bullet points summarizing main changes
    - Include any breaking changes

    [optional footer]

    Rules:
    1. First line should be a concise summary (50-72 chars)
    2. Use present tense ("add" not "added")
    3. Include relevant scope if changes are focused
    4. Add detailed bullet points for significant changes
    5. Mention breaking changes if any
    6. Reference issues/PRs if applicable
    
    {force_brackets_line}
    Respond with ONLY the commit message, no explanations.
    """


def model_prompt(prompt: str, tool_calls: Dict[str, Any]) -> str:
    return execute_with_progress(get_model_response, prompt, tool_calls)


def get_model_response(prompt: str, tool_calls: Dict[str, Any]) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Follow instructions precisely and respond concisely."},
                {"role": "user", "content": prompt}
            ],
            tool_calls=[tool_calls]  # Wrap in list as API expects array of tool calls
        )
        return response.choices[0].message.content if response and response.choices else None
    except Exception as e:
        console.print(f"[red]Error in model response: {str(e)}[/red]")
        return None


def execute_with_progress(func, *args):
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Waiting for model response...", total=None)
        return execute_with_timeout(func, progress, task, *args)


def execute_with_timeout(func, progress, task, *args, timeout=FALLBACK_TIMEOUT):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(func, *args)
        try:
            response = future.result(timeout=timeout)
            return process_response(response)
        except (TimeoutError, Exception) as e:
            handle_error(e)
            return None
        finally:
            progress.remove_task(task)


def process_response(response: Optional[str]) -> Optional[str]:
    if not response:
        return None
    message = response.strip()
    first_line = message.split("\n")[0] if '\n' in message else message
    console.print(f"[dim]Generated message:[/dim] [cyan]{first_line}[/cyan]")
    return message


def handle_error(error: Exception) -> None:
    if isinstance(error, TimeoutError):
        console.print("[yellow]Model response timed out, using fallback message[/yellow]")
    else:
        console.print(f"[yellow]Error in model response, using fallback message: {str(error)}[/yellow]")
    return None


def commit_changes(files: List[str], message: str):
    """Commit the changes to the specified files with the given message."""
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
    ) as progress:
        # Stage files
        stage_files(files, progress)

        # Commit changes
        commit_result = do_commit(message, progress)

        # Display result
        display_commit_result(commit_result, message)


def do_commit(message: str, progress: Progress) -> Tuple[str, int]:
    """Perform the actual git commit."""
    task = progress.add_task("Committing changes...", total=1)
    stdout, _, code = run_git_command(["git", "commit", "-m", message])
    progress.update(task, advance=1)
    return stdout, code


def stage_files(files: List[str], progress: Progress):
    stage_task = progress.add_task("Staging files...", total=len(files))
    for file_path in files:
        run_git_command(["git", "add", "--", file_path])
        progress.advance(stage_task)


def display_commit_result(result: Tuple[str, int], message: str):
    stderr, code = result
    if code == 0:
        console.print(f"[green]✔ Successfully committed:[/green] {message}")
    else:
        console.print(f"[red]✘ Error committing changes:[/red] {stderr}")


def reset_staging():
    run_git_command(["git", "reset", "HEAD"])


def format_diff_lines(lines: int) -> str:
    if lines < 10:
        return f"[green]{lines}[/green]"
    elif lines < 50:
        return f"[yellow]{lines}[/yellow]"
    else:
        return f"[red]{lines}[/red]"


def format_time_ago(timestamp: float) -> str:
    if timestamp == 0:
        return "N/A"

    diff = datetime.now().timestamp() - timestamp
    time_units = [
        (86400, "d"),
        (3600, "h"),
        (60, "m"),
        (0, "just now")
    ]

    for seconds, unit in time_units:
        if diff >= seconds:
            if seconds == 0:
                return unit
            count = int(diff / seconds)
            return f"{count}{unit} ago"

    # Time units is None
    return "N/A"


def create_staged_table() -> Table:
    return Table(
        title="Staged Changes",
        show_header=True,
        header_style="bold magenta",
        show_lines=True
    )


def config_staged_table(table) -> None:
    table.add_column("Status", justify="center", width=8)
    table.add_column("File Path", width=40)
    table.add_column("Type", justify="center", width=10)
    table.add_column("Changes", justify="right", width=10)
    table.add_column("Last Modified", justify="right", width=12)


def apply_table_styling(table, change):
    status_color = {
        'M': 'yellow',
        'A': 'green',
        'D': 'red',
        'R': 'blue'
    }.get(change.status, 'white')

    table.add_row(
        f"[{status_color}]{change.status}[/{status_color}]",
        str(change.path),
        f"[green]{change.type}[/green]",
        format_diff_lines(change.diff_lines),
        format_time_ago(change.last_modified)
    )


def display_changes(changes: List[FileChange]):
    # Create table
    table = create_staged_table()

    # Config the table
    config_staged_table(table)

    for change in changes:
        apply_table_styling(table, change)

    console.print(table)


def find_git_root() -> Path:
    """Find the root directory of the git repository.
    
    Returns:
        Path: The absolute path to the git repository root
        
    Raises:
        FileNotFoundError: If not in a git repository
    """
    try:
        # Use git rev-parse to find the root of the repository
        stdout, stderr, code = run_git_command(["git", "rev-parse", "--show-toplevel"])
        if code != 0:
            raise FileNotFoundError(f"Git error: {stderr}")
        
        # Get the absolute path and normalize it
        root_path = Path(stdout.strip()).resolve()
        
        if not root_path.exists() or not (root_path / ".git").exists():
            raise FileNotFoundError("Not a git repository")
            
        return root_path
        
    except Exception as e:
        raise FileNotFoundError(f"Failed to determine git root: {str(e)}")


def handle_non_existent_git_repo() -> None:
    """Verify git repository exists and change to its root directory."""
    try:
        root = find_git_root()
        try:
            os.chdir(root)
        except OSError as e:
            console.print(f"[red]Error: Failed to change directory: {str(e)}[/red]")
            sys.exit(1)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)


def main():
    handle_non_existent_git_repo()
    reset_staging()
    changes = get_valid_changes()
    if not changes:
        exit_with_no_changes()

    display_changes(changes)
    groups = group_related_changes(changes)

    accept_all = False
    for group in groups:
        if accept_all:
            process_change_group(group, accept_all=True)
        else:
            accept_all = process_change_group(group)


def get_valid_changes():
    changed_files = parse_git_status()
    if not changed_files:
        return []

    return process_changed_files(changed_files)


def process_changed_files(changed_files):
    changes = []
    with create_progress_bar() as progress:
        analyze_task, diff_task = create_progress_tasks(progress, len(changed_files))
        for status, file_path in changed_files:
            file_change = process_single_file(status, file_path, progress, diff_task)
            if file_change:
                changes.append(file_change)
            progress.advance(analyze_task)
    return changes


def create_progress_bar():
    return Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        TaskProgressColumn(),
        console=console
    )


def create_progress_tasks(progress, total):
    analyze_task = progress.add_task("Analyzing files...", total=total)
    diff_task = progress.add_task("Getting file diffs...", total=total)
    return analyze_task, diff_task


def process_single_file(status, file_path, progress, diff_task):
    path = Path(file_path)
    diff = get_file_diff(file_path)
    progress.advance(diff_task)
    if diff:
        file_type = analyze_file_type(path, diff)
        return FileChange(path, status, diff, file_type)
    return None


def create_file_change(status, file_path):
    path = Path(file_path)
    diff = get_file_diff(file_path)
    file_type = analyze_file_type(path, diff)
    return FileChange(path, status, diff, file_type) if diff else None


def exit_with_no_changes():
    console.print("[yellow]⚠ No changes to commit[/yellow]")
    sys.exit(0)


def process_change_group(group: List["FileChange"], accept_all: bool = False) -> bool:
    message = generate_commit_message(group)

    # Style Message
    md = Markdown(message)

    # Capture the rendered Markdown output
    with console.capture() as capture:
        console.print(md, end="")  # Ensure no extra newline
    rendered_message = capture.get()

    display_commit_preview(rendered_message)  # Pass the properly rendered string

    if accept_all:
        return do_group_commit(group, message, True)

    response = get_valid_user_response()
    return handle_user_response(response, group, message)


def get_valid_user_response() -> str:
    prompt = "Proceed with commit? ([Y/n] [/e] to edit [all/a] for accept all): "
    while True:
        response = input(prompt).lower().strip()
        if response in ["y", "n", "e", "a", "all", ""]:
            return response
        prompt = "Invalid response. " + prompt


def handle_user_response(response: str, group: List[FileChange], message: str) -> bool:
    actions = {
        "a": lambda: do_group_commit(group, message, True),
        "all": lambda: do_group_commit(group, message, True),
        "y": lambda: do_group_commit(group, message),
        "": lambda: do_group_commit(group, message),
        "n": lambda: console.print("[yellow]Skipping these changes...[/yellow]"),
        "e": lambda: do_group_commit(group, input("Enter new commit message: "))
    }

    if response not in actions:
        console.print("[red]Invalid response. Exiting...[/red]")
        sys.exit(1)

    actions[response]()
    return True if response in ["a", "all"] else False


def do_group_commit(group: List[FileChange], message: str, accept_all: bool = False) -> bool:
    """Commit a group of changes and return whether to accept all future commits."""
    files = [str(change.path) for change in group]
    commit_changes(files, message)
    return accept_all


def display_commit_preview(message):
    console.print(Panel(
        f"Proposed commit message:\n[bold cyan]{message}[/bold cyan]",
        title="Commit Preview",
        border_style="blue"
    ))


if __name__ == "__main__":
    main()
