"""Parallel processing module for Commit For Free.

This module provides classes for parallel processing of commit message generation,
allowing for faster response times when dealing with multiple groups of changes.
"""

import concurrent.futures
import threading
from typing import Dict, List, Optional, Tuple

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from c4f.base import Processor
from c4f.config import Config
from c4f.main import (
    display_commit_preview,
    do_group_commit,
    get_valid_user_response,
    handle_user_response,
)
from c4f.processor.processor_queue import ProcessorQueue
from c4f.utils import FileChange, console


class MessageGenerator:
    """Handles the generation of commit messages for groups of changes."""

    def __init__(self, config: Config) -> None:
        """Initialize the message generator.

        Args:
            config: Configuration object with settings for the commit message generator.
        """
        self.config = config
        self.console = console
        self._cache: Dict[Tuple[str, ...], Optional[str]] = {}
        self._cache_lock = threading.Lock()

    def generate_message_for_group(self, group: List[FileChange]) -> Optional[str]:
        """Generate a commit message for a group of changes.

        Args:
            group: List of file changes to generate a message for.

        Returns:
            Optional[str]: The generated commit message, or None if generation failed.
        """
        # Check cache first
        group_key = tuple(str(change.path) for change in group)
        with self._cache_lock:
            if group_key in self._cache:
                return self._cache[group_key]

        from c4f.main import generate_commit_message

        try:
            message = generate_commit_message(group, self.config)
            # Cache the result
            with self._cache_lock:
                self._cache[group_key] = message
        except Exception as e:
            self.console.print(f"[red]Error generating message for group: {e!s}[/red]")
            return None
        else:
            return message


class ParallelProcessor(Processor):
    """Processes multiple groups of changes in parallel."""

    def __init__(self, config: Config) -> None:
        """Initialize the parallel processor.

        Args:
            config: Configuration object with settings for the commit message generator.
        """
        self.config = config
        self.console = console
        self.message_generator = MessageGenerator(config)
        self.messages: Dict[Tuple[str, ...], Optional[str]] = {}
        self.queue = ProcessorQueue()
        self._stop_event = threading.Event()

    def pre_generate_messages(
        self, groups: List[List[FileChange]]
    ) -> Dict[Tuple[str, ...], Optional[str]]:
        """Pre-generate commit messages for all groups in parallel.

        Args:
            groups: List of groups of file changes.

        Returns:
            Dict[Tuple[str, ...], Optional[str]]: Dictionary mapping group keys to generated messages.
        """
        self.console.print(
            "[bold blue]Pre-generating commit messages for all groups...[/bold blue]"
        )

        # Add all groups to the queue
        for group in groups:
            self.queue.add_group(group)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Generating messages...", total=len(groups))

            # Create a thread pool with the configured number of workers
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.MAX_WORKERS
            ) as executor:
                # Track futures for all submitted tasks
                futures = []

                # Submit tasks for all groups
                for _ in range(len(groups)):
                    future = executor.submit(self._process_next_group_from_queue)
                    futures.append(future)

                # Wait for all futures to complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        # Each completed future should return a group key
                        future.result()
                        progress.advance(task)
                    except Exception as e:
                        self.console.print(f"[red]Error in worker thread: {e!s}[/red]")
                        progress.advance(task)

        # Get all results from the queue
        self.messages = self.queue.get_all_results()
        return self.messages

    def _process_next_group_from_queue(self) -> Optional[Tuple[str, ...]]:
        """Process the next group from the queue.

        Returns:
            Optional[Tuple[str, ...]]: The group key that was processed, or None if queue was empty.
        """
        next_item = self.queue.get_next_group()
        if not next_item:
            return None

        group_key, group = next_item

        try:
            # Generate message for the group
            message = self.message_generator.generate_message_for_group(group)

            # Set the result in the queue
            self.queue.set_result(group_key, message)
            self.queue.task_done()

        except Exception as e:
            self.console.print(f"[red]Error processing group: {e!s}[/red]")
            self.queue.set_result(group_key, None)
            self.queue.task_done()
            return group_key
        else:
            return group_key

    def process_group_with_message(
        self, group: List[FileChange], message: Optional[str]
    ) -> bool:
        """Process a group with a pre-generated message.

        Args:
            group: List of file changes to process.
            message: Pre-generated commit message.

        Returns:
            bool: True if the user chose to accept all future commits.
        """
        from c4f.main import process_change_group

        if message is None:
            # If no message was generated, fall back to normal processing
            self.console.print(
                "[yellow]No pre-generated message available, falling back to normal processing[/yellow]"
            )
            return process_change_group(group, self.config)

        # Create a modified version of process_change_group that uses the pre-generated message
        def process_with_message(
            group: List[FileChange], accept_all: bool = False
        ) -> bool:
            # Style Message
            from rich.markdown import Markdown

            md = Markdown(message)

            # Capture the rendered Markdown output
            with self.console.capture() as capture:
                self.console.print(md, end="")  # Ensure no extra newline
            rendered_message = capture.get()

            display_commit_preview(
                rendered_message
            )  # Pass the properly rendered string

            if accept_all:
                return do_group_commit(group, message, True)

            response = get_valid_user_response()
            return handle_user_response(response, group, message)

        return process_with_message(group)

    def process_all_groups(self, groups: List[List[FileChange]]) -> None:
        """Process all groups with pre-generated messages.

        Args:
            groups: List of groups of file changes.
        """
        # Pre-generate messages for all groups
        self.pre_generate_messages(groups)

        # Process each group with its pre-generated message
        accept_all = False
        for group in groups:
            if self._stop_event.is_set():
                self.console.print(
                    "[yellow]Processing stopped by user or error[/yellow]"
                )
                break

            group_key = tuple(str(change.path) for change in group)
            message = self.messages.get(group_key)

            if accept_all:
                # If user chose to accept all, just commit without showing the message

                do_group_commit(
                    group,
                    message
                    or f"{group[0].type}: update {' '.join(str(c.path.name) for c in group)}",
                    True,
                )
            else:
                # Process the group with its pre-generated message
                try:
                    accept_all = self.process_group_with_message(group, message)
                except KeyboardInterrupt:
                    self.console.print(
                        "[yellow]Processing interrupted by user[/yellow]"
                    )
                    self._stop_event.set()
                    break
                except Exception as e:
                    self.console.print(f"[red]Error processing group: {e!s}[/red]")
                    # Continue with next group without stopping completely

    def stop(self) -> None:
        """Stop all processing."""
        self._stop_event.set()
