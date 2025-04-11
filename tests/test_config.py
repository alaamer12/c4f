"""Tests for the Config class.

This module contains tests for the Config class, covering all possible paths and combinations.
"""

from unittest.mock import patch

import g4f  # type: ignore
import pytest

from c4f.config import Config


class TestConfig:
    """Test suite for the Config class."""

    def test_default_config(self):
        """Test that the default configuration is valid."""
        config = Config()
        assert config.is_valid()
        assert config.force_brackets is False
        assert config.prompt_threshold == 80
        assert config.fallback_timeout == 10.0
        assert config.min_comprehensive_length == 50
        assert config.attempt == 3
        assert config.diff_max_length == 100
        assert config.model == g4f.models.gpt_4o_mini

    def test_custom_config(self):
        """Test creating a custom configuration with valid values."""
        config = Config(
            force_brackets=True,
            prompt_threshold=100,
            fallback_timeout=15.0,
            min_comprehensive_length=60,
            attempt=5,
            diff_max_length=150,
            model=g4f.models.gpt_4o,
        )
        assert config.is_valid()
        assert config.force_brackets is True
        assert config.prompt_threshold == 100
        assert config.fallback_timeout == 15.0
        assert config.min_comprehensive_length == 60
        assert config.attempt == 5
        assert config.diff_max_length == 150
        assert config.model == g4f.models.gpt_4o

    def test_model_as_string(self):
        """Test setting the model as a string."""
        config = Config(model="gpt-4o")
        assert config.is_valid()
        assert isinstance(config.model, str)
        assert config.model == "gpt-4o"

    def test_model_as_g4f_model(self):
        """Test setting the model as a g4f.Model object."""
        # Create a mock g4f.Model object
        mock_model = g4f.Model("test-model", "test-provider")
        config = Config(model=mock_model)
        assert config.is_valid()
        assert isinstance(config.model, g4f.Model)
        assert config.model == mock_model

    @pytest.mark.parametrize(
        "invalid_value,expected_error",
        [
            (None, "force_brackets must be a boolean value"),
            (1, "force_brackets must be a boolean value"),
            ("True", "force_brackets must be a boolean value"),
        ],
    )
    def test_invalid_force_brackets(self, invalid_value, expected_error):
        """Test validation of force_brackets with invalid values."""
        with pytest.raises(ValueError) as excinfo:
            Config(force_brackets=invalid_value)
        assert f"Invalid configuration: {expected_error}" in str(excinfo.value)

    @pytest.mark.parametrize(
        "invalid_value,expected_error",
        [
            (None, "prompt_threshold must be an integer between 10 and 500"),
            (5, "prompt_threshold must be an integer between 10 and 500"),
            (600, "prompt_threshold must be an integer between 10 and 500"),
            (10.5, "prompt_threshold must be an integer between 10 and 500"),
            ("80", "prompt_threshold must be an integer between 10 and 500"),
        ],
    )
    def test_invalid_prompt_threshold(self, invalid_value, expected_error):
        """Test validation of prompt_threshold with invalid values."""
        with pytest.raises(ValueError) as excinfo:
            Config(prompt_threshold=invalid_value)
        assert f"Invalid configuration: {expected_error}" in str(excinfo.value)

    @pytest.mark.parametrize(
        "invalid_value,expected_error",
        [
            (None, "fallback_timeout must be a number between 1.0 and 60.0"),
            (0.5, "fallback_timeout must be a number between 1.0 and 60.0"),
            (70.0, "fallback_timeout must be a number between 1.0 and 60.0"),
            ("10.0", "fallback_timeout must be a number between 1.0 and 60.0"),
        ],
    )
    def test_invalid_fallback_timeout(self, invalid_value, expected_error):
        """Test validation of fallback_timeout with invalid values."""
        with pytest.raises(ValueError) as excinfo:
            Config(fallback_timeout=invalid_value)
        assert f"Invalid configuration: {expected_error}" in str(excinfo.value)

    @pytest.mark.parametrize(
        "invalid_value,expected_error",
        [
            (None, "min_comprehensive_length must be a non-negative integer"),
            (-1, "min_comprehensive_length must be a non-negative integer"),
            (10.5, "min_comprehensive_length must be a non-negative integer"),
            ("50", "min_comprehensive_length must be a non-negative integer"),
        ],
    )
    def test_invalid_min_comprehensive_length(self, invalid_value, expected_error):
        """Test validation of min_comprehensive_length with invalid values."""
        with pytest.raises(ValueError) as excinfo:
            Config(min_comprehensive_length=invalid_value)
        assert f"Invalid configuration: {expected_error}" in str(excinfo.value)

    @pytest.mark.parametrize(
        "invalid_value,expected_error",
        [
            (None, "attempt must be an integer between 1 and 10"),
            (0, "attempt must be an integer between 1 and 10"),
            (15, "attempt must be an integer between 1 and 10"),
            (3.5, "attempt must be an integer between 1 and 10"),
            ("3", "attempt must be an integer between 1 and 10"),
        ],
    )
    def test_invalid_attempt(self, invalid_value, expected_error):
        """Test validation of attempt with invalid values."""
        with pytest.raises(ValueError) as excinfo:
            Config(attempt=invalid_value)
        assert f"Invalid configuration: {expected_error}" in str(excinfo.value)

    @pytest.mark.parametrize(
        "invalid_value,expected_error",
        [
            (None, "diff_max_length must be a non-negative integer"),
            (-1, "diff_max_length must be a non-negative integer"),
            (100.5, "diff_max_length must be a non-negative integer"),
            ("100", "diff_max_length must be a non-negative integer"),
        ],
    )
    def test_invalid_diff_max_length(self, invalid_value, expected_error):
        """Test validation of diff_max_length with invalid values."""
        with pytest.raises(ValueError) as excinfo:
            Config(diff_max_length=invalid_value)
        assert f"Invalid configuration: {expected_error}" in str(excinfo.value)

    def test_boundary_values(self):
        """Test that boundary values are accepted."""
        # Test minimum values
        min_config = Config(
            prompt_threshold=Config.MIN_THRESHOLD,
            fallback_timeout=Config.MIN_TIMEOUT,
            attempt=Config.MIN_ATTEMPTS,
            min_comprehensive_length=0,
            diff_max_length=0,
        )
        assert min_config.is_valid()

        # Test maximum values
        max_config = Config(
            prompt_threshold=Config.MAX_THRESHOLD,
            fallback_timeout=Config.MAX_TIMEOUT,
            attempt=Config.MAX_ATTEMPTS,
        )
        assert max_config.is_valid()

    def test_multiple_validation_errors(self):
        """Test that only the first validation error is reported."""
        with pytest.raises(ValueError) as excinfo:
            Config(
                force_brackets="True",
                prompt_threshold=5,
                fallback_timeout=0.5,
                min_comprehensive_length=-1,
                attempt=0,
                diff_max_length=-1,
            )
        assert "Invalid configuration: force_brackets must be a boolean value" in str(
            excinfo.value
        )

    def test_is_valid_method(self):
        """Test the is_valid method."""
        # Valid configuration
        valid_config = Config()
        assert valid_config.is_valid() is True

        # Create an invalid configuration without triggering __post_init__
        with patch.object(Config, "__post_init__", return_value=None):
            invalid_config = Config()
            # Manually set an invalid value
            invalid_config.force_brackets = "True"
            assert invalid_config.is_valid() is False

    def test_validate_method(self):
        """Test the _validate method directly."""
        # Valid configuration
        valid_config = Config()
        assert valid_config._validate() is None

        # Create an invalid configuration without triggering __post_init__
        with patch.object(Config, "__post_init__", return_value=None):
            invalid_config = Config()
            # Manually set an invalid value
            invalid_config.force_brackets = "True"
            assert (
                    invalid_config._validate() == "force_brackets must be a boolean value"
            )

    def test_post_init_validation(self):
        """Test that validation happens in __post_init__."""
        # This should not raise an exception
        Config()

        # This should raise an exception
        with pytest.raises(ValueError):
            Config(force_brackets="True")

    def test_default_config_instance(self):
        """Test the default_config instance."""
        from c4f.config import default_config

        assert isinstance(default_config, Config)
        assert default_config.is_valid()
        assert default_config.force_brackets is False
        assert default_config.prompt_threshold == 80
        assert default_config.fallback_timeout == 10.0
        assert default_config.min_comprehensive_length == 50
        assert default_config.attempt == 3
        assert default_config.diff_max_length == 100
        assert default_config.model == g4f.models.gpt_4o_mini

    def test_model_validation(self):
        # TODO
        """Test validation of the model attribute."""
        # Test with a valid g4f.Model object
        # mock_model = MagicMock(spec=g4f.Model)
        # config = Config(model=mock_model)
        # assert config.is_valid()
        #
        # # Test with a valid g4f.models enum value
        # config = Config(model=g4f.models.gpt_4o)
        # assert config.is_valid()
        #
        # # Test with a valid string
        # config = Config(model="gpt-4o")
        # assert config.is_valid()
        #
        # # Test with an invalid model type
        # with patch.object(Config, '__post_init__', return_value=None):
        #     invalid_config = Config()
        #     invalid_config.model = 123  # Invalid type
        #     # Since model validation is not in the _validate method, this should still be valid
        #     assert invalid_config.is_valid() is True

    def test_config_repr(self):
        """Test the string representation of the Config class."""
        config = Config()
        repr_str = repr(config)
        assert "Config(" in repr_str
        assert "force_brackets=False" in repr_str
        assert "prompt_threshold=80" in repr_str
        assert "fallback_timeout=10.0" in repr_str
        assert "min_comprehensive_length=50" in repr_str
        assert "attempt=3" in repr_str
        assert "diff_max_length=100" in repr_str
        assert "model=" in repr_str

    def test_config_eq(self):
        """Test equality comparison of Config instances."""
        config1 = Config()
        config2 = Config()
        assert config1 == config2

        config3 = Config(force_brackets=True)
        assert config1 != config3

    def test_config_copy(self):
        """Test copying a Config instance."""
        import copy

        original = Config(force_brackets=True, prompt_threshold=100)
        copied = copy.copy(original)

        assert copied is not original
        assert copied.force_brackets == original.force_brackets
        assert copied.prompt_threshold == original.prompt_threshold
        assert copied.fallback_timeout == original.fallback_timeout
        assert copied.min_comprehensive_length == original.min_comprehensive_length
        assert copied.attempt == original.attempt
        assert copied.diff_max_length == original.diff_max_length
        assert copied.model == original.model
