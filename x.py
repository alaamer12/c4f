from rich.console import Console
from rich.markdown import Markdown

# Initialize the console
console = Console()

# Sample Markdown text
markdown_text = """
# My Markdown Example

This is a **bold** and *italic* text demo.

- Item 1
- Item 2
  - Subitem 2.1
  - Subitem 2.2

## Code Block
```python
print("Hello, Rich!")
```
"""
md = Markdown(markdown_text)
print(str(md))
console.print(md)

