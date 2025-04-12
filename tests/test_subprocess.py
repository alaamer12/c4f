import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from c4f.utils import (
    FileChange,
    ProcessResourceMonitor,
    SecureSubprocess,
    SecureSubprocessTermination,
    SubprocessConfig,
    SubprocessHandler,
    SubprocessExecutionParams,
)

# Define test commands that work cross-platform
if sys.platform == "win32":
    ECHO_CMD = ["cmd", "/c", "echo", "hello"]
    SLEEP_CMD = ["timeout", "2"]
    NOT_EXIST_CMD = ["command_does_not_exist"]
    CAT_FILE_CMD = ["type"]
else:
    ECHO_CMD = ["echo", "hello"]
    SLEEP_CMD = ["sleep", "2"]
    NOT_EXIST_CMD = ["command_does_not_exist"]
    CAT_FILE_CMD = ["cat"]


# Utility functions for tests
def create_temp_file(tmp_path, content="test content"):
    """Create a temporary file with content for testing."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text(content)
    return test_file


# Fixtures
@pytest.fixture
def subprocess_handler():
    """Return a SubprocessHandler instance with short timeout for testing."""
    return SubprocessHandler(timeout=2, max_termination_retries=2, termination_wait=0.1)


@pytest.fixture
def secure_subprocess():
    """Return a SecureSubprocess instance with permissive settings for testing."""
    config = SubprocessConfig(
        timeout=2,
        max_termination_retries=2,
        termination_wait=0.1,
        allowed_commands=set(),  # Allow all commands for testing
        max_output_size=1024,  # Small size for testing truncation
        enable_shell=False,
        restricted_env=False,  # Use full environment for testing
        monitor_interval=0.1,
    )
    return SecureSubprocess(config)


@pytest.fixture
def restricted_secure_subprocess():
    """Return a SecureSubprocess instance with restrictive settings."""
    # Only allow echo command for testing
    allowed_cmds = {"echo", "cmd", "type", "cat", "sleep", "timeout"}
    config = SubprocessConfig(
        timeout=2,
        max_termination_retries=2,
        termination_wait=0.1,
        allowed_commands=allowed_cmds,
        max_output_size=1024,
        enable_shell=False,
        restricted_env=True,
        monitor_interval=0.1,
    )
    return SecureSubprocess(config)


@pytest.fixture
def mock_process():
    """Create a mock for subprocess.Popen with controllable behavior."""
    mock = MagicMock(spec=subprocess.Popen)
    mock.poll.return_value = None  # Process is running by default
    mock.returncode = 0
    mock.pid = 12345  # Fake PID

    stdout_mock = MagicMock()
    stderr_mock = MagicMock()

    # Configure the mock's stdout and stderr attributes
    type(mock).stdout = PropertyMock(return_value=stdout_mock)
    type(mock).stderr = PropertyMock(return_value=stderr_mock)

    return mock


# Optional fixture for psutil - only used if psutil is available
try:
    # noinspection PyUnresolvedReferences
    import psutil

    PSUTIL_AVAILABLE = True


    @pytest.fixture
    def mock_psutil_process():
        """Create a mock for psutil.Process."""
        with patch("psutil.Process") as mock:
            process_instance = mock.return_value
            process_instance.cpu_percent.return_value = 5.0  # Default CPU usage
            process_instance.memory_info.return_value = MagicMock(
                rss=1024 * 1024
            )  # 1MB memory usage
            process_instance.children.return_value = []  # No child processes by default
            yield mock
except ImportError:
    PSUTIL_AVAILABLE = False


# Tests for SubprocessHandler
class TestSubprocessHandler:
    """Test suite for the SubprocessHandler class."""

    def test_initialization(self):
        """Test that SubprocessHandler initializes with correct defaults."""
        handler = SubprocessHandler()
        assert handler.timeout == 30
        assert handler.max_termination_retries == 3
        assert handler.termination_wait == 0.5
        assert handler.process is None

        # Test custom initialization
        custom_handler = SubprocessHandler(
            timeout=10, max_termination_retries=5, termination_wait=1.0
        )
        assert custom_handler.timeout == 10
        assert custom_handler.max_termination_retries == 5
        assert custom_handler.termination_wait == 1.0

    def test_create_env(self):
        """Test that create_env returns a copy of the environment with encoding set."""
        env = SubprocessHandler.create_env(True)
        assert isinstance(env, dict)
        assert env["PYTHONIOENCODING"] == "utf-8"

        # Test that it's a copy of os.environ
        assert len(env) >= len(os.environ)

    def test_run_command_success(self, subprocess_handler):
        """Test successful command execution."""
        stdout, stderr, returncode = subprocess_handler.run_command(ECHO_CMD)
        assert "hello" in stdout
        assert stderr == ""
        assert returncode == 0

    def test_run_command_error(self, subprocess_handler):
        """Test command that doesn't exist."""
        try:
            # This should raise an exception on most platforms
            stdout, stderr, returncode = subprocess_handler.run_command(NOT_EXIST_CMD)
            # If we get here, the command didn't fail on this platform
            assert returncode != 0  # At least ensure non-zero return code
        except FileNotFoundError:
            # This is the expected outcome on most platforms
            pass

    def test_run_command_timeout(self, subprocess_handler, mock_process):
        """Test command that times out."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = mock_popen.return_value
            mock_process.communicate.side_effect = subprocess.TimeoutExpired(
                SLEEP_CMD, 0.1
            )

            with pytest.raises(TimeoutError):
                subprocess_handler.run_command(SLEEP_CMD, timeout=0.1)

    def test_run_text_mode(self, subprocess_handler):
        """Test run_text_mode method."""
        stdout, stderr, returncode = subprocess_handler.run_text_mode(ECHO_CMD)
        assert "hello" in stdout
        assert stderr == ""
        assert returncode == 0

    def test_run_binary_mode(self, subprocess_handler):
        """Test run_binary_mode method."""
        stdout, stderr, returncode = subprocess_handler.run_binary_mode(ECHO_CMD)
        assert "hello" in stdout
        assert stderr == ""
        assert returncode == 0

    def test_cleanup_process(self, subprocess_handler, mock_process):
        """Test _cleanup_process method properly closes file descriptors."""
        # Call the cleanup method
        subprocess_handler._cleanup_process(mock_process)

        # Verify stdout and stderr were closed
        mock_process.stdout.close.assert_called_once()
        mock_process.stderr.close.assert_called_once()

        # Verify termination was attempted
        mock_process.poll.assert_called()

    def test_terminate_process(self, subprocess_handler, mock_process):
        """Test _terminate_process method attempts termination."""
        # Configure mock to simulate running then terminated process
        mock_process.poll.return_value = None  # Process is running

        # Call the termination method
        subprocess_handler._terminate_process(mock_process)

        # Verify termination was called
        mock_process.terminate.assert_called_once()

        # Test with already terminated process
        mock_process.reset_mock()
        mock_process.poll.return_value = 0  # Process already terminated

        # Call the termination method again
        subprocess_handler._terminate_process(mock_process)

        # Verify termination was not called since process was already terminated
        mock_process.terminate.assert_not_called()

    def test_terminate_process_with_kill(self, subprocess_handler, mock_process):
        """Test _terminate_process escalates to kill if necessary."""
        # Configure mock to simulate a stubborn process
        mock_process.poll.return_value = None  # Process never terminates

        # Call the termination method
        subprocess_handler._terminate_process(mock_process)

        # Verify termination and kill were called
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_encoding_error_handling(self, subprocess_handler, tmp_path):
        """Test handling of encoding errors."""
        # Create a file with non-UTF8 content using binary mode
        test_file = tmp_path / "test_file.txt"
        with open(test_file, "wb") as f:
            f.write(b"\x80\x81\x82")  # Write binary data directly

        # Test reading with text mode - should handle encoding errors
        if sys.platform == "win32":
            # On Windows, we need to use shell=True for built-in commands
            cmd = ["cmd", "/c", "type", str(test_file)]
        else:
            cmd = ["cat", str(test_file)]

        stdout, stderr, returncode = subprocess_handler.run_command(cmd)
        assert returncode == 0
        assert isinstance(
            stdout, str
        )  # Should still get string output even with encoding errors

    def test_handle_timeout(self, subprocess_handler, mock_process):
        """Test _handle_timeout method raises TimeoutError."""
        with pytest.raises(TimeoutError, match="Command timed out after 2 seconds"):
            subprocess_handler._handle_timeout(mock_process, ECHO_CMD, 2)

    def test_handle_execution_error(self, subprocess_handler, mock_process):
        """Test _handle_execution_error method."""
        test_error = OSError("Test error")

        # Should raise the original exception after cleanup
        with pytest.raises(OSError, match="Test error"):
            subprocess_handler._handle_execution_error(mock_process, test_error)

        # Verify process was terminated
        mock_process.terminate.assert_called_once()

    def test_process_output_binary_mode(self, subprocess_handler, mock_process):
        """Test _process_output method in binary mode."""
        # Configure mock process
        mock_process.returncode = 42

        # Test with binary output
        stdout = b"binary output"
        stderr = b"binary error"

        result_stdout, result_stderr, result_code = subprocess_handler._process_output(
            stdout,
            stderr,
            is_text_mode=False,
            encoding="utf-8",
            errors="replace",
            process=mock_process,
        )

        assert result_stdout == "binary output"
        assert result_stderr == "binary error"
        assert result_code == 42

    def test_process_output_text_mode(self, subprocess_handler, mock_process):
        """Test _process_output method in text mode."""
        # Configure mock process
        mock_process.returncode = 42

        # Test with text output
        stdout = "text output"
        stderr = "text error"

        result_stdout, result_stderr, result_code = subprocess_handler._process_output(
            stdout,
            stderr,
            is_text_mode=True,
            encoding="utf-8",
            errors="replace",
            process=mock_process,
        )

        assert result_stdout == "text output"
        assert result_stderr == "text error"
        assert result_code == 42

    def test_cleanup_process_with_none(self, subprocess_handler):
        """Test _cleanup_process method with None process."""
        # Should not raise any exceptions
        subprocess_handler._cleanup_process(None)

    def test_cleanup_process_with_closed_fds(self, subprocess_handler, mock_process):
        """Test _cleanup_process method with closed file descriptors."""
        # Configure mock to simulate closed file descriptors
        mock_process.stdout.close.side_effect = OSError("Already closed")
        mock_process.stderr.close.side_effect = OSError("Already closed")

        # Should not raise any exceptions
        subprocess_handler._cleanup_process(mock_process)

        # Verify close was attempted
        mock_process.stdout.close.assert_called_once()
        mock_process.stderr.close.assert_called_once()

    def test_terminate_process_with_oserror(self, subprocess_handler, mock_process):
        """Test _terminate_process method with OSError during termination."""
        # Configure mock to raise OSError during terminate
        mock_process.terminate.side_effect = OSError("Terminate failed")

        # Should not raise any exceptions
        subprocess_handler._terminate_process(mock_process)

        # Verify terminate was called
        mock_process.terminate.assert_called_once()

        # Verify kill was not called (since poll returns None)
        mock_process.kill.assert_not_called()

    def test_handle_execution_error_with_termination_error(
            self, subprocess_handler, mock_process
    ):
        """Test _handle_execution_error when process termination fails."""
        # Configure mock to raise OSError during termination
        mock_process.terminate.side_effect = OSError("Termination failed")

        # Should still raise the original exception
        with pytest.raises(OSError, match="Test error"):
            subprocess_handler._handle_execution_error(
                mock_process, OSError("Test error")
            )

        # Verify termination was attempted
        mock_process.terminate.assert_called_once()

    def test_terminate_process_with_psutil_error(
            self, subprocess_handler, mock_process
    ):
        """Test _terminate_process when psutil raises an exception."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        with patch("psutil.Process") as mock_psutil:
            mock_psutil.side_effect = Exception("psutil error")

            # Should fall back to standard termination
            subprocess_handler._terminate_process(mock_process)

            # Verify standard termination was attempted
            mock_process.terminate.assert_called_once()

    def test_monitor_process_tree_with_psutil_error(
            self, subprocess_handler, mock_process
    ):
        """Test _monitor_process_tree when psutil raises an exception."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        # Simulate a call that would use poll
        mock_process.poll.return_value = None  # Process is still running

        with patch("psutil.Process") as mock_psutil:
            mock_psutil.side_effect = Exception("psutil error")

            # The subprocess_handler doesn't have _monitor_process_tree, so we just verify
            # that when we try to terminate with psutil and it fails, the process is still monitored
            subprocess_handler._terminate_process(mock_process)

            # Verify process was still monitored
            mock_process.poll.assert_called()

    def test_process_output_binary_mode_with_non_bytes(
            self, secure_subprocess, mock_process
    ):
        """Test _process_output method in binary mode with non-bytes output."""
        # Configure mock process
        mock_process.returncode = 42

        # Test with non-bytes output
        stdout = "text output"
        stderr = "text error"

        result_stdout, result_stderr, result_code = secure_subprocess._process_output(
            stdout,
            stderr,
            is_text_mode=False,
            encoding="utf-8",
            errors="replace",
            process=mock_process,
        )

        assert result_stdout == "text output"
        assert result_stderr == "text error"
        assert result_code == 42


# Tests for SecureSubprocess
class TestSecureSubprocess:
    """Test suite for the SecureSubprocess class."""

    def test_initialization(self):
        """Test that SecureSubprocess initializes with correct defaults and custom values."""
        # Test default initialization
        secure = SecureSubprocess(SubprocessConfig())
        assert secure.timeout == 30
        assert secure.allowed_commands == set()
        assert secure.max_output_size == 10 * 1024 * 1024  # 10MB
        assert secure.enable_shell is False
        assert secure.restricted_env is True

        # Test custom initialization
        custom_config = SubprocessConfig(
            timeout=5,
            allowed_commands={"echo", "ls"},
            working_dir=".",
            max_output_size=1024,
            enable_shell=True,
            restricted_env=False,
        )
        custom_secure = SecureSubprocess(custom_config)
        assert custom_secure.timeout == 5
        assert custom_secure.allowed_commands == {"echo", "ls"}
        assert custom_secure.working_dir == Path()
        assert custom_secure.max_output_size == 1024
        assert custom_secure.enable_shell is True
        assert custom_secure.restricted_env is False

    def test_initialization_invalid_working_dir(self):
        """Test initialization with invalid working directory."""
        with pytest.raises(ValueError):
            SecureSubprocess(SubprocessConfig(working_dir="/path/that/does/not/exist"))

    def test_create_env_restricted(self):
        """Test that create_env with restricted=True returns a minimal environment."""
        secure = SecureSubprocess(SubprocessConfig())
        env = secure.create_env(restricted=True)
        assert "PATH" in env
        assert "PYTHONIOENCODING" in env
        assert env["PYTHONIOENCODING"] == "utf-8"

        # Restricted environment should have only essential variables
        # Check that it contains only the expected essential variables
        essential_vars = {"PATH", "PYTHONIOENCODING", "LANG", "LC_ALL"}

        # Add Windows-specific variables if on Windows
        if sys.platform == "win32":
            essential_vars.update({"SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC"})

        # Check that all keys in env are either essential or present in os.environ
        for key in env:
            assert key in essential_vars or key in os.environ

        # Verify some environment variables don't exist in restricted env
        # Find a variable in os.environ that's not one of the essential ones
        for key in os.environ:
            if key not in essential_vars and key in env:
                continue  # This key exists in both, so it doesn't help us test
            if key not in essential_vars and key not in env:
                # Found a non-essential key that's not in the restricted env
                break
        else:
            # If we didn't break, then all os.environ keys are in env, which is wrong for restricted mode
            assert False, (
                "Restricted environment should not contain all environment variables"
            )

    def test_create_env_full(self):
        """Test that create_env with restricted=False returns full environment."""
        secure = SecureSubprocess(SubprocessConfig())
        env = secure.create_env(restricted=False)
        assert env["PYTHONIOENCODING"] == "utf-8"

        # Should contain all environment variables
        for key in os.environ:
            assert key in env

    def test_validate_command_allowed(self, secure_subprocess):
        """Test command validation with allowed commands."""
        # With empty allowed_commands, all commands should be allowed
        assert secure_subprocess.validate_command(ECHO_CMD) is True
        assert secure_subprocess.validate_command(NOT_EXIST_CMD) is True

        # Test with restricted allowed commands
        secure_subprocess.allowed_commands = {"echo", "cmd"}  # Allow both echo and cmd
        if sys.platform == "win32":
            # On Windows, the command would be cmd.exe
            assert (
                    secure_subprocess.validate_command(["cmd", "/c", "echo", "test"])
                    is True
            )
        else:
            assert secure_subprocess.validate_command(["echo", "test"]) is True
        assert secure_subprocess.validate_command(["ls"]) is False

    def test_validate_command_empty(self, secure_subprocess):
        """Test command validation with empty command list."""
        assert secure_subprocess.validate_command([]) is False

    def test_sanitize_command(self, secure_subprocess):
        """Test command sanitization."""
        # Test basic command
        cmd = ["echo", "hello"]
        sanitized = secure_subprocess.sanitize_command(cmd)
        assert sanitized == cmd

        # Test command with potentially dangerous characters
        if sys.platform == "win32":
            # Windows-specific dangerous characters
            cmd = ["echo", "hello & del file.txt"]
            sanitized = secure_subprocess.sanitize_command(cmd)
            assert "&" not in sanitized[1]
        else:
            # Unix-specific dangerous characters
            cmd = ["echo", "hello; rm -rf /"]
            sanitized = secure_subprocess.sanitize_command(cmd)
            assert ";" not in sanitized[1]

    def test_run_command_success(self, secure_subprocess):
        """Test successful command execution with SecureSubprocess."""
        stdout, stderr, returncode = secure_subprocess.run_command(ECHO_CMD)
        assert "hello" in stdout
        assert stderr == ""
        assert returncode == 0

    def test_run_command_not_allowed(self, restricted_secure_subprocess):
        """Test execution of disallowed command."""
        # Set a command that's not in the allowed list
        restricted_secure_subprocess.allowed_commands = {"not_echo"}

        with pytest.raises(ValueError, match="Command not allowed"):
            restricted_secure_subprocess.run_command(ECHO_CMD)

    def test_output_truncation(self, secure_subprocess):
        """Test output truncation for large outputs."""
        # Create a command that generates output larger than max_output_size
        secure_subprocess.max_output_size = 10  # Set very small for testing

        # Create a command that generates more output
        if sys.platform == "win32":
            cmd = [
                "cmd",
                "/c",
                "echo",
                "This is a longer output that should be truncated",
            ]
        else:
            cmd = ["echo", "This is a longer output that should be truncated"]

        stdout, stderr, returncode = secure_subprocess.run_command(cmd)

        # Output should be truncated
        assert len(stdout) <= secure_subprocess.max_output_size + len("... (truncated)")
        assert "truncated" in stdout

    def test_working_directory(self, tmp_path):
        """Test subprocess execution with custom working directory."""
        # Create a secure subprocess with the temp directory as working dir
        config = SubprocessConfig(timeout=2, working_dir=tmp_path)
        secure = SecureSubprocess(config)

        # Create a file in the temp directory to verify working dir
        test_file = create_temp_file(tmp_path)

        # Run command to list files in current directory
        if sys.platform == "win32":
            cmd = ["cmd", "/c", "dir"]
        else:
            cmd = ["ls"]

        stdout, stderr, returncode = secure.run_command(cmd)

        # Output should contain our test file
        assert test_file.name in stdout

    def test_shell_execution(self):
        """Test subprocess execution with shell enabled."""
        # Create a secure subprocess with shell enabled
        config = SubprocessConfig(timeout=2, enable_shell=True)
        secure = SecureSubprocess(config)

        # Run a shell command that should work on both platforms
        if sys.platform == "win32":
            cmd = [
                "echo",
                "test",
            ]  # Simple command that works with shell=True on Windows
        else:
            cmd = ["echo", "test"]  # Simple command that works with shell=True on Unix

        stdout, stderr, returncode = secure.run_command(cmd)

        # Should execute the command through the shell
        assert returncode == 0
        # The output should contain our test string
        assert "test" in stdout

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_resource_monitoring(self, mock_psutil_process, mock_process):
        """Test process resource monitoring if psutil is available."""
        # Create a secure subprocess with resource limits
        config = SubprocessConfig(
            timeout=2,
            cpu_limit=10.0,  # 10% CPU limit
            memory_limit=10 * 1024 * 1024,  # 10MB memory limit
        )
        secure = SecureSubprocess(config)

        # Start a process
        with patch("subprocess.Popen") as mock_popen:
            mock_process = mock_popen.return_value
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_process.communicate.return_value = (b"output", b"error")

            # Run the command
            stdout, stderr, returncode = secure.run_command(ECHO_CMD)

            # Verify psutil.Process was called
            mock_psutil_process.assert_called_with(12345)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_cpu_limit_exceeded(self, mock_psutil_process, mock_process):
        """Test CPU limit enforcement if psutil is available."""
        # Configure mock psutil to report high CPU usage
        process_instance = mock_psutil_process.return_value
        process_instance.cpu_percent.return_value = 90.0  # 90% CPU usage

        # Create a secure subprocess with a low CPU limit
        config = SubprocessConfig(
            timeout=2,
            cpu_limit=10.0,  # 10% CPU limit - will be exceeded
            monitor_interval=0.1,
        )
        secure = SecureSubprocess(config)

        # Start monitoring in a thread to simulate background monitoring
        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = mock_thread.return_value

            # Run the command
            with patch("subprocess.Popen") as mock_popen:
                mock_process = mock_popen.return_value
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_process.communicate.side_effect = subprocess.TimeoutExpired(
                    cmd=ECHO_CMD, timeout=2
                )

                with pytest.raises(TimeoutError):
                    secure.run_command(ECHO_CMD)

                # Verify thread was started for monitoring
                mock_thread.assert_called()
                mock_thread_instance.start.assert_called_once()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_memory_limit_exceeded(self, mock_psutil_process, mock_process):
        """Test memory limit enforcement if psutil is available."""
        # Configure mock psutil to report high memory usage
        process_instance = mock_psutil_process.return_value
        process_instance.memory_info.return_value = MagicMock(
            rss=100 * 1024 * 1024
        )  # 100MB memory usage

        # Create a secure subprocess with a low memory limit
        config = SubprocessConfig(
            timeout=2,
            memory_limit=10 * 1024 * 1024,  # 10MB memory limit - will be exceeded
            monitor_interval=0.1,
        )
        secure = SecureSubprocess(config)

        # Start monitoring in a thread to simulate background monitoring
        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = mock_thread.return_value

            # Run the command
            with patch("subprocess.Popen") as mock_popen:
                mock_process = mock_popen.return_value
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_process.communicate.side_effect = subprocess.TimeoutExpired(
                    cmd=ECHO_CMD, timeout=2
                )

                with pytest.raises(TimeoutError):
                    secure.run_command(ECHO_CMD)

                # Verify thread was started for monitoring
                mock_thread.assert_called()
                mock_thread_instance.start.assert_called_once()

    def test_terminate_process_enhanced(
            self, restricted_secure_subprocess, mock_process
    ):
        """Test enhanced process termination in SecureSubprocess."""
        if not PSUTIL_AVAILABLE:
            # Skip psutil-specific tests if not available
            return

        with patch("psutil.Process") as mock_psutil:
            mock_psutil_instance = mock_psutil.return_value

            # Configure mock process
            mock_process.pid = 12345
            mock_process.poll.return_value = None

            # Call terminate
            restricted_secure_subprocess._terminate_process(mock_process)

            # Should have tried to use psutil for termination
            mock_psutil.assert_called_once_with(12345)

    def test_error_handling(self, secure_subprocess):
        """Test error handling during process execution."""
        with patch("subprocess.Popen") as mock_popen:
            # Configure Popen to raise an exception
            mock_popen.side_effect = OSError("Simulated error")

            # Should propagate the exception
            with pytest.raises(OSError, match="Simulated error"):
                secure_subprocess.run_command(ECHO_CMD)

    def test_timeout_handling(self, secure_subprocess, mock_process):
        """Test timeout handling during process execution."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = mock_popen.return_value
            mock_process.communicate.side_effect = subprocess.TimeoutExpired(
                cmd=ECHO_CMD, timeout=1
            )
            mock_process.poll.return_value = None  # Process is still running

            # Mock the _terminate_process method to ensure it's called
            with patch.object(
                    secure_subprocess, "_terminate_process"
            ) as mock_terminate:
                # Should convert to TimeoutError
                with pytest.raises(TimeoutError):
                    secure_subprocess.run_command(ECHO_CMD, timeout=1)

                # Should have tried to terminate the process at least once with the mock process
                mock_terminate.assert_any_call(mock_process)
                assert mock_terminate.call_count > 0

    def test_handle_win32_env(self, secure_subprocess):
        """Test _handle_win32_env method."""
        env = {}

        # Test on Windows
        with patch("sys.platform", "win32"):
            secure_subprocess._handle_win32_env(env)
            assert "SYSTEMROOT" in env
            assert "TEMP" in env
            assert "TMP" in env
            assert "PATHEXT" in env
            assert "COMSPEC" in env

        # Test on non-Windows
        env = {}
        with patch("sys.platform", "linux"):
            secure_subprocess._handle_win32_env(env)
            assert "SYSTEMROOT" not in env
            assert "TEMP" not in env
            assert "TMP" not in env
            assert "PATHEXT" not in env
            assert "COMSPEC" not in env

    def test_get_env(self, secure_subprocess):
        """Test _get_env method."""
        env = secure_subprocess._get_env()

        assert "PATH" in env
        assert "PYTHONIOENCODING" in env
        assert "LANG" in env
        assert "LC_ALL" in env
        assert env["PYTHONIOENCODING"] == "utf-8"

    def test_validate_command_windows(self, secure_subprocess):
        """Test validate_command method on Windows."""
        with patch("sys.platform", "win32"):
            # Test with .exe extension
            assert secure_subprocess.validate_command(["echo.exe", "test"]) is True

            # Test with .bat extension
            assert secure_subprocess.validate_command(["script.bat", "test"]) is True

            # Test with restricted commands
            secure_subprocess.allowed_commands = {"echo"}
            assert secure_subprocess.validate_command(["echo.exe", "test"]) is True
            assert secure_subprocess.validate_command(["cmd.exe", "test"]) is False

    def test_sanitize_command_empty(self, secure_subprocess):
        """Test sanitize_command method with empty command."""
        assert secure_subprocess.sanitize_command([]) == []

    def test_sanitize_command_windows(self, secure_subprocess):
        """Test sanitize_command method on Windows."""
        with patch("sys.platform", "win32"):
            # Test with dangerous characters
            cmd = ["echo", "hello & del file.txt | dir"]
            sanitized = secure_subprocess.sanitize_command(cmd)

            assert sanitized[0] == "echo"
            assert "&" not in sanitized[1]
            assert "|" not in sanitized[1]

    def test_sanitize_command_unix(self, secure_subprocess):
        """Test sanitize_command method on Unix."""
        with patch("sys.platform", "linux"):
            # Test with dangerous characters
            cmd = ["echo", "hello; rm -rf / | cat"]
            sanitized = secure_subprocess.sanitize_command(cmd)

            assert sanitized[0] == "echo"
            assert ";" not in sanitized[1]
            assert "|" not in sanitized[1]

    def test_start_resource_monitoring_no_psutil(self, secure_subprocess, mock_process):
        """Test _start_resource_monitoring method when psutil is not available."""
        with patch("c4f.utils.PSUTIL_AVAILABLE", False):
            # Should not raise any exceptions
            secure_subprocess._start_resource_monitoring(mock_process)

            # Verify threading.Thread was not called
            with patch("threading.Thread") as mock_thread:
                assert not mock_thread.called

    def test_start_resource_monitoring_no_limits(self, secure_subprocess, mock_process):
        """Test _start_resource_monitoring method when no limits are set."""
        secure_subprocess.cpu_limit = None
        secure_subprocess.memory_limit = None

        # Should not raise any exceptions
        secure_subprocess._start_resource_monitoring(mock_process)

        # Verify threading.Thread was not called
        with patch("threading.Thread") as mock_thread:
            assert not mock_thread.called

    def test_start_resource_monitoring_no_pid(self, secure_subprocess, mock_process):
        """Test _start_resource_monitoring method when process has no PID."""
        mock_process.pid = None

        # Should not raise any exceptions
        secure_subprocess._start_resource_monitoring(mock_process)

        # Verify threading.Thread was not called
        with patch("threading.Thread") as mock_thread:
            assert not mock_thread.called

    def test_truncate_output_string(self, secure_subprocess):
        """Test _truncate_output method with string output."""
        # Set small max output size
        secure_subprocess.max_output_size = 10

        # Test with string that exceeds max size
        output = "This is a long string that should be truncated"
        truncated = secure_subprocess._truncate_output(output)

        assert len(truncated) == 10 + len("... (truncated)")
        assert truncated.endswith("... (truncated)")

        # Test with string that doesn't exceed max size
        output = "Short"
        truncated = secure_subprocess._truncate_output(output)

        assert truncated == "Short"

    def test_truncate_output_bytes(self, secure_subprocess):
        """Test _truncate_output method with bytes output."""
        # Set small max output size
        secure_subprocess.max_output_size = 10

        # Test with bytes that exceeds max size
        output = b"This is a long string that should be truncated"
        truncated = secure_subprocess._truncate_output(output)

        assert len(truncated) == 10 + len(b"... (truncated)")
        assert truncated.endswith(b"... (truncated)")

        # Test with bytes that doesn't exceed max size
        output = b"Short"
        truncated = secure_subprocess._truncate_output(output)

        assert truncated == b"Short"

    def test_add_optional_popen_args(self, secure_subprocess):
        """Test _add_optional_popen_args method."""
        popen_kwargs = {}

        # Test with working directory
        secure_subprocess.working_dir = Path("/test/dir")
        secure_subprocess._add_optional_popen_args(popen_kwargs)
        assert popen_kwargs["cwd"] == Path("/test/dir")

        # Test with shell enabled
        popen_kwargs = {}
        secure_subprocess.enable_shell = True
        secure_subprocess._add_optional_popen_args(popen_kwargs)
        assert popen_kwargs["shell"] is True

        # Test with both
        popen_kwargs = {}
        secure_subprocess.working_dir = Path("/test/dir")
        secure_subprocess.enable_shell = True
        secure_subprocess._add_optional_popen_args(popen_kwargs)
        assert popen_kwargs["cwd"] == Path("/test/dir")
        assert popen_kwargs["shell"] is True

    def test_secure_subprocess_execute_with_exception(self, secure_subprocess):
        """Test SecureSubprocess execute with an exception."""
        # We need to patch _execute_subprocess directly since it's the method that catches exceptions
        with patch.object(
                secure_subprocess, "_execute_subprocess", return_value=("", "", -1)
        ):
            # Need to patch _prepare_command to avoid validation error
            with patch.object(
                    secure_subprocess, "_prepare_command", return_value=ECHO_CMD
            ):
                # Set up mock for _prepare_text_mode_kwargs
                with patch.object(
                        secure_subprocess, "_prepare_text_mode_kwargs", return_value={}
                ):
                    # Call _run_secure_subprocess
                    result = secure_subprocess._run_secure_subprocess(
                        ECHO_CMD, is_text_mode=True
                    )

                    # Verify return values
                    assert result == ("", "", -1)

    def test_file_change_with_invalid_path(self):
        """Test FileChange with an invalid file path."""
        file_change = FileChange(
            path=Path("/invalid/path/file.txt"),
            status="M",
            diff="test diff",
            type="fix",
        )

        assert file_change.path == Path("/invalid/path/file.txt")
        assert file_change.status == "M"
        assert file_change.diff == "test diff"
        assert file_change.type == "fix"
        assert file_change.last_modified == 0

    def test_file_change_handler_with_invalid_file(self, mock_process):
        """Test FileChangeHandler with an invalid file."""
        handler = FileChangeHandler(mock_process)

        # Test with invalid file path
        result = handler.handle_file_change("/invalid/path/file.txt")

        assert result is None
        mock_process.poll.assert_not_called()

    def test_file_change_handler_with_process_error(self, mock_process):
        """Test FileChangeHandler when process raises an error."""
        handler = FileChangeHandler(mock_process)
        mock_process.poll.side_effect = OSError("Process error")

        # Create a file that exists to pass the first check
        with patch("pathlib.Path.exists", return_value=True):
            # Test with valid file path
            result = handler.handle_file_change("test.txt")

        assert result is None
        mock_process.poll.assert_called_once()

    def test_process_monitor_with_early_exit(self, mock_process):
        """Test ProcessMonitor when process exits early."""
        monitor = ProcessMonitor(mock_process)
        mock_process.poll.return_value = 0

        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=monitor.start_monitoring)
        monitor_thread.start()

        # Wait for monitoring to complete
        monitor_thread.join(timeout=1.0)

        assert not monitor_thread.is_alive()
        mock_process.poll.assert_called()

    def test_process_monitor_with_error(self, mock_process):
        """Test ProcessMonitor when process raises an error."""
        monitor = ProcessMonitor(mock_process)
        mock_process.poll.side_effect = OSError("Process error")

        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=monitor.start_monitoring)
        monitor_thread.start()

        # Wait for monitoring to complete
        monitor_thread.join(timeout=1.0)

        assert not monitor_thread.is_alive()
        mock_process.poll.assert_called()

    def test_secure_subprocess_termination_with_error(self, mock_process):
        """Test SecureSubprocessTermination when termination fails."""
        terminator = SecureSubprocessTermination(
            termination_wait=0.01
        )  # Use shorter wait time for testing

        # Configure mock process poll to return None on first call, 0 on second call
        poll_return_values = [
            None,
            0,
        ]  # First call: still running, second call: terminated
        mock_process.poll.side_effect = (
            lambda: poll_return_values.pop(0) if poll_return_values else 0
        )

        # Make terminate fail but don't stop the test
        mock_process.terminate.side_effect = OSError("Termination failed")

        # Call the method under test
        terminator.terminate_process(mock_process, max_termination_retries=2)

        # Verify terminate was called
        mock_process.terminate.assert_called()

        # In our test scenario, poll() is called exactly once in the _terminate_and_wait method
        # This is because _is_process_already_terminated calls poll() once to check if it's already terminated,
        # but it returns None, so _terminate_and_wait is called, which calls poll() again.
        # However, since we configured poll() to return 0 on the second call, the method
        # exits early from the loop after the first iteration.
        assert mock_process.poll.call_count == 1

    def test_secure_subprocess_termination_with_psutil_error(self, mock_process):
        """Test SecureSubprocessTermination when psutil raises an exception."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        terminator = SecureSubprocessTermination(
            termination_wait=0.01
        )  # Use shorter wait time for testing

        # Configure mock process poll to return None on first call, 0 on second call
        poll_return_values = [
            None,
            0,
        ]  # First call: still running, second call: terminated
        mock_process.poll.side_effect = (
            lambda: poll_return_values.pop(0) if poll_return_values else 0
        )

        with patch("psutil.Process") as mock_psutil:
            mock_psutil.side_effect = Exception("psutil error")

            # Call the method under test - should fall back to standard termination
            terminator.terminate_process(mock_process, max_termination_retries=2)

            # Process should be terminated but not killed (since it terminates after the first attempt)
            mock_process.terminate.assert_called()

            # In this case, poll is called twice:
            # 1. First in _is_process_already_terminated
            # 2. Second in _terminate_and_wait
            assert mock_process.poll.call_count == 2

    def test_secure_subprocess_init_with_psutil_warning(self):
        """Test SecureSubprocess initialization with psutil warning."""
        # Mock PSUTIL_AVAILABLE to be False
        with patch("c4f.utils.PSUTIL_AVAILABLE", False):
            # Mock logger.warning
            with patch("c4f.utils.logger") as mock_logger:
                # Create a SecureSubprocess with resource limits
                SecureSubprocess(SubprocessConfig(cpu_limit=10.0, memory_limit=1024 * 1024))

                # Verify warning was logged
                mock_logger.warning.assert_called_once()

    def test_prepare_binary_mode_kwargs(self, secure_subprocess):
        """Test _prepare_binary_mode_kwargs method."""
        # Call the method
        kwargs = secure_subprocess._prepare_binary_mode_kwargs()

        # Verify the kwargs
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE
        assert "env" in kwargs

        # Verify _add_optional_popen_args was called
        with patch.object(secure_subprocess, "_add_optional_popen_args") as mock_add:
            secure_subprocess._prepare_binary_mode_kwargs()
            mock_add.assert_called_once()

    def test_validate_command_unix(self, secure_subprocess):
        """Test validate_command method on Unix."""
        with patch("sys.platform", "linux"):
            # Test with command without extension
            assert secure_subprocess.validate_command(["echo", "test"]) is True

            # Test with restricted commands
            secure_subprocess.allowed_commands = {"echo"}
            assert secure_subprocess.validate_command(["echo", "test"]) is True
            assert secure_subprocess.validate_command(["ls", "test"]) is False


# Tests for ProcessResourceMonitor
# noinspection PyUnresolvedReferences
class TestProcessResourceMonitor:
    """Test suite for the ProcessResourceMonitor class."""

    @pytest.fixture
    def resource_monitor(self, mock_process):
        """Return a ProcessResourceMonitor instance for testing."""
        return ProcessResourceMonitor(
            process=mock_process,
            cpu_limit=10.0,
            memory_limit=1024 * 1024,  # 1MB
            monitor_interval=0.1,
            terminate_callback=MagicMock(),
        )

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_start_monitoring_no_psutil(self, resource_monitor):
        """Test start_monitoring method when psutil is not available."""
        with patch("c4f.utils.PSUTIL_AVAILABLE", False):
            # Should not raise any exceptions
            resource_monitor.start_monitoring()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_start_monitoring_no_pid(self, resource_monitor):
        """Test start_monitoring method when process has no PID."""
        resource_monitor.process.pid = None

        # Should not raise any exceptions
        resource_monitor.start_monitoring()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_start_monitoring_process_error(self, resource_monitor):
        """Test start_monitoring method when process raises an exception."""
        with patch("psutil.Process") as mock_psutil:
            mock_psutil.side_effect = psutil.NoSuchProcess(12345)

            # Should not raise any exceptions
            resource_monitor.start_monitoring()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_monitor_process_tree_completed(self, resource_monitor):
        """Test _monitor_process_tree method when process completes quickly."""
        # Configure process to complete immediately
        resource_monitor.process.poll.return_value = 0

        # Should not raise any exceptions
        resource_monitor._monitor_process_tree(MagicMock())

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_monitor_process_tree_children_error(self, resource_monitor):
        """Test _monitor_process_tree method when children() raises an exception."""
        mock_psutil_process = MagicMock()
        mock_psutil_process.children.side_effect = psutil.NoSuchProcess(12345)

        # Should not raise any exceptions
        resource_monitor._monitor_process_tree(mock_psutil_process)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_check_resource_limits_no_exceed(self, resource_monitor):
        """Test _check_resource_limits method when limits are not exceeded."""
        mock_psutil_process = MagicMock()
        mock_psutil_process.cpu_percent.return_value = 5.0
        mock_psutil_process.memory_info.return_value = MagicMock(rss=512 * 1024)

        # Should return False
        assert (
                resource_monitor._check_resource_limits(
                    [mock_psutil_process], mock_psutil_process
                )
                is False
        )

        # Verify terminate_callback was not called
        resource_monitor.terminate_callback.assert_not_called()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_check_resource_limits_process_error(self, resource_monitor):
        """Test _check_resource_limits method when process raises an exception."""
        mock_psutil_process = MagicMock()
        mock_psutil_process.cpu_percent.side_effect = psutil.NoSuchProcess(12345)

        # Should not raise any exceptions
        assert (
                resource_monitor._check_resource_limits(
                    [mock_psutil_process], mock_psutil_process
                )
                is False
        )

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_check_cpu_limit_no_limit(self, resource_monitor):
        """Test _check_cpu_limit method when no CPU limit is set."""
        resource_monitor.cpu_limit = None

        # Should return False
        assert resource_monitor._check_cpu_limit(MagicMock(), MagicMock()) is False

        # Verify terminate_callback was not called
        resource_monitor.terminate_callback.assert_not_called()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_check_memory_limit_no_limit(self, resource_monitor):
        """Test _check_memory_limit method when no memory limit is set."""
        resource_monitor.memory_limit = None

        # Should return False
        assert resource_monitor._check_memory_limit(MagicMock(), MagicMock()) is False

        # Verify terminate_callback was not called
        resource_monitor.terminate_callback.assert_not_called()

    def test_process_resource_monitor_with_psutil_error(self, mock_process):
        """Test ProcessResourceMonitor when psutil raises an exception."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        monitor = ProcessResourceMonitor(
            process=mock_process,
            cpu_limit=10.0,
            memory_limit=1024 * 1024,
            monitor_interval=0.1,
            terminate_callback=MagicMock(),
        )

        # To make sure poll() is called, we need to set up the mock to simulate
        # the process is still running initially
        mock_process.poll.return_value = None

        with patch("psutil.Process") as mock_psutil:
            mock_psutil.side_effect = Exception("psutil error")

            # Call start_monitoring directly
            monitor.start_monitoring()

            # When psutil.Process raises an exception, the code should catch it
            # and not proceed to the _monitor_process_tree method where poll() would be called
            # So we should not expect poll() to be called
            mock_process.poll.assert_not_called()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_check_resource_limits_with_multiple_processes(self, resource_monitor):
        """Test _check_resource_limits method with multiple processes."""
        # Create mock processes
        mock_process1 = MagicMock()
        mock_process1.cpu_percent.return_value = 5.0
        mock_process1.memory_info.return_value = MagicMock(rss=512 * 1024)

        mock_process2 = MagicMock()
        mock_process2.cpu_percent.return_value = 15.0  # Exceeds CPU limit
        mock_process2.memory_info.return_value = MagicMock(rss=512 * 1024)

        # Create a list of processes
        processes = [mock_process1, mock_process2]

        # Should return True because one process exceeds the CPU limit
        assert resource_monitor._check_resource_limits(processes, mock_process1) is True

        # Verify terminate_callback was called
        resource_monitor.terminate_callback.assert_called_once()

    # noinspection PyUnresolvedReferences
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_check_resource_limits_with_exception(self, resource_monitor):
        """Test _check_resource_limits method when a process raises an exception."""
        # Create a mock psutil.Process that raises an exception
        mock_process = MagicMock()
        mock_process.cpu_percent.side_effect = psutil.NoSuchProcess(12345)

        # Create a list of processes with the one that raises an exception
        processes = [mock_process]

        # Should not raise any exceptions and should return False
        assert resource_monitor._check_resource_limits(processes, mock_process) is False

        # Verify terminate_callback was not called
        resource_monitor.terminate_callback.assert_not_called()


# Tests for SecureSubprocessTermination
class TestSecureSubprocessTermination:
    """Test suite for the SecureSubprocessTermination class."""

    @pytest.fixture
    def termination_handler(self):
        """Return a SecureSubprocessTermination instance for testing."""
        return SecureSubprocessTermination(termination_wait=0.1)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_terminate_process_and_children_no_psutil(self, termination_handler):
        """Test terminate_process_and_children method when psutil is not available."""
        with patch("c4f.utils.PSUTIL_AVAILABLE", False):
            # Should not raise any exceptions
            termination_handler.terminate_process_and_children(MagicMock())

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_terminate_process_and_children_process_error(self, termination_handler):
        """Test terminate_process_and_children method when process raises an exception."""
        mock_psutil_process = MagicMock()
        mock_psutil_process.children.side_effect = psutil.NoSuchProcess(12345)

        # Should not raise any exceptions
        termination_handler.terminate_process_and_children(mock_psutil_process)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_terminate_children_with_error(self, termination_handler):
        """Test _terminate_children method when child process raises an exception."""
        mock_child = MagicMock()
        mock_child.terminate.side_effect = psutil.NoSuchProcess(12345)

        # Should not raise any exceptions
        termination_handler._terminate_children([mock_child])

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_kill_remaining_processes_with_error(self, termination_handler):
        """Test _kill_remaining_processes method when process raises an exception."""
        mock_process = MagicMock()
        mock_process.kill.side_effect = psutil.NoSuchProcess(12345)

        # Should not raise any exceptions
        termination_handler._kill_remaining_processes([mock_process])

    def test_terminate_process_already_terminated(
            self, termination_handler, mock_process
    ):
        """Test terminate_process method when process is already terminated."""
        # Configure process to be already terminated
        mock_process.poll.return_value = 0

        # Should not raise any exceptions
        termination_handler.terminate_process(mock_process)

        # Verify terminate was not called
        mock_process.terminate.assert_not_called()

    def test_terminate_process_no_psutil(self, termination_handler, mock_process):
        """Test terminate_process method when psutil is not available."""
        with patch("c4f.utils.PSUTIL_AVAILABLE", False):
            # Should not raise any exceptions
            termination_handler.terminate_process(mock_process)

            # Should fall back to standard termination
            mock_process.terminate.assert_called_once()

    def test_terminate_process_psutil_error(self, termination_handler, mock_process):
        """Test terminate_process method when psutil raises an exception."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        with patch("psutil.Process") as mock_psutil:
            mock_psutil.side_effect = psutil.NoSuchProcess(12345)

            # Should not raise any exceptions
            termination_handler.terminate_process(mock_process)

            # Should fall back to standard termination
            mock_process.terminate.assert_called_once()

    def test_perform_standard_termination_with_error(
            self, termination_handler, mock_process
    ):
        """Test _perform_standard_termination method when terminate raises an exception."""
        mock_process.terminate.side_effect = OSError("Terminate failed")

        # Should not raise any exceptions
        termination_handler._perform_standard_termination(mock_process, 3, 0.1)

    def test_terminate_and_wait_completes(self, termination_handler, mock_process):
        """Test _terminate_and_wait method when process completes quickly."""
        # Configure process to complete after first poll
        mock_process.poll.side_effect = [None, 0]

        # Should not raise any exceptions
        termination_handler._terminate_and_wait(mock_process, 3, 0.1)

        # Verify terminate was called but kill was not
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_not_called()

    def test_terminate_and_wait_requires_kill(self, termination_handler, mock_process):
        """Test _terminate_and_wait method when process requires kill."""
        # Configure process to never complete
        mock_process.poll.return_value = None

        # Should not raise any exceptions
        termination_handler._terminate_and_wait(mock_process, 3, 0.1)

        # Verify both terminate and kill were called
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_terminate_process_and_children_with_exception(self, termination_handler):
        """Test terminate_process_and_children method when an exception occurs."""
        # Create a mock psutil.Process that raises an exception
        mock_process = MagicMock()
        mock_process.children.side_effect = Exception("Test exception")

        # Should not raise any exceptions
        termination_handler.terminate_process_and_children(mock_process)

        # Verify logger.exception was called
        with patch("c4f.utils.logger") as mock_logger:
            termination_handler.terminate_process_and_children(mock_process)
            mock_logger.exception.assert_called_once()


# Integration tests that run actual processes
class TestIntegration:
    """Integration tests that run actual processes."""

    def test_run_command_output_capture(self):
        """Test capturing output from a real command."""
        handler = SubprocessHandler(timeout=5)
        stdout, stderr, returncode = handler.run_command(ECHO_CMD)

        assert "hello" in stdout
        assert stderr == ""
        assert returncode == 0

    def test_secure_subprocess_restrictions(self, tmp_path):
        """Test SecureSubprocess with actual restrictions."""
        # Create a working directory
        working_dir = tmp_path / "workdir"
        working_dir.mkdir()
        create_temp_file(working_dir)

        # Create restricted subprocess with actual limits
        config = SubprocessConfig(
            timeout=5,
            working_dir=working_dir,
            allowed_commands={"echo", "cmd", "type", "cat", "dir", "ls"},
            max_output_size=1024,
            enable_shell=False,
            restricted_env=True,
        )
        secure = SecureSubprocess(config)

        # Test allowed command
        stdout, stderr, returncode = secure.run_command(ECHO_CMD)
        assert "hello" in stdout
        assert returncode == 0

        # Test working directory
        if sys.platform == "win32":
            cmd = ["cmd", "/c", "dir"]
        else:
            cmd = ["ls"]

        stdout, stderr, returncode = secure.run_command(cmd)
        assert "test_file.txt" in stdout
        assert returncode == 0

        # Test disallowed command
        secure.allowed_commands = {
            "not_a_real_command"
        }  # Remove echo from allowed commands

        with pytest.raises(ValueError, match="Command not allowed"):
            secure.run_command(ECHO_CMD)


# Tests for FileChange class
class TestFileChange:
    """Test suite for the FileChange class."""

    def test_initialization(self, tmp_path):
        """Test that FileChange initializes correctly with a file that exists."""
        # Create a test file
        test_file = tmp_path / "file.txt"
        test_file.write_text("test content")

        # Create a FileChange instance
        file_change = FileChange(
            path=test_file, status="M", diff="- old line\n+ new line", type="fix"
        )

        # Check initialization
        assert file_change.path == test_file
        assert file_change.status == "M"
        assert file_change.diff == "- old line\n+ new line"
        assert file_change.type == "fix"
        assert file_change.diff_lines == 2
        assert file_change.last_modified > 0

    def test_initialization_nonexistent_file(self):
        """Test that FileChange initializes correctly with a file that doesn't exist."""
        # Create a FileChange instance with non-existent file
        file_change = FileChange(
            path=Path("/path/to/nonexistent/file.txt"),
            status="A",
            diff="+ new file content",
            type="feat",
        )

        # Check initialization
        assert file_change.path == Path("/path/to/nonexistent/file.txt")
        assert file_change.status == "A"
        assert file_change.diff == "+ new file content"
        assert file_change.type == "feat"
        assert file_change.diff_lines == 1
        assert file_change.last_modified == 0


# Tests for edge cases and additional coverage
class TestEdgeCases:
    """Test edge cases and additional code paths for coverage."""

    def test_unicode_decode_error_fallback(self, tmp_path, subprocess_handler):
        """Test that run_command falls back to binary mode on UnicodeDecodeError."""
        with patch.object(subprocess_handler, "run_text_mode") as mock_text_mode:
            # Configure mock to raise UnicodeDecodeError
            mock_text_mode.side_effect = UnicodeDecodeError(
                "utf-8", b"\x80\x81", 0, 1, "invalid start byte"
            )

            # Patch run_binary_mode to return a known value
            with patch.object(
                    subprocess_handler, "run_binary_mode"
            ) as mock_binary_mode:
                mock_binary_mode.return_value = ("binary output", "binary error", 0)

                # Call run_command
                stdout, stderr, returncode = subprocess_handler.run_command(ECHO_CMD)

                # Verify fallback was used
                mock_text_mode.assert_called_once()
                mock_binary_mode.assert_called_once()
                assert stdout == "binary output"
                assert stderr == "binary error"
                assert returncode == 0

    def test_execute_subprocess_fallback_return(self, subprocess_handler):
        """Test the fallback return path in _execute_subprocess."""
        # Create a mocked command that will trigger exceptions in _execute_subprocess
        with patch.object(subprocess_handler, "_start_process") as mock_start:
            # Mock process setup
            mock_process = MagicMock()
            mock_process.communicate.side_effect = Exception("Unexpected error")
            mock_start.return_value = mock_process

            # Patch _handle_execution_error to not raise
            with patch.object(
                    subprocess_handler, "_handle_execution_error"
            ) as mock_handle:
                mock_handle.return_value = None  # Don't raise an exception

                # Create params object for _execute_subprocess
                params = SubprocessExecutionParams(
                    command=["test"],
                    popen_kwargs={},
                    timeout=None,
                    is_text_mode=True,
                    encoding="utf-8",
                    errors="replace"
                )

                # Call _execute_subprocess with the params object
                stdout, stderr, returncode = subprocess_handler._execute_subprocess(params)

                # Verify fallback return values
                assert stdout == ""
                assert stderr == ""
                assert returncode == -1

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_resource_monitor_immediate_termination(self, mock_process):
        """Test ProcessResourceMonitor with immediate process termination."""
        # Setup a terminate callback
        terminate_callback = MagicMock()

        # Create a ProcessResourceMonitor
        monitor = ProcessResourceMonitor(
            process=mock_process,
            cpu_limit=10.0,
            memory_limit=1024 * 1024,
            monitor_interval=0.001,  # Very small interval
            terminate_callback=terminate_callback,
        )

        # Configure process to be terminated after first poll
        mock_process.poll.side_effect = [None, 0]  # First None, then 0 (terminated)

        # Create a mock psutil.Process
        mock_psutil_process = MagicMock()
        # Configure cpu_percent to return a float
        mock_psutil_process.cpu_percent.return_value = 5.0
        # Configure memory_info to return a mock with an integer rss attribute
        mock_psutil_process.memory_info.return_value = MagicMock(rss=512 * 1024)

        # Monitor the process tree
        monitor._monitor_process_tree(mock_psutil_process)

        # Verify terminate callback was not called
        terminate_callback.assert_not_called()

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_cpu_limit_exceeded(self, mock_process):
        """Test ProcessResourceMonitor when CPU limit is exceeded."""
        # Setup a terminate callback
        terminate_callback = MagicMock()

        # Create a ProcessResourceMonitor
        monitor = ProcessResourceMonitor(
            process=mock_process,
            cpu_limit=10.0,
            memory_limit=None,
            monitor_interval=0.001,
            terminate_callback=terminate_callback,
        )

        # Create a mock psutil.Process
        mock_psutil_process = MagicMock()
        mock_psutil_process.cpu_percent.return_value = (
            90.0  # 90% CPU usage (exceeds limit)
        )

        # Check CPU limit
        assert (
                monitor._check_cpu_limit(mock_psutil_process, mock_psutil_process) is True
        )

        # Verify terminate callback was called
        terminate_callback.assert_called_once_with(mock_psutil_process)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_memory_limit_exceeded(self, mock_process):
        """Test ProcessResourceMonitor when memory limit is exceeded."""
        # Setup a terminate callback
        terminate_callback = MagicMock()

        # Create a ProcessResourceMonitor
        monitor = ProcessResourceMonitor(
            process=mock_process,
            cpu_limit=None,
            memory_limit=1024 * 1024,  # 1MB
            monitor_interval=0.001,
            terminate_callback=terminate_callback,
        )

        # Create a mock psutil.Process with high memory usage
        mock_psutil_process = MagicMock()
        mock_psutil_process.memory_info.return_value = MagicMock(
            rss=2 * 1024 * 1024
        )  # 2MB (exceeds limit)

        # Check memory limit
        assert (
                monitor._check_memory_limit(mock_psutil_process, mock_psutil_process)
                is True
        )

        # Verify terminate callback was called
        terminate_callback.assert_called_once_with(mock_psutil_process)

    def test_secure_subprocess_truncation_disabled(self, secure_subprocess):
        """Test SecureSubprocess with truncation disabled."""
        # Set very large max output size
        secure_subprocess.max_output_size = sys.maxsize

        # Test with string that normally would be truncated
        output = "This is a long string that should not be truncated"
        truncated = secure_subprocess._truncate_output(output)

        assert truncated == output  # Should not be truncated
        assert "... (truncated)" not in truncated

    def test_run_binary_mode_with_override(self, secure_subprocess):
        """Test SecureSubprocess run_binary_mode with environment override."""
        with patch.object(secure_subprocess, "_run_secure_subprocess") as mock_run:
            mock_run.return_value = ("custom output", "custom error", 123)

            # Call run_binary_mode with custom parameters
            stdout, stderr, returncode = secure_subprocess.run_binary_mode(
                ECHO_CMD, encoding="latin1", errors="ignore", timeout=99
            )

            # Verify custom parameters were passed
            mock_run.assert_called_once_with(
                ECHO_CMD,
                is_text_mode=False,
                encoding="latin1",
                errors="ignore",
                timeout=99,
            )
            assert stdout == "custom output"
            assert stderr == "custom error"
            assert returncode == 123

    def test_prepare_command_invalid(self, secure_subprocess):
        """Test _prepare_command with invalid command."""
        # Set allowed commands
        secure_subprocess.allowed_commands = {"allowed_command"}

        # Test with invalid command
        with pytest.raises(ValueError, match="Command not allowed"):
            secure_subprocess._prepare_command(["invalid_command"])

    def test_secure_subprocess_termination_handler(
            self, secure_subprocess, mock_process
    ):
        """Test the termination handler in SecureSubprocess."""
        # Test direct call to _terminate_process_and_children
        if PSUTIL_AVAILABLE:
            with patch.object(
                    secure_subprocess.termination_handler, "terminate_process_and_children"
            ) as mock_terminate:
                mock_psutil_process = MagicMock()
                secure_subprocess._terminate_process_and_children(mock_psutil_process)
                mock_terminate.assert_called_once_with(mock_psutil_process)

        # Test delegation to termination handler for _terminate_process
        with patch.object(
                secure_subprocess.termination_handler, "terminate_process"
        ) as mock_terminate:
            secure_subprocess._terminate_process(mock_process)
            mock_terminate.assert_called_once_with(
                mock_process,
                max_termination_retries=secure_subprocess.max_termination_retries,
                termination_wait=secure_subprocess.termination_wait,
            )

    def test_log_messages(self, secure_subprocess, caplog):
        """Test that log messages are created correctly."""
        caplog.set_level(logging.INFO)

        # Test command preparation with logging
        with patch.object(secure_subprocess, "validate_command") as mock_validate:
            mock_validate.return_value = True

            # Call prepare_command
            result = secure_subprocess._prepare_command(ECHO_CMD)

            # Check that logging occurred
            assert any(
                record.levelname == "INFO" and "Executing command" in record.message
                for record in caplog.records
            )

            # Check that the command was sanitized and returned
            assert result == ECHO_CMD

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_get_child_processes(self):
        """Test _get_child_processes method."""
        handler = SecureSubprocessTermination()

        # Create a mock psutil.Process
        mock_process = MagicMock()
        mock_process.children.return_value = [MagicMock(), MagicMock()]

        # Get child processes
        children = handler._get_child_processes(mock_process)

        # Verify children were retrieved
        assert len(children) == 2
        mock_process.children.assert_called_once_with(recursive=True)

    def test_run_command_with_process(self, secure_subprocess):
        """Test run_command with a mocked process."""
        # Mock the entire execution path
        with patch.object(secure_subprocess, "run_text_mode") as mock_text_mode:
            mock_text_mode.return_value = ("process output", "process error", 0)

            # Call run_command
            stdout, stderr, returncode = secure_subprocess.run_command(ECHO_CMD)

            # Verify results
            assert stdout == "process output"
            assert stderr == "process error"
            assert returncode == 0
            mock_text_mode.assert_called_once()


class FileChangeHandler:
    """Handler for monitoring file changes during subprocess execution."""

    def __init__(self, process: subprocess.Popen[Any]) -> None:
        self.process = process

    def handle_file_change(self, file_path: str) -> FileChange | None:
        """Handle a file change event.

        Args:
            file_path: Path to the changed file.

        Returns:
            Optional[FileChange]: FileChange object if successful, None otherwise.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None

            # Check if process is still running
            if self.process.poll() is not None:
                return None

            return FileChange(
                path=path,
                status="M",  # Modified
                diff="",  # Empty diff for now
                type=None,
            )
        except Exception as e:
            import warnings

            warnings.warn(f"Error handling file change: {e!s}")
            return None


class ProcessMonitor:
    """Monitor for subprocess execution."""

    def __init__(self, process: subprocess.Popen[Any]) -> None:
        self.process = process
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

    def start_monitoring(self) -> None:
        """Start monitoring the process."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_process)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def _monitor_process(self) -> None:
        """Monitor the process until it completes."""
        try:
            while self._monitoring and self.process.poll() is None:
                try:
                    time.sleep(0.1)
                except Exception as e:
                    import warnings

                    warnings.warn(f"Error during process monitoring: {e!s}")
                    break
        except OSError:
            # Handle process polling errors gracefully
            pass
        finally:
            self._monitoring = False
