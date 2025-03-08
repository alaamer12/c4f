#!/usr/bin/env python3
"""
Auto-Commit CLI Interface

This module provides a command-line interface for the auto-commit tool,
allowing users to customize the commit process through command-line arguments.

Usage:
    auto-commit [options]

Options:
    -y, --yes             Auto-accept all commits without prompting
    -m, --model MODEL     Specify the AI model to use (default: gpt_4o_mini)
    -p, --path PATH      Specify the repository path (default: current directory)
    -t, --threshold INT   Set the prompt threshold for diff lines (default: 80)
    --no-color           Disable colored output
    -v, --verbose        Enable verbose output
    --version           Show version information
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import g4f
from rich.console import Console

from . import main

def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Auto-Commit: An Intelligent Git Commit Message Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Auto-accept all commits without prompting"
    )

    parser.add_argument(
        "-m", "--model",
        type=str,
        default="gpt_4o_mini",
        choices=[m.name for m in g4f.models if hasattr(m, 'name')],
        help="AI model to use for generating commit messages"
    )

    parser.add_argument(
        "-p", "--path",
        type=str,
        default=".",
        help="Path to the Git repository (default: current directory)"
    )

    parser.add_argument(
        "-t", "--threshold",
        type=int,
        default=80,
        help="Prompt threshold for diff lines (default: 80)"
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
        help="Show version information"
    )

    return parser

def validate_path(path: str) -> Optional[Path]:
    """Validate the repository path."""
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}")
        return None
    
    git_dir = repo_path / ".git"
    if not git_dir.is_dir():
        print(f"Error: Not a git repository: {repo_path}")
        return None
    
    return repo_path

def configure_environment(args: argparse.Namespace) -> None:
    """Configure the environment based on command-line arguments."""
    # Configure model
    model_name = args.model.upper()
    if hasattr(g4f.models, model_name):
        main.MODEL = getattr(g4f.models, model_name)
    
    # Configure threshold
    main.PROMPT_THRESHOLD = args.threshold
    
    # Configure console
    if args.no_color:
        main.console = Console(force_terminal=False, color_system=None)

def main_cli() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Validate repository path
    repo_path = validate_path(args.path)
    if not repo_path:
        return 1

    # Change to repository directory
    original_cwd = os.getcwd()
    os.chdir(repo_path)

    try:
        # Configure environment
        configure_environment(args)
        
        # Run main with CLI arguments
        changes = main.get_valid_changes()
        if not changes:
            main.exit_with_no_changes()

        main.display_changes(changes)
        groups = main.group_related_changes(changes)
        
        for group in groups:
            if args.yes:  # Auto-accept all commits
                main.process_change_group(group, accept_all=True)
            else:
                accept_all = main.process_change_group(group)
                if accept_all:  # User chose to accept all
                    args.yes = True

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        if args.verbose:
            raise
        print(f"Error: {str(e)}")
        return 1
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    sys.exit(main_cli())
