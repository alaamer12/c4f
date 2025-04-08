"""Configuration module for c4f (Commit For Free).

This module provides a configuration class that holds all the settings
for the commit message generator.
"""

from typing import Union

import g4f  # type: ignore

# Type alias for the supported model types
MODEL_TYPE = Union[g4f.Model, g4f.models, str]

from dataclasses import dataclass, field
from typing import Optional, ClassVar


@dataclass
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
	# Default values
	force_brackets: bool = False
	prompt_threshold: int = 80
	fallback_timeout: float = 10.0
	min_comprehensive_length: int = 50
	attempt: int = 3
	diff_max_length: int = 100
	model: MODEL_TYPE = field(default=g4f.models.gpt_4o_mini)
	
	# Validation constraints
	MIN_THRESHOLD: ClassVar[int] = 10
	MAX_THRESHOLD: ClassVar[int] = 500
	MIN_TIMEOUT: ClassVar[float] = 1.0
	MAX_TIMEOUT: ClassVar[float] = 60.0
	MIN_ATTEMPTS: ClassVar[int] = 1
	MAX_ATTEMPTS: ClassVar[int] = 10
	
	def __post_init__(self) -> None:
		"""Validate configuration settings after initialization.
		
		Raises:
			ValueError: If any configuration setting is invalid.
		"""
		error_message = self._validate()
		if error_message:
			raise ValueError(f"Invalid configuration: {error_message}")
	
	def _validate(self) -> Optional[str]:
		"""Validate the configuration settings.
		
		Returns:
			Optional[str]: Error message if validation fails, None otherwise.
		"""
		# Define validation rules as a list of (condition, error_message) tuples
		validation_rules = [
			(not isinstance(self.force_brackets, bool),
			 "force_brackets must be a boolean value"),
			
			(not isinstance(self.prompt_threshold, int) or 
			 not self.MIN_THRESHOLD <= self.prompt_threshold <= self.MAX_THRESHOLD,
			 f"prompt_threshold must be an integer between {self.MIN_THRESHOLD} and {self.MAX_THRESHOLD}"),
			
			(not isinstance(self.fallback_timeout, (int, float)) or 
			 not self.MIN_TIMEOUT <= self.fallback_timeout <= self.MAX_TIMEOUT,
			 f"fallback_timeout must be a number between {self.MIN_TIMEOUT} and {self.MAX_TIMEOUT}"),
			
			(not isinstance(self.min_comprehensive_length, int) or self.min_comprehensive_length < 0,
			 "min_comprehensive_length must be a non-negative integer"),
			
			(not isinstance(self.attempt, int) or 
			 not self.MIN_ATTEMPTS <= self.attempt <= self.MAX_ATTEMPTS,
			 f"attempt must be an integer between {self.MIN_ATTEMPTS} and {self.MAX_ATTEMPTS}"),
			
			(not isinstance(self.diff_max_length, int) or self.diff_max_length < 0,
			 "diff_max_length must be a non-negative integer")
		]
		
		# Check each validation rule and return the first error found
		for condition, error_message in validation_rules:
			if condition:
				return error_message
				
		return None

	def is_valid(self) -> bool:
		"""Check if the configuration is valid.
		
		Returns:
			bool: True if the configuration is valid, False otherwise.
		"""
		return self._validate() is None


# Default configuration instance
default_config = Config()
