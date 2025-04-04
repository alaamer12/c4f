# GitHub Actions

This document describes the GitHub Actions workflows used in the C4F project.

## g4f Dependency Updates

C4F relies on [g4f](https://github.com/xtekky/gpt4free) for AI model access. To ensure we're always using the latest version with bug fixes and improvements, we've implemented an automated update workflow.

### How It Works

The `.github/workflows/update-g4f.yml` workflow:

1. **Schedule**: Automatically runs once a week (on Sundays at 00:00 UTC)
2. **Version Check**: 
   - Extracts the current g4f version from pyproject.toml
   - Fetches the latest g4f version from PyPI
   - Compares them to determine if an update is needed
3. **Update Process**:
   - If a newer version is available, updates the dependency using Poetry
   - Creates a pull request with the changes
   - Adds appropriate labels and description

### Manual Trigger

You can also trigger this workflow manually from the GitHub Actions tab in your repository.

### Pull Request Review

While the process is automated, pull requests still require review and approval before merging to ensure the update doesn't break any functionality.

## Customizing the Workflow

If you need to adjust how often the check runs, you can modify the cron schedule in the workflow file. For example:

- Daily check: `0 0 * * *` (at midnight UTC every day)
- Weekly check: `0 0 * * 0` (at midnight UTC every Sunday)
- Monthly check: `0 0 1 * *` (at midnight UTC on the first day of each month)

If you need to specify a custom version or pin g4f to a specific version, you can modify the workflow or manually update the dependency. 