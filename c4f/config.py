"""Configuration module for c4f (Commit For Free).

This module provides a configuration class that holds all the settings
for the commit message generator.
"""

from typing import Union

import g4f  # type: ignore

# Type alias for the supported model types
MODEL_TYPE = Union[g4f.Model, g4f.models, str]

class Config:
    """Configuration class for c4f.
    
    This class holds all the configuration settings for the commit message generator.
    It can be instantiated with default values or customized values.
    
    Attributes:
        force_brackets: Whether to force brackets in commit messages.
        prompt_threshold: Threshold in lines to determine comprehensive messages.
        fallback_timeout: Timeout in seconds before falling back to simple messages.
        min_comprehensive_length: Minimum length for comprehensive commit messages.
        attempt: Number of attempts to generate a commit message.
        diff_max_length: Maximum number of lines to include in diff snippets.
        model: The AI model to use for generating commit messages. Can be a g4f.Model object,
              a g4f.models enum value, or a string (which will be converted to a Model object).
    """
    
    def __init__(
        self,
        force_brackets: bool = False,
        prompt_threshold: int = 80,
        fallback_timeout: int = 10,
        min_comprehensive_length: int = 50,
        attempt: int = 3,
        diff_max_length: int = 100,
        model: MODEL_TYPE = g4f.models.gpt_4o_mini
    ):
        """Initialize the configuration with the given values.
        
        Args:
            force_brackets: Whether to force brackets in commit messages.
            prompt_threshold: Threshold in lines to determine comprehensive messages.
            fallback_timeout: Timeout in seconds before falling back to simple messages.
            min_comprehensive_length: Minimum length for comprehensive commit messages.
            attempt: Number of attempts to generate a commit message.
            diff_max_length: Maximum number of lines to include in diff snippets.
            model: The AI model to use for generating commit messages.
        """
        self.force_brackets: bool = force_brackets
        self.prompt_threshold: int = prompt_threshold
        self.fallback_timeout: float = fallback_timeout
        self.min_comprehensive_length: int = min_comprehensive_length
        self.attempt: int = attempt
        self.diff_max_length: int = diff_max_length
        self.model: MODEL_TYPE = model

# Default configuration instance
default_config = Config()