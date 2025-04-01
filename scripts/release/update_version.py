import sys
import re
import argparse
from pathlib import Path
from typing import List, Optional

# Add the project root directory to Python path
PROJECT_NAME = "c4f"
project_root = str(Path(__file__).resolve().parent.parent.parent)  # Go up one more level to reach project root
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.utils.styles import Styles as styles
from scripts.utils.styles import print_header

# Check common project files
common_files = [
    "pyproject.toml",
    # "setup.cfg",
    # "setup.py",
    f"{PROJECT_NAME}/__init__.py",
]

def read_file_content(file_path: Path) -> str:
    with open(file_path, 'r') as f:
        return f.read()

def write_file_content(file_path: Path, content: str) -> None:
    with open(file_path, 'w') as f:
        f.write(content)

def get_version_increment(current_version: str, increment_type: str) -> str:
    """Calculate new version based on increment type."""
    major, minor, patch = map(int, current_version.split('.'))

    if increment_type.lower() == 'major':
        return f"{major + 1}.0.0"
    elif increment_type.lower() == 'minor':
        return f"{major}.{minor + 1}.0"
    elif increment_type.lower() == 'patch':
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError("Invalid version increment type")

def get_version_decrement(current_version: str) -> str:
    """Calculate previous version by decrementing patch number."""
    major, minor, patch = map(int, current_version.split('.'))
    if patch > 0:
        return f"{major}.{minor}.{patch - 1}"
    elif minor > 0:
        return f"{major}.{minor - 1}.0"
    elif major > 0:
        return f"{major - 1}.0.0"
    else:
        raise ValueError(styles.ERROR("Cannot decrement version 0.0.0"))

def update_version_in_content(content: str, old_version: str, new_version: str) -> str:
    """Update version while preserving the original format."""
    # First find how version is formatted in the file
    patterns = [
        r'version\s*=\s*"[^"]*"',  # version = "0.1.3"
        r'version\s*=\s*\'[^\']*\'',  # version = '0.1.3'
        r'version\s*=\s*[0-9.]+',  # version = 0.1.3
        r'__version__\s*=\s*"[^"]*"',  # __version__ = "0.1.3"
        r'__version__\s*=\s*\'[^\']*\'',  # __version__ = '0.1.3'
        r'__version__\s*=\s*[0-9.]+',  # __version__ = 0.1.3
        r'VERSION\s*=\s*"[^"]*"',  # VERSION = "0.1.3"
        r'VERSION\s*=\s*\'[^\']*\'',  # VERSION = '0.1.3'
        r'VERSION\s*=\s*[0-9.]+',  # version = 0.1.3
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            # Get the matched version string
            old_str = match.group(0)
            # Create new string with updated version
            new_str = old_str.replace(old_version, new_version)
            # Replace in content
            content = content.replace(old_str, new_str)
            break
    
    return content

def update_version_in_file(file_path: Path, old_version: str, new_version: str) -> None:
    try:
        content = read_file_content(file_path)
        updated_content = update_version_in_content(content, old_version, new_version)
        write_file_content(file_path, updated_content)
        print(styles.SUCCESS(f"Successfully updated: {file_path}"))
    except Exception as e:
        print(styles.ERROR(f"Error updating {file_path}: {e}"))

def get_current_version(file_path: Path) -> str:
    """Extract version from various file formats."""
    try:
        content = read_file_content(file_path)
        
        # Try different version patterns
        patterns = [
            r'version\s*=\s*["\']?(\d+\.\d+\.\d+)["\']?',  # Matches: version = "X.Y.Z" or version = X.Y.Z
            r'__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']',  # Matches: __version__ = "X.Y.Z"
            r'VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']',  # Matches: VERSION = "X.Y.Z"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        raise ValueError(styles.ERROR(f"No version pattern found in {file_path}"))
    except Exception as e:
        raise ValueError(styles.ERROR(f"Failed to extract version: {e}"))

def validate_files(files: List[Path], quiet: bool) -> None:
    if not quiet:
        print(styles.INFO("Checking files..."))
    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(styles.ERROR(f"File not found: {file_path}"))
        if not quiet:
            print(styles.FILE_OP(f"Found: {file_path}"))

def get_increment_type() -> str:
    print_header("Version Update Options")
    print(styles.OPTION("major - For significant changes"))
    print(styles.OPTION("minor - For new features"))
    print(styles.OPTION("patch - For bug fixes"))
    
    while True:
        increment_type = input(styles.PROMPT("Choose version type (major/minor/patch): ")).lower()
        if increment_type in ['major', 'minor', 'patch']:
            return increment_type
        print(styles.ERROR("Invalid input. Please choose 'major', 'minor', or 'patch'"))

def check_version_consistency(files: List[Path], quiet: bool = False) -> str:
    """Check if all files have the same version number."""
    versions = {}
    for file_path in files:
        try:
            version = get_current_version(file_path)
            versions[str(file_path)] = version
        except Exception as e:
            raise ValueError(styles.ERROR(f"Failed to get version from {file_path}: {e}"))
    
    if not versions:
        raise ValueError(styles.ERROR("No version information found in any files"))
    
    unique_versions = set(versions.values())
    if len(unique_versions) > 1:
        error_msg = "Version mismatch detected:\n"
        for file_path, version in versions.items():
            error_msg += styles.FILE_OP(f"  {file_path}: {version}\n")
        raise ValueError(styles.ERROR(error_msg))
    
    if not quiet:
        print(styles.SUCCESS(f"All files have consistent version: {list(unique_versions)[0]}"))
    
    return list(unique_versions)[0]

def rollback_files(files: List[Path], quiet: bool = False) -> None:
    """Roll back version by decrementing the version number."""
    if not quiet:
        print(styles.INFO("Rolling back version..."))
    
    try:
        current_version = check_version_consistency(files, quiet)
        previous_version = get_version_decrement(current_version)
        
        if not quiet:
            print(styles.INFO(f"Rolling back from {styles.VERSION_OLD(current_version)} to {styles.VERSION_NEW(previous_version)}"))
        
        for file_path in files:
            update_version_in_file(file_path, current_version, previous_version)
            
        if not quiet:
            print(styles.SUCCESS("Version rollback complete"))
            
    except Exception as e:
        raise ValueError(styles.ERROR(f"Failed to rollback version: {e}"))

def update_version(root_dir: Path, increment_type: Optional[str] = None, quiet: bool = False, 
                   rollback: bool = False) -> str:
    """Update version in all relevant files.
    
    Args:
        root_dir: Project root directory containing version files
        increment_type: Type of version increment ('major', 'minor', 'patch')
        quiet: If True, suppress output messages
        rollback: If True, rollback to previous version
        
    Returns:
        str: New version number, or empty string if rollback
    """
    if not quiet:
        print_header("Version Update Tool")

    # Validate and find files
    if not root_dir.exists():
        raise FileNotFoundError(styles.ERROR(f"Directory not found: {root_dir}"))
        
    files_to_update = [root_dir / file for file in common_files if (root_dir / file).exists()]
    validate_files(files_to_update, quiet)

    if rollback:
        rollback_files(files_to_update, quiet)
        return ""

    # Get current version and calculate new version
    current_version = check_version_consistency(files_to_update, quiet)
    if increment_type is None:
        increment_type = get_increment_type()
    
    if not quiet:
        print(styles.INFO(f"Current Version: {current_version}"))
    
    new_version = get_version_increment(current_version, increment_type)

    # Update files
    try:
        if not quiet:
            print(styles.INFO("Updating version in files..."))
        for file_path in files_to_update:
            update_version_in_file(file_path, current_version, new_version)
            
        if not quiet:
            print_header("Version Update Complete")
            print(styles.VERSION_OLD(current_version))
            print(styles.VERSION_NEW(new_version))
            
    except Exception as e:
        print(styles.ERROR(f"Error during update: {e}"))
        print(styles.WARNING("Rolling back changes..."))
        rollback_files(files_to_update, quiet)
        raise

    return new_version

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Version management tool for Python projects. Updates or rolls back version numbers in common project files."
    )
    parser.add_argument("-t", "--type", choices=["major", "minor", "patch"], 
                       help="Type of version increment")
    parser.add_argument("-q", "--quiet", action="store_true", 
                       help="Suppress output messages")
    parser.add_argument("-r", "--rollback", action="store_true", 
                       help="Rollback to previous version")
    return parser.parse_args()

def cli():
    """Command line interface for the version updater."""
    args = parse_arguments()
    try:
        root_dir = Path.cwd()
        if args.rollback:
            update_version(root_dir, rollback=True, quiet=args.quiet)
        else:
            update_version(root_dir, increment_type=args.type, quiet=args.quiet)
    except KeyboardInterrupt:
        print(styles.WARNING("\nOperation cancelled by user"))
        sys.exit(1)
    except Exception as e:
        print(styles.ERROR(f"Error: {e}"), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    cli()