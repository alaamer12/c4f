from abc import ABC, abstractmethod
from typing import List

from c4f.config import Config
from c4f.utils import FileChange


class Processor(ABC):
    """Base abstract processor class that all processor implementations should inherit from."""

    config: Config

    @abstractmethod
    def __init__(self, config: Config) -> None:
        """Initialize the processor with configuration.

        Args:
            config: Configuration object with settings for the commit message generator.
        """
        self.config = config

    @abstractmethod
    def stop(self) -> None:
        """Stop processing."""

    @abstractmethod
    def process_groups(self, groups: List[List[FileChange]]) -> None:
        """Process groups of file changes.

        Args:
            groups: List of groups of file changes.
        """
