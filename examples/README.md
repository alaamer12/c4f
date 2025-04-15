# C4F Examples

This directory contains example scripts to demonstrate the features of the Commit For Free (C4F) library.

## Progress Bar Demo

The `progress_bar_demo.py` script shows how to use the singleton `ProgressBar` class for creating customized progress indicators in your applications.

### Running the demo

```bash
python examples/progressbar_demo.py
```

## Using the ProgressBar Class

The `ProgressBar` class is a singleton that provides a centralized way to create and manage progress bars using Rich. It supports customizing the appearance and behavior of progress bars and ensures that only one progress bar is active at a time.

### Basic Usage

```python
from c4f.utils import ProgressBar

# Get the progress bar instance
progress = ProgressBar.get_instance()

# Create a basic progress bar
with progress.create() as p:
    task = p.add_task("Processing...", total=100)
    for i in range(100):
        # Do some work
        p.update(task, advance=1)
```

### Progress Bar Types

The `ProgressBar` class uses an enum `ProgressBarType` to define different types of progress bars:

```python
from c4f.utils import ProgressBar, ProgressBarType

progress = ProgressBar.get_instance()

# Create different types of progress bars
with progress.create(bar_type=ProgressBarType.SPINNER) as p:
    # Spinner-only progress
    task = p.add_task("Loading...", total=None)
    # Do work...

with progress.create(bar_type=ProgressBarType.DOWNLOAD) as p:
    # Download-style progress bar
    task = p.add_task("Downloading file.zip", total=file_size)
    # Download with chunking...
    p.update(task, advance=chunk_size)

with progress.create(bar_type=ProgressBarType.COMMIT) as p:
    # Git commit-style progress bar
    task = p.add_task("Committing changes", total=files_count)
    # Process files...
    p.update(task, advance=1)

with progress.create(bar_type=ProgressBarType.MULTIPLE) as p:
    # Progress bar optimized for multiple tasks
    task1 = p.add_task("Task 1", total=100)
    task2 = p.add_task("Task 2", total=50)
    # Update multiple tasks...

with progress.create(bar_type=ProgressBarType.MINIMAL) as p:
    # Minimal progress bar with less visual elements
    task = p.add_task("Processing", total=100)
    # Do work...

# Indeterminate progress bar returns both progress and task_id
p, task_id = progress.create(bar_type=ProgressBarType.INDETERMINATE)
with p:
    # Do work with unknown duration...
```

### Themed Progress Bars

The `ProgressBar` class comes with several predefined themes:

- `default`: Green progress bar with dots spinner
- `ocean`: Blue progress bar theme
- `fire`: Red to yellow theme
- `elegant`: Clean white theme
- `forest`: Green forest theme
- `sunset`: Orange sunset theme
- `neon`: Bright pink and cyan theme
- `minimal`: Simple minimalistic theme

```python
# Create a progress bar with a predefined theme
with progress.create(theme="ocean") as p:
    task = p.add_task("Ocean theme progress", total=100)
    for i in range(100):
        # Do some work
        p.update(task, advance=1)
```

### Tracking Iterables

You can easily track progress while iterating:

```python
# Track an iterable with a progress bar
for item in progress.track(items, description="Processing items"):
    # Process item
    pass

# Alternative with context manager
with progress.for_loop(items, description="Processing") as (p, tracked_items):
    for item in tracked_items:
        # Process item
        pass
```

### Custom Columns

You can specify columns using either string identifiers or Rich column objects:

```python
# String-based column specification
with progress.create(columns=["spinner", "description", "bar", "percentage", "elapsed"]) as p:
    task = p.add_task("Processing with custom columns", total=100)
    # Work with task

# Object-based column specification
from rich.progress import TextColumn, BarColumn, TimeElapsedColumn

columns = [
    TextColumn("[bold green]{task.description}"),
    BarColumn(bar_width=30, complete_style="yellow"),
    TextColumn("[bold]{task.percentage:>3.0f}%"),
    TimeElapsedColumn()
]

with progress.create(columns=columns) as p:
    task = p.add_task("Custom styled columns", total=100)
    # Work with task
```

### Custom Themes

You can create and use your own themes:

```python
# Define a custom theme
custom_theme = {
    "spinner": "dots12",
    "bar_width": 40,
    "complete_style": "magenta",
    "finished_style": "bold magenta",
    "pulse_style": "bright_magenta",
}

# Add the custom theme
progress.add_theme("purple_dream", custom_theme)

# Use the custom theme
with progress.create(theme="purple_dream") as p:
    task = p.add_task("Custom purple theme", total=100)
    # Work with task
```

### Available Column Types

The following column types are available by name:

- `spinner`: Animated spinner
- `description`: Task description text
- `bar`: Progress bar
- `percentage`: Percentage text (e.g., "85%")
- `progress`: Task progress (e.g., "1/100")
- `elapsed`: Time elapsed
- `remaining`: Time remaining
- `filesize`: Current file size
- `totalsize`: Total file size
- `download`: Download indicator
- `speed`: Transfer speed
- `count`: Count of items (e.g., "1 of 100")

## Advanced Features

The `ProgressBar` class also provides:

- Theme management (add, update, list)
- Progress tracking and reporting
- Custom styling for individual columns

For more examples, see the `progress_bar_demo.py` script. 