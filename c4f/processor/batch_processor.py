"""Batch processing module for Commit For Free.

This module provides classes for batch processing of commit message generation,
allowing for faster response times when dealing with multiple groups of changes.
"""

import concurrent.futures
import threading
from pathlib import Path
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
from c4f.processor.base import Processor
from c4f.processor.processor_queue import ProcessorQueue
from c4f.utils import FileChange, console

__all__ = ["BatchProcessor"]


class BatchProcessor(Processor):
    """Processes multiple groups of changes in batches."""

    def __init__(self, config: Config, batch_size: int = 3) -> None:
        """Initialize the batch processor.

        Args:
            config: Configuration object with settings for the commit message generator.
            batch_size: Maximum number of groups to process in a single batch.
        """
        self.config = config
        self.console = console
        self.batch_size = batch_size if batch_size else config.batch_size
        self.messages: Dict[Tuple[str, ...], Optional[str]] = {}
        self.queue = ProcessorQueue()
        self._stop_event = threading.Event()
        self._batch_cache: Dict[Tuple[Tuple[str, ...], ...], Optional[str]] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def create_combined_context(groups: List[List[FileChange]]) -> str:
        """Create a combined context string from multiple groups of changes.

        Args:
            groups: List of groups of file changes.

        Returns:
            str: Combined context string.
        """
        from c4f.main import create_combined_context

        all_changes = [change for group in groups for change in group]
        return create_combined_context(all_changes)

    def generate_batch_message(self, groups: List[List[FileChange]]) -> Optional[str]:
        """Generate a commit message for a batch of groups.

        Args:
            groups: List of groups of file changes.

        Returns:
            Optional[str]: The generated commit message, or None if generation failed.
        """
        # Check if this exact batch is in cache
        batch_key = tuple(
            tuple(str(change.path) for change in group) for group in groups
        )
        with self._cache_lock:
            if batch_key in self._batch_cache:
                return self._batch_cache[batch_key]

        from c4f.main import generate_commit_message

        try:
            # Combine all changes from all groups
            all_changes = [change for group in groups for change in group]

            # Generate a message for all changes
            message = generate_commit_message(all_changes, self.config)

            # Cache the result
            with self._cache_lock:
                self._batch_cache[batch_key] = message

        except Exception as e:
            self.console.print(f"[red]Error generating batch message: {e!s}[/red]")
            return None
        else:
            return message

    def split_message_for_groups(
        self, message: str, groups: List[List[FileChange]]
    ) -> Dict[Tuple[str, ...], str]:
        """Split a batch message into parts for individual groups.

        This is a more sophisticated implementation that tries to analyze the message
        and split it based on the content of each group, using file names as hints.

        Args:
            message: The batch commit message.
            groups: List of groups of file changes.

        Returns:
            Dict[Tuple[str, ...], str]: Dictionary mapping group keys to message parts.
        """
        if "\n- " in message:
            return self._split_message_with_bullets(message, groups)
        return self._assign_full_message_to_groups(message, groups)

    def _split_message_with_bullets(
        self, message: str, groups: List[List[FileChange]]
    ) -> Dict[Tuple[str, ...], str]:
        """Split a multipart message into parts for individual groups based on bullet points.

        Args:
            message: The batch commit message.
            groups: List of groups of file changes.

        Returns:
            Dict[Tuple[str, ...], str]: Dictionary mapping group keys to message parts.
        """
        result = {}
        header, bullet_points = self._extract_header_and_bullets(message)

        for group in groups:
            group_key = tuple(str(change.path) for change in group)
            best_match = self._find_best_matching_bullet(group, bullet_points)

            if best_match:
                result[group_key] = f"{header}\n{best_match}"
            else:
                result[group_key] = message

        return result

    @staticmethod
    def _extract_header_and_bullets(message: str) -> Tuple[str, List[str]]:
        """Extract the header and bullet points from the message.

        Args:
            message: The batch commit message.

        Returns:
            Tuple[str, List[str]]: The header and list of bullet points.
        """
        header = message.split("\n- ")[0].strip()
        bullet_points = ["- " + point for point in message.split("\n- ")[1:]]
        return header, bullet_points

    def _find_best_matching_bullet(
        self, group: List[FileChange], bullet_points: List[str]
    ) -> Optional[str]:
        """Find the bullet point that best matches the files in the group.

        Args:
            group: List of file changes.
            bullet_points: List of bullet points from the message.

        Returns:
            Optional[str]: The best matching bullet point or None if no match is found.
        """
        file_names = [change.path.name for change in group]
        best_match = None
        best_score = 0

        for bullet in bullet_points:
            score = self._calculate_bullet_score(bullet, file_names)
            if score > best_score:
                best_score = score
                best_match = bullet

        return best_match if best_score >= 2 else None  # noqa: PLR2004

    @staticmethod
    def _calculate_bullet_score(bullet: str, file_names: List[str]) -> int:
        """Calculate the score for a bullet point based on file names.

        Args:
            bullet: A bullet point from the message.
            file_names: List of file names in the group.

        Returns:
            int: The calculated score for the bullet.
        """
        score = 0
        for file_name in file_names:
            if file_name.lower() in bullet.lower():
                score += 3
            elif any(ext.lower() in bullet.lower() for ext in [Path(file_name).suffix]):
                score += 1
        return score

    @staticmethod
    def _assign_full_message_to_groups(
        message: str, groups: List[List[FileChange]]
    ) -> Dict[Tuple[str, ...], str]:
        """Assign the full message to all groups.

        Args:
            message: The batch commit message.
            groups: List of groups of file changes.

        Returns:
            Dict[Tuple[str, ...], str]: Dictionary mapping group keys to the full message.
        """
        return {
            tuple(str(change.path) for change in group): message for group in groups
        }

    def process_batches(self, groups: List[List[FileChange]]) -> None:
        """Process groups in batches.

        Args:
            groups: List of groups of file changes.
        """
        batches = self._split_into_batches(groups)
        self._display_batch_info(len(groups), len(batches))
        batch_messages = self._process_batches_with_progress(batches)
        self._update_messages_dict(batch_messages)
        self.process_groups_with_messages(groups)

    def _split_into_batches(
        self, groups: List[List[FileChange]]
    ) -> List[List[List[FileChange]]]:
        """Split groups into batches of specified size.

        Args:
            groups: List of groups of file changes.

        Returns:
            List of batches, where each batch contains multiple groups.
        """
        return [
            groups[i : i + self.batch_size]
            for i in range(0, len(groups), self.batch_size)
        ]

    def _display_batch_info(self, group_count: int, batch_count: int) -> None:
        """Display information about the batches to be processed.

        Args:
            group_count: Total number of groups.
            batch_count: Total number of batches.
        """
        self.console.print(
            f"[bold blue]Processing {group_count} groups in {batch_count} batches...[/bold blue]"
        )

    def _process_batches_with_progress(
        self, batches: List[List[List[FileChange]]]
    ) -> Dict[Tuple[str, ...], str]:
        """Process batches with a progress bar.

        Args:
            batches: List of batches to process.

        Returns:
            Dictionary mapping group keys to messages.
        """
        all_batch_messages = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            batch_task = progress.add_task("Processing batches...", total=len(batches))
            batch_messages = self._process_batches_in_parallel(
                batches, progress, batch_task
            )
            all_batch_messages.update(batch_messages)

        return all_batch_messages

    def _process_batches_in_parallel(
        self,
        batches: List[List[List[FileChange]]],
        progress: Progress,
        batch_task: TaskID,
    ) -> Dict[Tuple[str, ...], str]:
        """Process batches in parallel using a thread pool.

        Args:
            batches: List of batches to process.
            progress: Progress instance for updating progress.
            batch_task: Task ID for the batch processing task.

        Returns:
            Dictionary mapping group keys to messages.
        """
        all_messages = {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(batches), self.config.MAX_WORKERS)
        ) as executor:
            # Submit batch processing tasks
            batch_futures = {
                executor.submit(self._process_batch, batch): batch_idx
                for batch_idx, batch in enumerate(batches)
            }

            # Wait for all batches to complete
            for future in concurrent.futures.as_completed(batch_futures):
                batch_idx = batch_futures[future]
                batch_messages = self._handle_batch_future(future, batch_idx)
                all_messages.update(batch_messages)
                progress.advance(batch_task)

        return all_messages

    def _handle_batch_future(
        self, future: concurrent.futures.Future, batch_idx: int
    ) -> Dict[Tuple[str, ...], str]:
        """Handle the result of a batch processing future.

        Args:
            future: Future object containing the batch processing result.
            batch_idx: Index of the batch being processed.

        Returns:
            Dictionary mapping group keys to messages.
        """
        try:
            # Get the result
            batch_messages = future.result()
        except Exception as e:
            self.console.print(f"[red]Error processing batch {batch_idx}: {e!s}[/red]")
            return {}
        else:
            return batch_messages or {}

    def _update_messages_dict(self, batch_messages: Dict[Tuple[str, ...], str]) -> None:
        """Update the messages dictionary with batch messages.

        Args:
            batch_messages: Dictionary mapping group keys to messages.
        """
        self.messages.update(batch_messages)

    def _process_batch(
        self, batch: List[List[FileChange]]
    ) -> Dict[Tuple[str, ...], str]:
        """Process a single batch of groups.

        Args:
            batch: List of groups to process as a batch

        Returns:
            Dict[Tuple[str, ...], str]: Dictionary mapping group keys to messages
        """
        if self._stop_event.is_set():
            return {}

        try:
            # Generate a message for the batch
            batch_message = self.generate_batch_message(batch)

            if not batch_message:
                return {}

            # Split the message for each group
            return self.split_message_for_groups(batch_message, batch)
        except Exception as e:
            self.console.print(f"[red]Error in batch processing: {e!s}[/red]")
            return {}

    def process_groups_with_messages(self, groups: List[List[FileChange]]) -> None:
        """Process groups with their messages.

        Args:
            groups: List of groups of file changes.
        """
        from c4f.processor.parallel_processor import ParallelProcessor

        # Use the ParallelProcessor to process the groups
        processor = ParallelProcessor(self.config)
        processor.messages = self.messages
        processor.process_groups(groups)

    def process_batches_sequential(self, groups: List[List[FileChange]]) -> None:
        """Process groups in batches sequentially (fallback if threading fails).

        Args:
            groups: List of groups of file changes.
        """
        batches = self._split_into_batches(groups)
        self._display_batch_info(len(groups), len(batches))
        self._process_batches_with_progress(batches)
        self.process_groups_with_messages(groups)

    def _process_single_batch(self, batch: List[List[FileChange]]) -> None:
        """Process a single batch and store the resulting messages.

        Args:
            batch: A batch of file change groups to process.
        """
        batch_message = self.generate_batch_message(batch)

        if batch_message:
            group_messages = self.split_message_for_groups(batch_message, batch)
            self._store_messages(group_messages)

    def _store_messages(self, group_messages: Dict[Tuple[str, ...], str]) -> None:
        """Store generated messages in the messages dictionary.

        Args:
            group_messages: Dictionary mapping group keys to messages.
        """
        for group_key, message in group_messages.items():
            self.messages[group_key] = message

    def stop(self) -> None:
        """Stop all processing."""
        self._stop_event.set()

    def process_groups(self, groups: List[List[FileChange]]) -> None:
        """Process groups of file changes in batches.

        Implementation of the abstract method from the base Processor class.

        Args:
            groups: List of groups of file changes.
        """
        try:
            self.process_batches(groups)
        except Exception as e:
            self.console.print(f"[red]Error in batch processing: {e!s}[/red]")
            self.console.print(
                "[yellow]Falling back to sequential batch processing...[/yellow]"
            )
            self.process_batches_sequential(groups)
