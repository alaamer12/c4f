"""
C4F (Commit For Free) - An Intelligent Git Commit Message Generator

A sophisticated Git commit message generator that uses AI to create meaningful, 
conventional commit messages based on your code changes.

Key Features:
    - Automatic detection of changed, added, and deleted files
    - Smart categorization of changes (feat, fix, docs, etc.)
    - AI-powered commit message generation
    - Interactive commit process with manual override options
    - Support for both individual and batch commits
    - Handles binary files, directories, and permission issues gracefully

Usage:
    Run the command in a Git repository:
    $ c4f

    The tool will:
    1. Detect all changes in the repository
    2. Group related changes together
    3. Generate commit messages for each group
    4. Allow user interaction to approve, edit, or skip commits
    5. Commit the changes with the generated/edited messages

Commands:
    - [Y/Enter]: Accept and commit changes
    - [n]: Skip these changes
    - [e]: Edit the commit message
    - [a/all]: Accept all remaining commits without prompting

Project Information:
    Author: Alaamer
    Email: ahmedmuhamed12@gmail.com
    License: MIT
    Repository: https://github.com/alaamer12/c4f
    Documentation: https://github.com/alaamer12/c4f
    Python Support: >=3.11
    Keywords: git, commit, ai, conventional-commits, automation
"""

__version__ = "1.1.0"
__author__ = "Alaamer"
__email__ = "ahmedmuhamed12@gmail.com"
__license__ = "MIT"
__copyright__ = "Copyright 2025 Alaamer"
__github__ = "https://github.com/alaamer12/c4f"
__documentation__ = "https://github.com/alaamer12/c4f"
__homepage__ = "https://github.com/alaamer12/c4f"
__description__ = "A sophisticated Git commit message generator that uses AI to create meaningful, conventional commit messages based on your code changes."
__long_description__ = """
C4F (Commit For Free) is an intelligent Git commit message generator that analyzes your code changes
and automatically generates meaningful, conventional commit messages using AI.

It detects changed, added, and deleted files, smartly categorizes changes (feat, fix, docs, etc.),
and provides an interactive commit process with manual override options.

C4F depends on g4f (GPT4Free) to generate the commit messages, providing a free alternative to
paid AI services while maintaining high-quality commit message generation.
"""
__python_requires__ = ">=3.11"
__keywords__ = [
    "git", "commit", "ai", "artificial-intelligence", "conventional-commits",
    "developer-tools", "automation", "cli", "command-line", "productivity",
    "version-control", "commit-message", "code-quality", "workflow",
    "git-tools", "semantic-commits", "devops", "software-development",
    "python-tool", "git-automation", "commit-history", "code-documentation"
]

__status__ = "Development/Stable"
__project_urls__ = {
    "Bug Tracker": "https://github.com/alaamer12/c4f/issues",
    "Documentation": "https://github.com/alaamer12/c4f",
    "Source Code": "https://github.com/alaamer12/c4f",
    "Changelog": "https://github.com/alaamer12/c4f/blob/main/CHANGELOG.md",
    "Contributing": "https://github.com/alaamer12/c4f/blob/main/CONTRIBUTING.md"
}

__release_date__ = "2025-04-03"
__maintainer__ = "Alaamer"
__maintainer_email__ = "ahmedmuhamed12@gmail.com"

from .cli import run_main as main

__all__ = [
    'main',
    '__version__',
    '__author__',
    '__email__',
    '__license__',
    '__copyright__',
    '__github__',
    '__documentation__',
    '__homepage__',
    '__description__',
    '__long_description__',
    '__python_requires__',
    '__keywords__',
    '__status__',
    '__project_urls__',
    '__release_date__',
    '__maintainer__',
    '__maintainer_email__',
]
