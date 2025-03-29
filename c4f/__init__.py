"""
Auto-Commit: An Intelligent Git Commit Message Generator

Key Features:
    - Automatic detection of changed, added, and deleted files
    - Smart categorization of changes (feat, fix, docs, etc.)
    - AI-powered commit message generation
    - Interactive commit process with manual override options
    - Support for both individual and batch commits
    - Handles binary files, directories, and permission issues gracefully

Usage:
    Run the script in a Git repository:
    $ python main.py

    The script will:
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
"""

__version__ = "1.0.0"
__author__ = "Alaamer"

from .main import main

__all__ = ['main', '__version__', '__author__']
