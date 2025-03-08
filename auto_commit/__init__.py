"""
Auto-Commit: An Intelligent Git Commit Message Generator

This package provides tools for automatically generating meaningful Git commit messages
using AI assistance and smart change detection.
"""

__version__ = "1.0.0"
__author__ = "Alaamer"

from .main import *
from .cli import main_cli

__all__ = ['main_cli']