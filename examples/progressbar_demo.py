#!/usr/bin/env python
"""Demo script for the ProgressBar singleton class.

This script demonstrates the various features of the ProgressBar class,
including different types of progress bars, themes, and usage patterns.
"""

import random
import sys
import time
from pathlib import Path
from c4f._progress import ProgressBar, ProgressBarType, console

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def basic_progress_demo():
    """Demonstrate a basic progress bar."""
    console.print("\n[bold cyan]Basic Progress Bar Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    with progress.create() as p:
        task = p.add_task("Processing items", total=100)
        for _ in range(100):
            time.sleep(0.02)
            p.update(task, advance=1)


def themed_progress_demo():
    """Demonstrate different themed progress bars."""
    console.print("\n[bold cyan]Themed Progress Bars Demo[/bold cyan]")

    progress = ProgressBar.get_instance()
    themes = progress.get_themes()

    for theme in themes:
        console.print(f"\n[bold]Theme: {theme}[/bold]")
        with progress.create(theme=theme) as p:
            task = p.add_task(f"{theme.capitalize()} theme", total=50)
            for i in range(50):
                time.sleep(0.01)
                p.update(task, advance=1)


def spinner_progress_demo():
    """Demonstrate a spinner progress indicator."""
    console.print("\n[bold cyan]Spinner Progress Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    with progress.create(description="Loading data...", bar_type=ProgressBarType.SPINNER) as p:
        p.add_task("", total=None)
        for _ in range(50):
            time.sleep(0.05)


def download_progress_demo():
    """Demonstrate a download progress bar."""
    console.print("\n[bold cyan]Download Progress Bar Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    file_size = 1024 * 1024 * 10  # 10 MB

    with progress.create(bar_type=ProgressBarType.DOWNLOAD) as p:
        task = p.add_task("Downloading example.zip", total=file_size)
        downloaded = 0
        while downloaded < file_size:
            # Simulate variable download speeds
            chunk_size = min(random.randint(2048, 1024 * 1024), file_size - downloaded)
            downloaded += chunk_size
            p.update(task, advance=chunk_size)
            time.sleep(0.05)


def multiple_tasks_demo():
    """Demonstrate a progress bar with multiple tasks."""
    console.print("\n[bold cyan]Multiple Tasks Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    with progress.create(theme="ocean", bar_type=ProgressBarType.MULTIPLE) as p:
        task1 = p.add_task("[red]Processing images", total=100)
        task2 = p.add_task("[green]Analyzing data", total=50)
        task3 = p.add_task("[blue]Generating reports", total=80)

        for i in range(100):
            time.sleep(0.05)
            p.update(task1, advance=1)
            if i % 2 == 0:
                p.update(task2, advance=1)
            if i % 1.25 == 0:
                p.update(task3, advance=1)


def track_iteration_demo():
    """Demonstrate tracking progress during iteration."""
    console.print("\n[bold cyan]Track Iteration Demo[/bold cyan]")

    progress = ProgressBar.get_instance()
    items = list(range(50))

    for _ in progress.track(items, description="Processing items", theme="forest"):
        time.sleep(0.05)


def for_loop_context_demo():
    """Demonstrate the for_loop context manager."""
    console.print("\n[bold cyan]For Loop Context Demo[/bold cyan]")

    progress = ProgressBar.get_instance()
    items = list(range(30))

    with progress.for_loop(items, description="Iterating", theme="sunset") as (p, tracked_items):
        for _ in tracked_items:
            time.sleep(0.05)


def indeterminate_progress_demo():
    """Demonstrate an indeterminate progress bar."""
    console.print("\n[bold cyan]Indeterminate Progress Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    progress_bar, task_id = progress.create(
        description="Working on something...",
        bar_type=ProgressBarType.INDETERMINATE
    )

    with progress_bar:
        for _ in range(100):
            time.sleep(0.05)


def custom_columns_demo():
    """Demonstrate progress bars with custom columns."""
    console.print("\n[bold cyan]Custom Columns Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    console.print("[bold]String-based column specification:[/bold]")
    with progress.create(columns=["spinner", "description", "bar", "percentage", "elapsed"]) as p:
        task = p.add_task("Processing with custom columns", total=100)
        for _ in range(100):
            time.sleep(0.01)
            p.update(task, advance=1)

    from rich.progress import TextColumn, BarColumn, TimeElapsedColumn

    console.print("\n[bold]Object-based column specification:[/bold]")
    columns = [
        TextColumn("[bold green]{task.description}"),
        BarColumn(bar_width=30, complete_style="yellow"),
        TextColumn("[bold]{task.percentage:>3.0f}%"),
        TimeElapsedColumn()
    ]

    with progress.create(columns=columns) as p:
        task = p.add_task("Custom styled columns", total=100)
        for _ in range(100):
            time.sleep(0.01)
            p.update(task, advance=1)


def create_custom_theme_demo():
    """Demonstrate creating a custom theme."""
    console.print("\n[bold cyan]Custom Theme Demo[/bold cyan]")

    progress = ProgressBar.get_instance()

    # Define a custom theme
    custom_theme = {
        "spinner": "dots12",
        "bar_width": 40,
        "complete_style": "magenta",
        "finished_style": "bold magenta",
        "pulse_style": "bright_magenta",
        "percentage_style": "bold cyan",
        "task_progress_style": "yellow",
        "description_style": "bold green",
    }

    # Add the custom theme
    progress.add_theme("purple_dream", custom_theme)

    with progress.create(theme="purple_dream") as p:
        task = p.add_task("Custom purple theme", total=100)
        for _ in range(100):
            time.sleep(0.01)
            p.update(task, advance=1)

    # Try another custom theme with different text colors
    vibrant_theme = {
        "spinner": "bouncingBar",
        "bar_width": 35,
        "complete_style": "bright_green",
        "finished_style": "bold bright_green",
        "pulse_style": "yellow",
        "percentage_style": "bold bright_yellow",
        "task_progress_style": "bright_cyan",
        "description_style": "bold bright_white",
    }

    progress.add_theme("vibrant", vibrant_theme)

    with progress.create(theme="vibrant") as p:
        task = p.add_task("Vibrant theme with custom text colors", total=100)
        for i in range(100):
            time.sleep(0.01)
            p.update(task, advance=1)


def run_all_demos():
    """Run all demos in sequence."""
    console.print("[bold yellow]ProgressBar Class Demo[/bold yellow]")
    console.print("This demo shows the features of the singleton ProgressBar class.")

    # Run all demo functions
    basic_progress_demo()
    spinner_progress_demo()
    download_progress_demo()
    themed_progress_demo()
    multiple_tasks_demo()
    track_iteration_demo()
    for_loop_context_demo()
    indeterminate_progress_demo()
    custom_columns_demo()
    create_custom_theme_demo()

    console.print("\n[bold green]Demo complete![/bold green]")


if __name__ == "__main__":
    run_all_demos()
