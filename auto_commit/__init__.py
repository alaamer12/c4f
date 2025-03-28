"""
Auto-Commit: An Intelligent Git Commit Message Generator

This package provides tools for automatically generating meaningful Git commit messages
using AI assistance and smart change detection.
"""

__version__ = "1.0.0"
__author__ = "Alaamer"

from .main import (FileChange,
    generate_commit_message,
    create_combined_context,
    calculate_total_diff_lines,
    generate_diff_summary,
    determine_prompt,
    generate_simple_prompt,
    generate_comprehensive_prompt,
   analyze_file_type,
   check_file_path_patterns,
   check_diff_patterns,
   group_related_changes,
   run_git_command,
    parse_git_status,
    get_file_diff,
    commit_changes,
    stage_files,
    reset_staging,)
from .cli import main_cli

__all__ = ['main_cli']