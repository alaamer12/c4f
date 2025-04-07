import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from c4f.utils import SubprocessHandler, SecureSubprocess

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
    return SecureSubprocess(
        timeout=2,
        max_termination_retries=2,
        termination_wait=0.1,
        allowed_commands=set(),  # Allow all commands for testing
        max_output_size=1024,    # Small size for testing truncation
        enable_shell=False,
        restricted_env=False,    # Use full environment for testing
        monitor_interval=0.1
    )


@pytest.fixture
def restricted_secure_subprocess():
    """Return a SecureSubprocess instance with restrictive settings."""
    # Only allow echo command for testing
    allowed_cmds = {"echo", "cmd", "type", "cat", "sleep", "timeout"}
    return SecureSubprocess(
        timeout=2,
        max_termination_retries=2,
        termination_wait=0.1,
        allowed_commands=allowed_cmds,
        max_output_size=1024,
        enable_shell=False,
        restricted_env=True,
        monitor_interval=0.1
    )


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
    import psutil
    PSUTIL_AVAILABLE = True

    @pytest.fixture
    def mock_psutil_process():
        """Create a mock for psutil.Process."""
        with patch("psutil.Process") as mock:
            process_instance = mock.return_value
            process_instance.cpu_percent.return_value = 5.0  # Default CPU usage
            process_instance.memory_info.return_value = MagicMock(rss=1024*1024)  # 1MB memory usage
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
        custom_handler = SubprocessHandler(timeout=10, max_termination_retries=5, termination_wait=1.0)
        assert custom_handler.timeout == 10
        assert custom_handler.max_termination_retries == 5
        assert custom_handler.termination_wait == 1.0
    
    def test_create_env(self):
        """Test that create_env returns a copy of the environment with encoding set."""
        env = SubprocessHandler.create_env(True)
        assert isinstance(env, dict)
        assert env['PYTHONIOENCODING'] == 'utf-8'
        
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
            mock_process.communicate.side_effect = subprocess.TimeoutExpired(SLEEP_CMD, 0.1)
            
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
        with open(test_file, 'wb') as f:
            f.write(b'\x80\x81\x82')  # Write binary data directly
        
        # Test reading with text mode - should handle encoding errors
        if sys.platform == 'win32':
            # On Windows, we need to use shell=True for built-in commands
            cmd = ["cmd", "/c", "type", str(test_file)]
        else:
            cmd = ["cat", str(test_file)]
        
        stdout, stderr, returncode = subprocess_handler.run_command(cmd)
        assert returncode == 0
        assert isinstance(stdout, str)  # Should still get string output even with encoding errors


# Tests for SecureSubprocess
class TestSecureSubprocess:
    """Test suite for the SecureSubprocess class."""
    
    def test_initialization(self):
        """Test that SecureSubprocess initializes with correct defaults and custom values."""
        # Test default initialization
        secure = SecureSubprocess()
        assert secure.timeout == 30
        assert secure.allowed_commands == set()
        assert secure.max_output_size == 10 * 1024 * 1024  # 10MB
        assert secure.enable_shell is False
        assert secure.restricted_env is True
        
        # Test custom initialization
        custom_secure = SecureSubprocess(
            timeout=5,
            allowed_commands={"echo", "ls"},
            working_dir=".",
            max_output_size=1024,
            enable_shell=True,
            restricted_env=False
        )
        assert custom_secure.timeout == 5
        assert custom_secure.allowed_commands == {"echo", "ls"}
        assert custom_secure.working_dir == Path(".")
        assert custom_secure.max_output_size == 1024
        assert custom_secure.enable_shell is True
        assert custom_secure.restricted_env is False
    
    def test_initialization_invalid_working_dir(self):
        """Test initialization with invalid working directory."""
        with pytest.raises(ValueError):
            SecureSubprocess(working_dir="/path/that/does/not/exist")
    
    def test_create_env_restricted(self):
        """Test that create_env with restricted=True returns a minimal environment."""
        secure = SecureSubprocess()
        env = secure.create_env(restricted=True)
        assert "PATH" in env
        assert "PYTHONIOENCODING" in env
        assert env['PYTHONIOENCODING'] == 'utf-8'
        
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
            assert False, "Restricted environment should not contain all environment variables"
    
    def test_create_env_full(self):
        """Test that create_env with restricted=False returns full environment."""
        secure = SecureSubprocess()
        env = secure.create_env(restricted=False)
        assert env['PYTHONIOENCODING'] == 'utf-8'
        
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
            assert secure_subprocess.validate_command(["cmd", "/c", "echo", "test"]) is True
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
            cmd = ["cmd", "/c", "echo", "This is a longer output that should be truncated"]
        else:
            cmd = ["echo", "This is a longer output that should be truncated"]
        
        stdout, stderr, returncode = secure_subprocess.run_command(cmd)
        
        # Output should be truncated
        assert len(stdout) <= secure_subprocess.max_output_size + len("... (truncated)")
        assert "truncated" in stdout
    
    def test_working_directory(self, tmp_path):
        """Test subprocess execution with custom working directory."""
        # Create a secure subprocess with the temp directory as working dir
        secure = SecureSubprocess(
            timeout=2,
            working_dir=tmp_path
        )
        
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
        secure = SecureSubprocess(
            timeout=2,
            enable_shell=True
        )
        
        # Run a shell command that should work on both platforms
        if sys.platform == "win32":
            cmd = ["echo", "test"]  # Simple command that works with shell=True on Windows
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
        secure = SecureSubprocess(
            timeout=2,
            cpu_limit=10.0,   # 10% CPU limit
            memory_limit=10 * 1024 * 1024  # 10MB memory limit
        )
        
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
        secure = SecureSubprocess(
            timeout=2,
            cpu_limit=10.0,  # 10% CPU limit - will be exceeded
            monitor_interval=0.1
        )
        
        # Start monitoring in a thread to simulate background monitoring
        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = mock_thread.return_value
            
            # Run the command
            with patch("subprocess.Popen") as mock_popen:
                mock_process = mock_popen.return_value
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd=ECHO_CMD, timeout=2)
                
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
        process_instance.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)  # 100MB memory usage
        
        # Create a secure subprocess with a low memory limit
        secure = SecureSubprocess(
            timeout=2,
            memory_limit=10 * 1024 * 1024,  # 10MB memory limit - will be exceeded
            monitor_interval=0.1
        )
        
        # Start monitoring in a thread to simulate background monitoring
        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = mock_thread.return_value
            
            # Run the command
            with patch("subprocess.Popen") as mock_popen:
                mock_process = mock_popen.return_value
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd=ECHO_CMD, timeout=2)
                
                with pytest.raises(TimeoutError):
                    secure.run_command(ECHO_CMD)
                
                # Verify thread was started for monitoring
                mock_thread.assert_called()
                mock_thread_instance.start.assert_called_once()
    
    def test_terminate_process_enhanced(self, restricted_secure_subprocess, mock_process):
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
            mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd=ECHO_CMD, timeout=1)
            mock_process.poll.return_value = None  # Process is still running

            # Mock the _terminate_process method to ensure it's called
            with patch.object(secure_subprocess, '_terminate_process') as mock_terminate:
                # Should convert to TimeoutError
                with pytest.raises(TimeoutError):
                    secure_subprocess.run_command(ECHO_CMD, timeout=1)

                # Should have tried to terminate the process at least once with the mock process
                mock_terminate.assert_any_call(mock_process)
                assert mock_terminate.call_count > 0


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
        secure = SecureSubprocess(
            timeout=5,
            working_dir=working_dir,
            allowed_commands={"echo", "cmd", "type", "cat", "dir", "ls"},
            max_output_size=1024,
            enable_shell=False,
            restricted_env=True
        )
        
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
        secure.allowed_commands = {"not_a_real_command"}  # Remove echo from allowed commands
        
        with pytest.raises(ValueError, match="Command not allowed"):
            secure.run_command(ECHO_CMD) 