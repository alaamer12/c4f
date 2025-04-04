# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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