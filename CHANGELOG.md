# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.3] - 2025-04-18

### Added
- New feature to force icon display in commit messages
- ASCII-only mode for better terminal compatibility with `--ascii-only` flag

### Fixed
- Resolved issue with undetected empty files
- Fixed handling of unstaged and undetected files
- Fixed failing tests related to icon display in messages

### Changed
- Implemented smart fallback strategy for emojis with ASCII alternatives
- Enhanced test suite with comprehensive coverage for icon display features
- Improved terminal compatibility detection for better cross-platform experience

### Changed
- Refactored processor implementations into self-contained, modular structures
- Enhanced error handling with graceful fallbacks between processing strategies
- Improved progress tracking with detailed status updates
- Optimized resource management for long-running operations

### Technical
- Introduced abstract base processor class for better code organization
- Implemented factory pattern for processor instantiation
- Added comprehensive type hints and runtime type checking
- Enhanced thread safety in parallel operations

## [1.1.2] - 2025-04-15

### Changed
- Enforced stricter static typing across the codebase.
- Improved overall code typing coverage and quality.
- Enhanced the robustness and coverage of the testing suite.

### Fixed
- Resolved bugs related to subprocess resource monitoring.

## [1.1.1] - 2025-04-12

### Added
- More robust testing framework with comprehensive test cases
- Enhanced configuration system for better customization
- Improved user experience with additional customization options
- Better error handling and user feedback

### Changed
- Refined configuration management for more flexibility
- Enhanced test coverage across all components
- Improved documentation for configuration options

### Fixed
- Various minor bugs and edge cases in testing framework
- Configuration validation issues

## [1.1.0] - 2025-04-8

### Added
- New architecture for better maintenance and fault tolerance
- New Safe and robust source of truth implementation for subprocess
- More comprehensive test coverage

### Fixed
- Memory leak issues in long-running processes
- Infinite loops in process monitoring
- Resource cleanup in subprocess handling

## [1.0.3] - 2025-04-6

### Added
- Support for legacy systems and environments
- More comprehensive test coverage with parameterized tests
- Better error handling for edge cases

### Fixed
- Resolved terminal encoding issues with CP1252 and other encodings
- Fixed subprocess issues on Windows platforms
- Improved error handling for non-UTF-8 environments

### Changed
- Enhanced terminal CLI styling with better colors and layout
- Improved README and documentation with more examples
- Upgraded code quality with stricter linting and type checking

## [1.0.2] - 2025-04-4

### Added
- Improved type annotations throughout the codebase
- Enhanced documentation with Google-style docstrings

### Fixed
- Resolved building issues in package distribution

## [1.0.1] - 2025-04-3

### Fixed
- Resolved issue with metadata files not being included in package distribution
- Fixed configuration in pyproject.toml to properly include unversioned files (CHANGELOG.md, CODE_OF_CONDUCT.md, etc.)
- Removed duplicate include directive from poetry.urls section

## [1.0.0] - 2025-03-29

### Added
- Initial release of C4F
- AI-powered commit message generation with GPT models
- Support for conventional commits format
- analysis of file changes and diffs
- CLI interface with rich formatting
- Command-line arguments for customization
- Support for various AI models (gpt-4-mini, gpt-4, gpt-3.5-turbo)
- Progress tracking and status display
- Fallback mechanisms for reliability