"""
CLI interface for c4f (Commit For Free) - An Intelligent Git Commit Message Generator.

This module provides a command-line interface for the c4f tool, allowing users to configure
and customize the commit message generation process through various command-line arguments.

Arguments:
    -h, --help              Show this help message and exit
    -v, --version           Show program's version number and exit
    -r, --root PATH        Set the root directory [default: current project root]
    -m, --model MODEL      Set the AI model to use [default: gpt-4-mini]
    -a, --attempts NUM     Set the number of generation attempts [default: 3]
    -t, --timeout SEC      Set the fallback timeout in seconds [default: 10]
    -f, --force-brackets   Force conventional commit type with brackets [default: False]
"""

import argparse
import os
from pathlib import Path

# Import main functionality here to avoid circular imports
from c4f.main import main as run_main

__all__ = ["run_main"]

# ASCII art banner for c4f
BANNER = r"""
   _____ _  _     _____ 
  / ____| || |   |  ___|
 | |    | || |_  | |_   
 | |    |__   _| |  _|  
 | |____   | |   | |    
  \_____|  |_|   |_|    
                        
 Commit For Free - AI-Powered Git Commit Message Generator
"""

# Define color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# noinspection PyProtectedMember
class ColoredHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter that adds colors to the help text."""

    def __init__(self, prog, indent_increment=2, max_help_position=30, width=None, color=True):
        super().__init__(prog, indent_increment, max_help_position, width)
        self.color = color

    def _format_action(self, action):
        # Get the original help text
        help_text = super()._format_action(action)

        if not self.color:
            return help_text

        # Add colors to different parts of the help text
        help_text = help_text.replace('usage:', f'{Colors.BOLD}{Colors.GREEN}usage:{Colors.ENDC}')
        help_text = help_text.replace('options:', f'{Colors.BOLD}{Colors.BLUE}options:{Colors.ENDC}')

        # Highlight option strings
        for opt in ['-h', '--help', '-v', '--version']:
            if opt in help_text:
                help_text = help_text.replace(f'{opt}', f'{Colors.BOLD}{Colors.YELLOW}{opt}{Colors.ENDC}')

        return help_text

    def _format_usage(self, usage, actions, groups, prefix):
        usage_text = super()._format_usage(usage, actions, groups, prefix)

        if not self.color:
            return usage_text

        # Add colors to the usage text
        usage_text = usage_text.replace('usage:', f'{Colors.BOLD}{Colors.GREEN}usage:{Colors.ENDC}')

        return usage_text

    def _format_action_invocation(self, action):
        text = super()._format_action_invocation(action)

        if not self.color or not action.option_strings:
            return text

        # Add colors to option strings
        for opt in action.option_strings:
            text = text.replace(f'{opt}', f'{Colors.BOLD}{Colors.YELLOW}{opt}{Colors.ENDC}')

        return text

def create_argument_parser(color: bool = True) -> argparse.ArgumentParser:
    """Create and configure the argument parser for the CLI.

    Args:
        color (bool): Whether to use colored output.

    Returns:
        argparse.ArgumentParser: Configured argument parser with program metadata.
    """
    # Prepare the description text with ASCII banner if color is enabled
    description = f"{Colors.BLUE}{BANNER}{Colors.ENDC}\nIntelligent Git Commit Message Generator" if color else "Intelligent Git Commit Message Generator"

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=lambda prog: ColoredHelpFormatter(prog, color=color),
        epilog=f"{Colors.GREEN}For more information, visit: https://github.com/alaamer12/c4f{Colors.ENDC}" if color else "For more information, visit: https://github.com/alaamer12/c4f",
        prog="c4f",
        add_help=True,
        allow_abbrev=True
    )
    return parser

def add_version_argument(parser: argparse.ArgumentParser) -> None:
    """Add version argument to the parser.

    Args:
        parser (argparse.ArgumentParser): The argument parser to add the version argument to.
    """
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 1.0.0",
        help="Show program's version number and exit"
    )

def add_directory_argument(parser: argparse.ArgumentParser) -> None:
    """Add root directory argument to the parser.

    Args:
        parser (argparse.ArgumentParser): The argument parser to add the directory argument to.
    """
    parser.add_argument(
        "-r", "--root",
        type=Path,
        help="Set the root directory for git operations [default: current project root]",
        default=Path.cwd(),
        metavar="PATH",
        dest="root"
    )

def add_model_argument(parser: argparse.ArgumentParser) -> None:
    """Add AI model argument to the parser.

    Args:
        parser (argparse.ArgumentParser): The argument parser to add the model argument to.
    """
    parser.add_argument(
        "-m", "--model",
        type=str,
        help="Set the AI model to use for commit message generation [default: gpt-4-mini]",
        default="gpt-4-mini",
        metavar="MODEL",
        choices=["gpt-4-mini", "gpt-4", "gpt-3.5-turbo"],
        dest="model"
    )

def add_generation_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments related to message generation.

    Args:
        parser (argparse.ArgumentParser): The argument parser to add the generation arguments to.
    """
    generation_group = parser.add_argument_group('Generation Options', 'Configure the commit message generation process')

    generation_group.add_argument(
        "-a", "--attempts",
        type=int,
        help="Set the number of generation attempts before falling back [default: 3]",
        default=3,
        metavar="NUM",
        choices=range(1, 11),
        dest="attempts"
    )

    generation_group.add_argument(
        "-t", "--timeout",
        type=int,
        help="Set the fallback timeout in seconds for model response [default: 10]",
        default=10,
        metavar="SEC",
        choices=range(1, 61),
        dest="timeout"
    )

def add_formatting_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments related to commit message formatting.

    Args:
        parser (argparse.ArgumentParser): The argument parser to add the formatting arguments to.
    """
    formatting_group = parser.add_argument_group('Formatting Options', 'Configure the commit message format')

    formatting_group.add_argument(
        "-f", "--force-brackets",
        action="store_true",
        help="Force conventional commit type with brackets (e.g., feat(scope): message)",
        dest="force_brackets"
    )

def parse_args() -> argparse.Namespace:
    """Create parser, add arguments, and parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    # First parse just the color argument to determine if we should use colors
    pre_parser = argparse.ArgumentParser(add_help=False)

    # Parse known args to get the color setting
    pre_args, _ = pre_parser.parse_known_args()

    # Now create the full parser with the correct color setting
    parser = create_argument_parser(color=True)

    # Add all arguments
    add_version_argument(parser)
    add_directory_argument(parser)
    add_model_argument(parser)
    add_generation_arguments(parser)
    add_formatting_arguments(parser)

    args = parser.parse_args()

    # If root is specified, change to that directory
    if args.root:
        try:
            os.chdir(args.root)
        except (OSError, FileNotFoundError) as e:
            parser.error(f"Failed to change to directory {args.root}: {str(e)}")

    return args

def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()
    # Update global constants based on CLI arguments
    globals().update({
        'FORCE_BRACKETS': args.force_brackets,
        'FALLBACK_TIMEOUT': args.timeout,
        'ATTEMPT': args.attempts,
        'MODEL': args.model,
    })

    # Run the main program with the root argument
    run_main()

if __name__ == "__main__":
    main()