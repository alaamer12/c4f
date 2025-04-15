"""Processor factory module for Commit For Free.

This module provides a factory class for creating and managing different processing strategies
for commit message generation.
"""

import threading
from enum import Enum, auto
from typing import Any, Dict, List, Type

from c4f.base import Processor
from c4f.config import Config
from c4f.utils import FileChange, console


class ProcessingStrategy(Enum):
    """Enum for different processing strategies."""

    SEQUENTIAL = auto()  # Original sequential processing
    PARALLEL = auto()  # Parallel processing of groups
    BATCH = auto()  # Batch processing of groups

    def __str__(self) -> str:
        """Return a string representation of the strategy."""
        return self.name.lower()


class ProcessorFactory:
    """Factory class for creating and managing different processing strategies."""

    _instances: Dict[ProcessingStrategy, Any] = {}
    _instance_lock = threading.Lock()

    @classmethod
    def create_processor(
        cls, strategy: ProcessingStrategy, config: Config, **kwargs: dict
    ):
        """Create or get a processor for the specified strategy.

        This method implements a singleton pattern for processors, creating
        a new processor only if one doesn't already exist for the given strategy.

        Args:
            strategy: The processing strategy to use.
            config: Configuration object with settings for the commit message generator.
            **kwargs: Additional arguments for the processor.

        Returns:
            Any: The processor instance.

        Raises:
            ValueError: If the strategy is unknown.
        """
        # Check if we should reuse an existing instance
        with cls._instance_lock:
            if strategy in cls._instances and config is cls._instances[strategy].config:
                return cls._instances[strategy]

            # Create a new processor
            processor = cls._create_new_processor(strategy, config, **kwargs)
            cls._instances[strategy] = processor
            return processor

    @classmethod
    def _create_new_processor(
        cls, strategy: ProcessingStrategy, config: Config, **kwargs: dict
    ) -> Type[Processor]:
        """Create a new processor instance.

        Args:
            strategy: The processing strategy to use.
            config: Configuration object with settings for the commit message generator.
            **kwargs: Additional arguments for the processor.

        Returns:
            Any: The new processor instance.

        Raises:
            ValueError: If the strategy is unknown.
        """
        # Import these here to avoid circular imports
        from c4f.processor.batch_processor import BatchProcessor
        from c4f.processor.parallel_processor import ParallelProcessor

        if strategy == ProcessingStrategy.SEQUENTIAL:
            return SequentialProcessor(config)
        if strategy == ProcessingStrategy.PARALLEL:
            return ParallelProcessor(config)
        if strategy == ProcessingStrategy.BATCH:
            batch_size = int(kwargs.get("batch_size", config.batch_size))  # type: ignore
            return BatchProcessor(config, batch_size)
        ve = f"Unknown processing strategy: {strategy}"
        raise ValueError(ve)

    @classmethod
    def determine_best_strategy(
        cls, groups: List[List[FileChange]], config: Config
    ) -> ProcessingStrategy:
        """Determine the best processing strategy based on the number of groups.

        Args:
            groups: List of groups of file changes.
            config: Configuration object with settings for the commit message generator.

        Returns:
            ProcessingStrategy: The recommended processing strategy.
        """
        # Disable parallel/batch processing if configured to do so
        if not config.parallel_processing and not config.batch_processing:
            return ProcessingStrategy.SEQUENTIAL

        # Determine based on number of groups
        if len(groups) <= 1:
            # For a single group, use sequential processing
            return ProcessingStrategy.SEQUENTIAL
        if len(groups) <= 3 and config.parallel_processing:  # noqa: PLR2004
            # For a few groups, use parallel processing if enabled
            return ProcessingStrategy.PARALLEL
        if config.batch_processing:
            # For many groups, use batch processing if enabled
            return ProcessingStrategy.BATCH
        if config.parallel_processing:
            # Fall back to parallel if batch is disabled but parallel is enabled
            return ProcessingStrategy.PARALLEL
        # Fall back to sequential as a last resort
        return ProcessingStrategy.SEQUENTIAL

    @classmethod
    def clear_instances(cls) -> None:
        """Clear all cached processor instances."""
        with cls._instance_lock:
            for processor in cls._instances.values():
                if hasattr(processor, "stop"):
                    processor.stop()
            cls._instances.clear()


class SequentialProcessor(Processor):
    """Processes groups of changes sequentially (original implementation)."""

    def __init__(self, config: Config) -> None:
        """Initialize the sequential processor.

        Args:
            config: Configuration object with settings for the commit message generator.
        """
        self.config = config
        self.console = console
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Stop processing."""
        self._stop_event.set()

    def process_groups(self, groups: List[List[FileChange]]) -> None:
        """Process groups sequentially.

        Args:
            groups: List of groups of file changes.
        """
        for group in groups:
            if self._stop_event.is_set():
                self._handle_processing_stopped()
                break

            self._process_group(group)

    def _process_group(self, group: List[FileChange]) -> bool:
        """Process a single group of changes.

        Args:
            group: List of file changes to process.
        """
        from c4f.main import process_change_group

        try:
            accept_all = process_change_group(group, self.config)
        except KeyboardInterrupt:
            self.console.print("[yellow]Processing interrupted by user[/yellow]")
            self._stop_event.set()
        except Exception as e:
            self.console.print(f"[red]Error processing group: {e!s}[/red]")
            self._stop_event.set()
        else:
            return accept_all

        return False

    def _handle_processing_stopped(self) -> None:
        """Handle the event when processing is stopped."""
        self.console.print("[yellow]Processing stopped[/yellow]")
