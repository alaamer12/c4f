"""Tests for the SSL workaround functionality.

This module contains tests for the SSL workaround functionality in c4f.ssl_utils.
It includes tests for the with_ssl_workaround decorator and related functions.
"""

import os
import unittest
from unittest.mock import patch, MagicMock, call
import ssl
import tempfile
from pathlib import Path

from c4f.ssl_utils import with_ssl_workaround, create_ssl_config_file, is_ssl_renegotiation_error


class MockSSLError(ssl.SSLError):
    """Mock SSL error for testing."""
    def __init__(self, message="SSL error"):
        super().__init__(1, message)


class TestSSLWorkaround(unittest.TestCase):
    """Test cases for SSL workaround functionality."""

    def test_is_ssl_renegotiation_error(self):
        """Test the is_ssl_renegotiation_error function."""
        # Test with a renegotiation error
        error = MockSSLError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled")
        self.assertTrue(is_ssl_renegotiation_error(error))
        
        # Test with a different SSL error
        error = MockSSLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        self.assertFalse(is_ssl_renegotiation_error(error))
        
        # Test with a non-SSL error
        error = ValueError("Some other error")
        self.assertFalse(is_ssl_renegotiation_error(error))

    @patch('tempfile.mkstemp')
    @patch('os.fdopen')
    def test_create_ssl_config_file(self, mock_fdopen, mock_mkstemp):
        """Test the create_ssl_config_file function."""
        # Mock the file descriptor and path
        mock_fd = 123
        mock_path = "/tmp/openssl_12345.cnf"
        mock_mkstemp.return_value = (mock_fd, mock_path)
        
        # Mock the file object
        mock_file = MagicMock()
        mock_fdopen.return_value.__enter__.return_value = mock_file
        
        # Call the function
        result = create_ssl_config_file()
        
        # Verify the result
        self.assertEqual(result, mock_path)
        mock_mkstemp.assert_called_once_with(suffix='.cnf', prefix='openssl_')
        mock_fdopen.assert_called_once_with(mock_fd, 'w')
        mock_file.write.assert_called_once()
        self.assertIn("UnsafeLegacyRenegotiation", mock_file.write.call_args[0][0])

    @patch('tempfile.mkstemp')
    def test_create_ssl_config_file_error(self, mock_mkstemp):
        """Test the create_ssl_config_file function with an error."""
        # Mock an exception when creating the file
        mock_mkstemp.side_effect = OSError("Failed to create file")
        
        # Call the function
        result = create_ssl_config_file()
        
        # Verify the result
        self.assertEqual(result, "")

    @patch('c4f.ssl_utils.create_ssl_config_file')
    @patch('os.environ')
    @patch('os.remove')
    def test_with_ssl_workaround_success(self, mock_remove, mock_environ, mock_create_config):
        """Test the with_ssl_workaround decorator with successful execution."""
        # Mock the config file creation
        mock_config_path = "/tmp/openssl_12345.cnf"
        mock_create_config.return_value = mock_config_path
        
        # Mock environment variables
        mock_environ.get.return_value = None
        
        # Mock Path.exists to return True
        with patch('pathlib.Path.exists', return_value=True):
            # Create a test function with the decorator
            @with_ssl_workaround
            def test_func():
                return "success"
            
            # Call the function
            result = test_func()
            
            # Verify the result
            self.assertEqual(result, "success")
            mock_create_config.assert_called_once()
            mock_environ.__setitem__.assert_called_with('OPENSSL_CONF', mock_config_path)
            mock_environ.pop.assert_called_with('OPENSSL_CONF', None)
            mock_remove.assert_called_once_with(mock_config_path)

    @patch('c4f.ssl_utils.create_ssl_config_file')
    @patch('os.environ')
    def test_with_ssl_workaround_exception(self, mock_environ, mock_create_config):
        """Test the with_ssl_workaround decorator with an exception."""
        # Mock the config file creation
        mock_config_path = "/tmp/openssl_12345.cnf"
        mock_create_config.return_value = mock_config_path
        
        # Mock environment variables
        original_conf = "/etc/ssl/openssl.cnf"
        mock_environ.get.return_value = original_conf
        
        # Create a test function with the decorator that raises an exception
        @with_ssl_workaround
        def test_func():
            raise MockSSLError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled")
        
        # Call the function and expect an exception
        with self.assertRaises(MockSSLError), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            test_func()
            
            # Verify environment variables were restored
            mock_environ.__setitem__.assert_called_with('OPENSSL_CONF', original_conf)
            mock_remove.assert_called_once_with(mock_config_path)

    def test_real_api_call_simulation(self):
        """Simulate a real API call with SSL error and workaround."""
        # Create a mock API function that raises an SSL error on first call
        # but succeeds on second call (simulating the workaround working)
        mock_api = MagicMock()
        mock_api.side_effect = [
            MockSSLError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled"),
            "API response"
        ]
        
        # Apply our workaround to the mock API function
        @with_ssl_workaround
        def call_api():
            return mock_api()
        
        # Patch the necessary functions
        with patch('c4f.ssl_utils.create_ssl_config_file', return_value="/tmp/mock_config.cnf"), \
             patch('os.environ'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('os.remove'):
            
            # This should succeed because our decorator will catch the first exception
            # and retry with the workaround applied
            try:
                result = call_api()
                self.assertEqual(result, "API response")
            except MockSSLError:
                # If we get here, the workaround didn't work as expected
                self.fail("SSL workaround did not handle the error correctly")


class TestIntegrationWithHuggingFace(unittest.TestCase):
    """Integration tests with mocked Hugging Face API."""
    
    @patch('c4f.main.client.chat.completions.create')
    def test_huggingface_api_call(self, mock_create):
        """Test that the SSL workaround is applied to Hugging Face API calls."""
        from c4f.main import get_model_response
        from c4f.config import Config
        import g4f
        
        # Configure the mock to simulate an SSL error on first call
        mock_create.side_effect = [
            MockSSLError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled"),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Generated commit message"))])
        ]
        
        # Create a minimal config
        config = Config(model=g4f.models.gpt_4o_mini, thread_count=1)
        
        # Call the function that should have our SSL workaround
        with patch('c4f.ssl_utils.create_ssl_config_file', return_value="/tmp/mock_config.cnf"), \
             patch('os.environ'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('os.remove'):
            
            # This should handle the SSL error and return the successful response
            result = get_model_response("Generate a commit message", {}, config)
            
            # Verify the result
            self.assertEqual(result, "Generated commit message")
            
            # Verify the API was called twice (once with error, once with success)
            self.assertEqual(mock_create.call_count, 2)


if __name__ == '__main__':
    unittest.main()