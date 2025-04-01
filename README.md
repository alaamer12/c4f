# Auto-Commit

A sophisticated Git commit message generator that uses AI to create meaningful, conventional commit messages based on your code changes.

## Features

- 🤖 AI-powered commit message generation using GPT models
- 📝 Follows [Conventional Commits](https://www.conventionalcommits.org/) format
- 🔍 Smart analysis of file changes and diffs
- 🎨 Beautiful CLI interface with rich formatting
- ⚡ Efficient handling of both small and large changes
- 🔄 Fallback mechanisms for reliability
- 🎯 Automatic change type detection (feat, fix, docs, etc.)
- 📊 Progress tracking and status display

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/auto-commit.git
cd auto-commit
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Simply run the script in your Git repository:

```bash
python main.py
```

The tool will:
1. Detect staged and unstaged changes in your repository
2. Analyze the changes and their context
3. Generate an appropriate commit message using AI
4. Stage and commit the changes with the generated message

### Features in Detail

- **Smart Change Analysis**: Automatically detects the type of changes (feature, fix, documentation, etc.) based on file paths and content
- **Comprehensive Messages**: Generates detailed commit messages for larger changes with bullet points and breaking change notifications
- **Interactive Interface**: Displays changes in a formatted table and allows user interaction when needed
- **Progress Tracking**: Shows real-time progress for file analysis and commit operations
- **Fallback Mechanism**: Includes a fallback system if AI generation fails or times out

## Configuration

Key configuration variables in `main.py`:

- `PROMPT_THRESHOLD = 80`: Line threshold for comprehensive vs. simple commit messages
- `FALLBACK_TIMEOUT = 10`: Timeout in seconds for AI response
- `MIN_COMPREHENSIVE_LENGTH = 50`: Minimum length for comprehensive commit messages
- `ATTEMPT = 3`: Number of attempts for generating commit messages
- `MODEL`: The AI model to use for generation (default: gpt_4o_mini)

## Requirements

- Python 3.6+
- Git
- Required Python packages (see requirements.txt)
- Internet connection for AI model access

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes using the tool itself! 😉
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Model Compatibility 

While c4f has been primarily tested with `gpt-4-mini`, `gpt-4`, and `gpt-3.5-turbo`, the underlying g4f library supports many additional models. However, please note:

⚠️ **Warning**: Although most g4f-supported models may technically work with c4f, they have not been extensively tested and are not officially recommended. Using untested models may result in:
- Lower quality commit messages
- Slower performance
- Unexpected errors or timeouts

For the best experience, we recommend using one of the officially supported models specified in the command-line options.

## License

This project is licensed under the MIT License - see the [LICENSE file](LICENSE) for details.

## Acknowledgments

- Built with [g4f](https://github.com/xtekky/gpt4free) for AI generation
  - Special thanks to the g4f library maintainers for making powerful AI models accessible
  - g4f enables this tool to generate high-quality commit messages without API keys
- Uses [rich](https://github.com/Textualize/rich) for beautiful terminal formatting