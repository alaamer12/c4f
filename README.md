# C4F - Commit For Free
[![PyPI version](https://img.shields.io/pypi/v/commit-for-free.svg)](https://pypi.org/project/commit-for-free/)
[![Python Version](https://img.shields.io/pypi/pyversions/commit-for-free.svg)](https://pypi.org/project/commit-for-free/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A sophisticated Git commit message generator that uses AI to create meaningful, conventional commit messages based on your code changes.

![Simple GIF showcase an introduction about C4f](https://raw.githubusercontent.com/alaamer12/c4f/main/assets/intro.gif "Intro Animation")

<div>
  <pre style="background-color:#282c34; color:#61afef; font-weight:bold; padding:20px; border-radius:10px; font-size:16px">
   _____ _  _     _____ 
  / ____| || |   |  ___|
 | |    | || |_  | |_   
 | |    |__   _| |  _|  
 | |____   | |   | |    
  \_____|  |_|   |_|    
                        
 Commit For Free - AI-Powered Git Commit Message Generator
  </pre>
</div>

## Features

- 🤖 AI-powered commit message generation using GPT models
- 📝 Follows [Conventional Commits](https://www.conventionalcommits.org/) format
- 🔍 Smart analysis of file changes and diffs
- 🎨 Beautiful CLI interface with rich formatting
- ⚡ Efficient handling of both small and large changes
- 🔄 Fallback mechanisms for reliability
- 🎯 Automatic change type detection (feat, fix, docs, etc.)
- 📊 Progress tracking and status display

## Demo

See C4F in action:

![Commit generation demo](https://raw.githubusercontent.com/alaamer12/c4f/main/assets/commits.gif)

> **Note:** It's normal to occasionally see model response timeouts as shown in the demo. This is due to limitations of the free GPT models provided by `g4f`. After all configured attempts, the package automatically creates a fallback commit message to ensure you can always complete your workflow.

## Installation

> **⚠️ Important:** C4F requires **Python 3.11 or higher** to run.

### Using pip

```bash
pip install commit-for-free
```

### Using pipx (Recommended for non-Windows platforms)

For a clean, isolated installation that doesn't interfere with your system Python:

```bash
# Install pipx if you don't have it
python -m pip install --user pipx
python -m pipx ensurepath

# Install c4f
pipx install commit-for-free
```

### With Enhanced Resource Monitoring

For more accurate system resource monitoring (CPU, memory, process tree):

```bash
pip install commit-for-free[monitoring]
```

### From source

1. Clone the repository:
```bash
git clone https://github.com/alaamer12/c4f.git
cd c4f
```

2. Install using Poetry:
```bash
poetry install
```

Or with pip:
```bash
pip install -e .
```

## Usage

### Basic Usage

Simply run the command in your Git repository:

```bash
c4f
```

The tool will:
1. Detect staged and unstaged changes in your repository
2. Analyze the changes and their context
3. Generate an appropriate commit message using AI
4. Stage and commit the changes with the generated message

![A Long GIF file showcasing how the author commited changes using c4f with inudstrial practices](https://raw.githubusercontent.com/alaamer12/c4f/main/assets/full.gif "Full workflow demonstration")

### Command-line Options

```
usage: c4f [-r PATH] [-m MODEL] [-a NUM] [-t SEC] [-f]

Intelligent Git Commit Message Generator

options:
  -r PATH, --root PATH  Set the root directory for git operations [default: current project root]
  -m MODEL, --model MODEL
                        Set the AI model to use for commit message generation [default: gpt-4-mini]
                        Choices: gpt-4-mini, gpt-4, gpt-3.5-turbo

Generation Options:
  Configure the commit message generation process

  -a NUM, --attempts NUM
                        Set the number of generation attempts before falling back [default: 3]
                        Range: 1-10
  -t SEC, --timeout SEC
                        Set the fallback timeout in seconds for model response [default: 10]
                        Range: 1-60

Formatting Options:
  Configure the commit message format

  -f, --force-brackets  Force conventional commit type with brackets (e.g., feat(scope): message)
```

### Examples

Generate commit messages with the default settings:
```bash
c4f
```

Use a specific AI model:
```bash
c4f --model gpt-4
```

Set custom generation parameters:
```bash
c4f --attempts 5 --timeout 20
```

Force brackets in conventional commit format:
```bash
c4f --force-brackets
```

Specify a different root directory:
```bash
c4f --root /path/to/your/repo
```

### Features in Detail

- **Smart Change Analysis**: Automatically detects the type of changes (feature, fix, documentation, etc.) based on file paths and content
- **Comprehensive Messages**: Generates detailed commit messages for larger changes with bullet points and breaking change notifications
- **Interactive Interface**: Displays changes in a formatted table and allows user interaction when needed
- **Progress Tracking**: Shows real-time progress for file analysis and commit operations
- **Fallback Mechanism**: Includes a fallback system if AI generation fails or times out

## Configuration

Key configuration options available through command-line arguments:

| Option             | Description                           | Default    |
|--------------------|---------------------------------------|------------|
| `--model`          | AI model to use                       | gpt-4-mini |
| `--attempts`       | Number of message generation attempts | 3          |
| `--timeout`        | Timeout in seconds for AI response    | 10         |
| `--force-brackets` | Force brackets in conventional format | False      |

## Requirements

- **Python 3.11+** - C4F uses modern Python features that require version 3.11 or higher
- **Git** - Required for accessing repository information and making commits
- **Required Python packages:**
  - `g4f` - Provides free access to AI models for generating commit messages
  - `rich` - Powers the beautiful terminal interface and formatted output

### System Requirements

- Any modern operating system (Windows, macOS, Linux)
- Approximately 100MB of disk space (including dependencies)
- Stable internet connection for AI model access

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes using c4f itself! 😉
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/alaamer12/c4f.git
cd c4f

# Install development dependencies
poetry install --with dev

# Run tests
pytest

# Run Coverage
coverage -m pytest
```

## Model Compatibility 

While c4f has been primarily tested with `gpt-4-mini`, `gpt-4`, and `gpt-3.5-turbo`, the underlying g4f library supports many additional models. However, please note:

⚠️ **Warning**: Although most g4f-supported models may technically work with c4f, they have not been extensively tested and are not officially recommended. Using untested models may result in:
- Lower quality commit messages
- Slower performance
- Unexpected errors or timeouts

Always use the latest version of g4f to ensure compatibility and access to the most recent models and improvements. You can update g4f with:
```bash
pip install -U g4f
```

For the best experience, we recommend using one of the officially supported models specified in the command-line options.

## License

This project is licensed under the MIT License - see the [LICENSE file](LICENSE) for details.

## Changelog

See the [CHANGELOG.md](CHANGELOG.md) file for details about version history and updates.

## Security

Please review our [SECURITY.md](SECURITY.md) file for information about:
- How to report security vulnerabilities
- Our responsible disclosure policy
- Security best practices when using this tool
- Dependency tracking and security audits

## Acknowledgments

- Built with [g4f](https://github.com/xtekky/gpt4free) for AI generation
  - Special thanks to the g4f library maintainers for making powerful AI models accessible
  - g4f enables this tool to generate high-quality commit messages without API keys
- Uses [rich](https://github.com/Textualize/rich) for beautiful terminal formatting
