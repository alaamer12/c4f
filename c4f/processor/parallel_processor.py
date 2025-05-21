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
    TaskID,
    TaskProgressColumn,
    TextColumn,
)

from c4f.config import Config
from c4f.main import (
    display_commit_preview,
    do_group_commit,
    get_valid_user_response,
    handle_user_response,
    process_change_group,
)
from c4f.processor.base import Processor
from c4f.processor.processor_queue import ProcessorQueue
from c4f.utils import FileChange, console

__all__ = ["MessageGenerator", "ParallelProcessor"]


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
        self._announce_pre_generation()
        self._queue_all_groups(groups)
        self._process_groups_in_parallel(len(groups))
        return self._collect_results()

    def _announce_pre_generation(self) -> None:
        """Announce the start of pre-generating commit messages."""
        self.console.print(
            "[bold blue]Pre-generating commit messages for all groups...[/bold blue]"
        )

    def _queue_all_groups(self, groups: List[List[FileChange]]) -> None:
        """Add all groups to the processing queue.

        Args:
            groups: List of groups of file changes.
        """
        for group in groups:
            self.queue.add_group(group)

    def _process_groups_in_parallel(self, total_groups: int) -> None:
        """Process all queued groups in parallel with a progress bar.

        Args:
            total_groups: Total number of groups to process.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Generating messages...", total=total_groups)
            self._execute_parallel_tasks(total_groups, progress, task)

    def _execute_parallel_tasks(
        self, total_tasks: int, progress: Progress, task_id: TaskID
    ) -> None:
        """Execute tasks in parallel using a thread pool.

        Args:
            total_tasks: Total number of tasks to execute.
            progress: Progress bar instance.
            task_id: ID of the progress bar task.
        """
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.MAX_WORKERS
        ) as executor:
            futures = self._submit_tasks(executor, total_tasks)
            self._process_completed_futures(futures, progress, task_id)

    def _submit_tasks(
        self, executor: concurrent.futures.ThreadPoolExecutor, total_tasks: int
    ) -> List[concurrent.futures.Future]:
        """Submit tasks to the executor.

        Args:
            executor: ThreadPoolExecutor instance.
            total_tasks: Number of tasks to submit.

        Returns:
            List of futures for submitted tasks.
        """
        futures = []
        for _ in range(total_tasks):
            future = executor.submit(self._process_next_group_from_queue)
            futures.append(future)
        return futures

    def _process_completed_futures(
        self,
        futures: List[concurrent.futures.Future],
        progress: Progress,
        task_id: TaskID,
    ) -> None:
        """Process completed futures and update progress.

        Args:
            futures: List of futures to process.
            progress: Progress bar instance.
            task_id: ID of the progress bar task.
        """
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
                progress.advance(task_id)
            except Exception as e:
                self.console.print(f"[red]Error in worker thread: {e!s}[/red]")
                progress.advance(task_id)

    def _collect_results(self) -> Dict[Tuple[str, ...], Optional[str]]:
        """Collect all results from the queue.

        Returns:
            Dictionary mapping group keys to generated messages.
        """
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
        """Process a group with a pre-generated message."""

        if message is None:
            return self._handle_missing_message(group)

        return self._process_with_existing_message(group, message)

    def _handle_missing_message(self, group: List[FileChange]) -> bool:
        """Handle the case when no pre-generated message is available.

        Args:
            group: List of file changes to process.

        Returns:
            bool: Result from the fallback processing.
        """

        self.console.print(
            "[yellow]No pre-generated message available, falling back to normal processing[/yellow]"
        )
        return process_change_group(group, self.config)

    def _process_with_existing_message(
        self, group: List[FileChange], message: str, accept_all: bool = False
    ) -> bool:
        """Process a group with an existing pre-generated message.

        Args:
            group: List of file changes to process.
            message: Pre-generated commit message.
            accept_all: Whether to automatically accept the commit.

        Returns:
            bool: True if the user chose to accept all future commits.
        """
        rendered_message = self._render_markdown_message(message)
        display_commit_preview(rendered_message)

        if accept_all:
            return do_group_commit(group, message, True)

        response = get_valid_user_response()
        return handle_user_response(response, group, message)

    def _render_markdown_message(self, message: str) -> str:
        """Render a markdown message to a string.

        Args:
            message: Markdown message to render.

        Returns:
            str: Rendered markdown as a string.
        """
        from rich.markdown import Markdown

        md = Markdown(message)

        with self.console.capture() as capture:
            self.console.print(md, end="")  # Ensure no extra newline

        return capture.get()

    def process_groups(self, groups: List[List[FileChange]]) -> None:
        """Process all groups with pre-generated messages.

        Args:
            groups: List of groups of file changes.
        """
        # Pre-generate messages for all groups
        self.pre_generate_messages(groups)

        # Process each group with its pre-generated message
        accept_all = False
        for group in groups:
            if self._check_if_stopped():
                break

            group_key = self._get_group_key(group)
            message = self.messages.get(group_key)

            if accept_all:
                accept_all = self._process_with_auto_accept(group, message)
            else:
                accept_all = self._process_with_user_confirmation(group, message)

    def _check_if_stopped(self) -> bool:
        """Check if processing has been stopped.

        Returns:
            bool: True if processing should stop, False otherwise.
        """
        if self._stop_event.is_set():
            self.console.print("[yellow]Processing stopped by user or error[/yellow]")
            return True
        return False

    @staticmethod
    def _get_group_key(group: List[FileChange]) -> Tuple[str, ...]:
        """Get the key for a group of file changes."""
        return tuple(str(change.path) for change in group)

    @staticmethod
    def _process_with_auto_accept(
        group: List[FileChange], message: Optional[str]
    ) -> bool:
        """Process a group with automatic acceptance.

        Args:
            group: List of file changes to process.
            message: Pre-generated commit message.

        Returns:
            bool: True to continue auto-accepting commits.
        """
        # If user chose to accept all, just commit without showing the message
        fallback_message = (
            f"{group[0].type}: update {' '.join(str(c.path.name) for c in group)}"
        )
        do_group_commit(
            group,
            message or fallback_message,
            True,
        )
        return True

    def _process_with_user_confirmation(
        self, group: List[FileChange], message: Optional[str]
    ) -> bool:
        """Process a group with user confirmation.

        Args:
            group: List of file changes to process.
            message: Pre-generated commit message.

        Returns:
            bool: True if user chose to accept all future commits.
        """
        try:
            return self.process_group_with_message(group, message)
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt()
            return False
        except Exception as e:
            self._handle_processing_error(e)
            return False

    def _handle_keyboard_interrupt(self) -> None:
        """Handle keyboard interrupt during processing."""
        self.console.print("[yellow]Processing interrupted by user[/yellow]")
        self._stop_event.set()

    def _handle_processing_error(self, error: Exception) -> None:
        """Handle errors during group processing.

        Args:
            error: The exception that occurred.
        """
        self.console.print(f"[red]Error processing group: {error!s}[/red]")
        # Continue with next group without stopping completely

    def stop(self) -> None:
        """Stop all processing."""
        self._stop_event.set()
