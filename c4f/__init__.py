"""
C4F (Commit For Future) - An Intelligent Git Commit Message Generator

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
    Author: Ahmed Alaamer
    Email: ahmedmuhamed12@gmail.com
    License: MIT
    Repository: https://github.com/alaamer12/c4f
    Documentation: https://github.com/alaamer12/c4f
    Python Support: >=3.9
    Keywords: git, commit, ai, conventional-commits, automation
"""

__version__ = "0.1.0"
__author__ = "Ahmed Alaamer"
__email__ = "ahmedmuhamed12@gmail.com"
__license__ = "MIT"
__copyright__ = "Copyright 2024 Ahmed Alaamer"
__github__ = "https://github.com/alaamer12/c4f"
__description__ = "A sophisticated Git commit message generator that uses AI to create meaningful, conventional commit messages."
__python_requires__ = ">=3.9"

from .main import main

__all__ = [
    'main',
    '__version__',
    '__author__',
    '__email__',
    '__license__',
    '__copyright__',
    '__github__',
    '__description__',
    '__python_requires__'
]
