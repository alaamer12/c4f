#!/usr/bin/env python3
import concurrent.futures
import os
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import TimeoutError
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Union, Literal, Dict, Any

import g4f
from g4f.client import Client
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

console = Console()
client = Client()

# ROOT = Path(__file__).parent
ROOT = r"E:\Projects\Languages\Python\auto-commit"
PROMPT_THRESHOLD = 80  # lines
FALLBACK_TIMEOUT = 10  # secs
MIN_COMPREHENSIVE_LENGTH = 50  # minimum length for comprehensive commit messages
ATTEMPT = 3  # number of attempts
MODEL_TYPE = Union[g4f.Model, g4f.models, str]
MODEL: MODEL_TYPE = g4f.models.gpt_4o_mini


@dataclass
class FileChange:
    path: Path
    status: str  # 'M' (modified), 'A' (added), 'D' (deleted), 'R' (renamed)
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


def parse_git_status() -> List[Tuple[str, str]]:
    stdout, stderr, code = run_git_command(["git", "status", "--porcelain"])
    if code != 0:
        console.print(f"[red]Error getting git status:[/red] {stderr}", style="bold red")
        sys.exit(1)

    changes = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        status, file_path = line[:2].strip(), line[3:].strip()
        # Handle untracked files (marked as '??')
        if status == "??":
            status = "A"  # Treat untracked as new/added files
        elif status == "R":
            file_path = file_path.split(" -> ")[1]
        changes.append((status, file_path))
    return changes


def get_file_diff(file_path: str) -> str:
    console.print(f"Getting diff for {file_path}...", style="blue")
    stdout, _, code = run_git_command(["git", "diff", "--cached", "--", file_path])
    if code == 0 and stdout:
        return stdout
    stdout, _, code = run_git_command(["git", "diff", "--", file_path])
    return stdout if code == 0 else ""


def analyze_file_type(file_path: Path, diff: str) -> str:
    """Determine the type of change based on file path and diff content."""
    type_checks = [
        ("chore", lambda: "scripts" in file_path.parts),
        ("test", lambda: is_test_file(file_path)),
        (check_file_path_patterns(file_path), lambda: True),
        (check_diff_patterns(diff), lambda: True),
        ("feat", lambda: True)  # Default case
    ]

    return next(_type for _type, condition in type_checks if condition())


def is_test_file(file_path: Path) -> bool:
    """Check if the file is in a dedicated test directory."""
    test_indicators = ("tests", "test", "spec", "specs", "pytest", "unittest", "mocks", "fixtures")
    return any(part.lower() in test_indicators for part in file_path.parts)


def check_file_path_patterns(file_path: Path) -> Optional[str]:
    """Check file name patterns to determine file type."""
    # Enhanced patterns based on conventional commits and industry standards
    type_patterns = {
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
    return check_patterns(str(file_path), type_patterns)


def check_diff_patterns(diff: str) -> Optional[str]:
    """Check diff content patterns to determine file type."""
    # Enhanced patterns for detecting commit types from diff content
    diff_patterns = {
        "test": r"\bdef test_|\bclass Test|\@pytest|\bunittest|\@test\b|\bit\(['\"]\w+['\"]|describe\(['\"]\w+['\"]|\bexpect\(|\bshould\b|\.spec\.|\.test\.|mock|stub|spy|assert|verify",
        "fix": r"\bfix|\bbug|\bissue|\berror|\bcrash|resolve|closes?\s+#\d+|\bpatch|\bsolve|\baddress|\bfailing|\bbroken|\bregression",
        "refactor": r"\brefactor|\bclean|\bmove|\brename|\brestructure|\brewrite|\bimprove|\bsimplify|\boptimize|\breorganize|\benhance|\bupdate|\bmodernize|\bsimplify|\streamline",
        "perf": r"\boptimiz|\bperformance|\bspeed|\bmemory|\bcpu|\bruntime|\bcache|\bfaster|\bslower|\blatency|\bthroughput|\bresponse time|\befficiency|\bbenchmark|\bprofile|\bmeasure|\bmetric|\bmonitoring",
        "style": r"\bstyle|\bformat|\blint|\bprettier|\beslint|\bindent|\bspacing|\bwhitespace|\btabs|\bspaces|\bsemicolons|\bcommas|\bbraces|\bparens|\bquotes|\bsyntax|\btypo|\bspelling|\bgrammar|\bpunctuation",
        "feat": r"\badd|\bnew|\bfeature|\bimplement|\bsupport|\bintroduce|\benable|\bcreate|\ballow|\bfunctionality",
        "docs": r"\bdocument|\bcomment|\bexplain|\bclari|\bupdate readme|\bupdate changelog|\bupdate license|\bupdate contribution|\bjsdoc|\btypedoc|\bdocstring|\bjavadoc|\bapidoc|\bswagger|\bopenapi|\bdocs",
        "chore": r"\bchore|\bupdate dependencies|\bupgrade|\bdowngrade|\bpackage|\bbump version|\brelease|\btag|\bversion|\bdeployment|\bci|\bcd|\bpipeline|\bworkflow|\bautomation|\bscripting|\bconfiguration|\bsetup|\bmaintenance|\bcleanup|\bupkeep|\borganize|\btrack|\bmonitor",
        "security": r"\bsecurity|\bvulnerability|\bcve|\bauth|\bauthentication|\bauthorization|\baccess control|\bpermission|\bprivilege|\bvalidation|\bsanitization|\bencryption|\bdecryption|\bhashing|\bcipher|\btoken|\bsession|\bxss|\bsql injection|\bcsrf|\bcors|\bfirewall|\bwaf|\bpen test|\bpenetration test|\baudit|\bscan|\bdetect|\bprotect|\bprevent|\bmitigate|\bremedy|\bfix|\bpatch|\bupdate|\bsecure|\bharden|\bfortify|\bsafeguard|\bshield|\bguard|\bblock|\bfilter|\bscreen|\bcheck|\bverify|\bvalidate|\bconfirm|\bensure|\bensure|\btrustworthy|\breliable|\brobust|\bresilient|\bimmune|\bimpervious|\binvulnerable"
    }
    return check_patterns(diff.lower(), diff_patterns)


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
        message = attempt_generate_message(combined_context, tool_calls, changes, total_diff_lines)
        if not message:
            continue

        if is_comprehensive:
            result = handle_comprehensive_message(message, changes)
            if result == "retry":
                continue
            if result:
                return result
        else:
            return message

    return generate_fallback_message(changes)


def determine_tool_calls(is_comprehensive: bool, combined_text: str, diffs_summary: str = "") -> Dict[str, Any]:
    if is_comprehensive:
        return create_comprehensive_tool_call(combined_text, diffs_summary)
    else:
        return create_simple_tool_call(combined_text)


def attempt_generate_message(combined_context: str, tool_calls: Dict[str, Any], changes: List[FileChange],
                             total_diff_lines: int) -> Optional[str]:
    prompt = determine_prompt(combined_context, changes, total_diff_lines)
    return model_prompt(prompt, tool_calls)


def handle_comprehensive_message(message: Optional[str], changes: List[FileChange]) -> (
        Optional)[Union[str, Literal["retry"]]]:
    if not message:
        return None

    if len(message) < MIN_COMPREHENSIVE_LENGTH:
        action = handle_short_comprehensive_message(message)
        if action == "use":
            return message
        elif action == "retry":
            return "retry"
        else:
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
        f"File: {change.path}\nStatus: {change.status}\nChanges:\n{change.diff}\n"
        for change in changes
    ])


def determine_prompt(combined_text: str, changes: List[FileChange], diff_lines: int) -> str:
    # For small changes (less than 50 lines), use a simple inline commit message
    if diff_lines < PROMPT_THRESHOLD:
        return generate_simple_prompt(combined_text)

    # For larger changes, create a comprehensive commit message with details
    diffs_summary = generate_diff_summary(changes)

    return generate_comprehensive_prompt(combined_text, diffs_summary)


def generate_simple_prompt(combined_text):
    return f"""
        Analyze these file changes and generate a conventional commit message:
        {combined_text}
        Respond with only a single-line commit message following conventional commits format.
        Keep it brief and focused on the main change.
        """


def generate_comprehensive_prompt(combined_text, diffs_summary):
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

    Respond with ONLY the commit message, no explanations.
    """


def model_prompt(prompt: str, tool_calls: Dict[str, Any]) -> str:
    return execute_with_progress(get_model_response, prompt, tool_calls)


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
    message = response.strip().split("\n")[0] if '\n' in response else response.strip()
    console.print(f"[dim]Generated message:[/dim] [cyan]{message}[/cyan]")
    return message


def handle_error(error: Exception) -> None:
    if isinstance(error, TimeoutError):
        console.print("[yellow]Model response timed out, using fallback message[/yellow]")
    else:
        console.print(f"[yellow]Error in model response, using fallback message: {str(error)}[/yellow]")
    return None


def commit_changes(files: List[str], message: str):
    with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            TaskProgressColumn(),
            console=console
    ) as progress:
        stage_files(files, progress)
        commit_result = perform_commit(message, progress)

    display_commit_result(commit_result, message)


def stage_files(files: List[str], progress: Progress):
    stage_task = progress.add_task("Staging files...", total=len(files))
    for file_path in files:
        run_git_command(["git", "add", "--", file_path])
        progress.advance(stage_task)


def perform_commit(message: str, progress: Progress) -> Tuple[str, int]:
    commit_task = progress.add_task("Committing changes...", total=1)
    _, stderr, code = run_git_command(["git", "commit", "-m", message])
    progress.advance(commit_task)
    return stderr, code


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

    now = datetime.now().timestamp()
    diff = now - timestamp

    if diff < 60:
        return "just now"
    elif diff < 3600:
        minutes = int(diff / 60)
        return f"{minutes}m ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours}h ago"
    else:
        days = int(diff / 86400)
        return f"{days}d ago"


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


def handle_non_existent_git_repo():
    os.chdir(ROOT)
    if not os.path.exists(".git"):
        console.print("[red]Error: Not a git repository[/red]")
        sys.exit(1)


def main():
    handle_non_existent_git_repo()
    reset_staging()
    changes = get_valid_changes()
    if not changes:
        exit_with_no_changes()

    display_changes(changes)
    change_groups = group_related_changes(changes)

    for group in change_groups:
        process_change_group(group)


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


def process_change_group(group):
    message = generate_commit_message(group)
    display_commit_preview(message)
    response = input("Proceed with commit? (Y/n/e to edit): ").lower().strip()
    while response not in ["y", "n", "e", ""]:
        response = input("Invalid response. Proceed with commit? (Y/n/e to edit): ").lower()
    if response == "y" or response == "":
        commit_changes([str(change.path) for change in group], message)
    elif response == "n":
        console.print("[yellow]Skipping these changes...[/yellow]")
    elif response == "e":
        message = input("Enter new commit message: ")
        commit_changes([str(change.path) for change in group], message)
    else:
        console.print("[red]Something went wrong. Exiting...[/red]")
        sys.exit(1)


def display_commit_preview(message):
    console.print(Panel(
        f"Proposed commit message:\n[bold cyan]{message}[/bold cyan]",
        title="Commit Preview",
        border_style="blue"
    ))


if __name__ == "__main__":
    main()
