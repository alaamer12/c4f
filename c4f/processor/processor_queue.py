"""Processor queue module for Commit For Free.

This module provides a thread-safe queue class for managing commit message generation tasks,
serving as a single source of truth for processing operations across different strategies.
"""

import threading
import time
from queue import Queue
from typing import Dict, List, Optional, Set, Tuple

from c4f.utils import FileChange

__all__ = ["ProcessorQueue"]


class ProcessorQueue:
    """Thread-safe queue for managing commit message generation tasks.

    This class provides a central source of truth for all processing operations,
    ensuring consistency across different processing strategies.
    """

    def __init__(self) -> None:
        """Initialize the processor queue."""
        self._queue: Queue = Queue()
        self._results: Dict[Tuple[str, ...], Optional[str]] = {}
        self._processing: Set[Tuple[str, ...]] = set()
        self._completed: Set[Tuple[str, ...]] = set()
        self._lock = threading.RLock()
        self._event = threading.Event()

    def add_group(self, group: List[FileChange]) -> Tuple[str, ...]:
        """Add a group of file changes to the queue.

        Args:
            group: List of file changes to process.

        Returns:
            Tuple[str, ...]: The group key for retrieval.
        """
        group_key = self._get_group_key(group)
        with self._lock:
            if group_key not in self._processing and group_key not in self._completed:
                self._queue.put((group_key, group))
                self._processing.add(group_key)
        return group_key

    def add_batch(self, groups: List[List[FileChange]]) -> List[Tuple[str, ...]]:
        """Add multiple groups as a batch.

        Args:
            groups: List of groups of file changes.

        Returns:
            List[Tuple[str, ...]]: List of group keys.
        """
        group_keys = []
        for group in groups:
            group_keys.append(self.add_group(group))
        return group_keys

    def get_next_group(self) -> Optional[Tuple[Tuple[str, ...], List[FileChange]]]:
        """Get the next group to process.

        Returns:
            Optional[Tuple[Tuple[str, ...], List[FileChange]]]: Tuple containing group key and file changes,
            or None if queue is empty.
        """
        try:
            return self._queue.get(block=False)  # type: ignore
        except Exception as e:
            import warnings

            warnings.warn(
                f"Failed to get next group from queue: {e}, Check if the queue is empty",
                category=UserWarning,
                stacklevel=2,
            )
            return None

    def set_result(self, group_key: Tuple[str, ...], message: Optional[str]) -> None:
        """Set the result for a processed group.

        Args:
            group_key: Key of the group.
            message: Generated commit message, or None if generation failed.
        """
        with self._lock:
            self._results[group_key] = message
            self._processing.discard(group_key)
            self._completed.add(group_key)
            self._event.set()

    def get_result(
        self, group_key: Tuple[str, ...], timeout: Optional[float] = None
    ) -> Optional[str]:
        """Get the result for a group.

        Args:
            group_key: Key of the group.
            timeout: Maximum time to wait for the result, in seconds.

        Returns:
            Optional[str]: The generated commit message, or None if not available.
        """
        start_time = time.time()
        while True:
            with self._lock:
                if group_key in self._results:
                    return self._results[group_key]

                if group_key not in self._processing:
                    # Group not found or processing failed
                    return None

                if timeout and (time.time() - start_time) > timeout:
                    return None

            # Wait for new results
            self._event.wait(timeout=0.1 if not timeout else min(0.1, timeout))
            self._event.clear()

    def get_all_results(self) -> Dict[Tuple[str, ...], Optional[str]]:
        """Get all results.

        Returns:
            Dict[Tuple[str, ...], Optional[str]]: Dictionary mapping group keys to results.
        """
        with self._lock:
            return self._results.copy()

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            bool: True if the queue is empty, False otherwise.
        """
        return self._queue.empty() and not self._processing

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all tasks to complete.

        Args:
            timeout: Maximum time to wait, in seconds.

        Returns:
            bool: True if all tasks completed, False if timed out.
        """
        start_time = time.time()
        while True:
            with self._lock:
                if not self._processing:
                    return True

                if timeout and (time.time() - start_time) > timeout:
                    return False

            self._event.wait(timeout=0.1 if not timeout else min(0.1, timeout))
            self._event.clear()

    @staticmethod
    def _get_group_key(group: List[FileChange]) -> Tuple[str, ...]:
        """Generate a unique key for a group of file changes.

        Args:
            group: List of file changes.

        Returns:
            Tuple[str, ...]: Tuple of file paths, used as a dictionary key.
        """
        return tuple(str(change.path) for change in group)

    def task_done(self) -> None:
        """Mark a task as done in the queue."""
        self._queue.task_done()

    def join(self) -> None:
        """Wait until all items in the queue have been processed."""
        self._queue.join()

    def clear(self) -> None:
        """Clear all queue data."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except Exception as e:
                    import warnings

                    warnings.warn(
                        f"Failed to clear queue: {e}",
                        category=UserWarning,
                        stacklevel=2,
                    )

            self._results.clear()
            self._processing.clear()
            self._completed.clear()
