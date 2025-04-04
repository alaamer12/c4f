"""
Entry point for running c4f as a package.

This module allows the package to be executed directly using:
python -m c4f
"""

from .cli import run_main

if __name__ == "__main__":
    run_main()
