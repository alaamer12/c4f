import threading
from typing import List

from c4f.config import Config
from c4f.processor.base import Processor
from c4f.utils import FileChange, console


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
