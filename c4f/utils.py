import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Literal, Any
from rich.console import Console
from g4f.client import Client  # type: ignore

__all__ = ["console", "client", "SubprocessHandler", "FileChange"]

console = Console()

client = Client()

@dataclass
class FileChange:
    path: Path
    status: Literal["M", "A", "D", "R"]
    diff: str
    type: Optional[str] = None  # 'feat', 'fix', 'docs', etc.
    diff_lines: int = 0
    last_modified: float = 0.0

    def __post_init__(self):
        self.diff_lines = len(self.diff.strip().splitlines())
        self.last_modified = os.path.getmtime(self.path) if os.path.exists(self.path) else 0.0



class SubprocessHandler:
    """Dedicated class for handling subprocess execution to prevent memory leaks.

    This class encapsulates subprocess operations, ensuring proper resource management
    and consistent error handling across the application.
    """

    def __init__(self, timeout: Optional[int] = None, 
                 max_termination_retries: Optional[int] = None, 
                 termination_wait: Optional[float] = None) -> None:
        """Initialize the SubprocessHandler with configurable timeout and termination settings.
        
        Args:
            timeout: Maximum time in seconds to wait for a process to complete.
            max_termination_retries: Maximum number of attempts to terminate a process.
            termination_wait: Time to wait between termination attempts in seconds.
        """
        self.process: Optional[subprocess.Popen[Any]] = None
        self.timeout: int = timeout or 30
        self.max_termination_retries: int = max_termination_retries or 3
        self.termination_wait: float = termination_wait or 0.5

    @staticmethod
    def create_env() -> Dict[str, str]:
        """Create environment with explicit encoding settings for subprocess.

        Returns:
            Dict[str, str]: Environment variables dictionary with encoding settings.
        """
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        return env

    def run_text_mode(self, command: List[str], encoding: str = 'utf-8',
                      errors: str = 'replace', timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Run subprocess in text mode with specified encoding.

        Args:
            command: Command to execute as a list of strings.
            encoding: Character encoding to use.
            errors: How to handle encoding/decoding errors.
            timeout: Maximum time in seconds to wait for the process to complete.

        Returns:
            Tuple[str, str, int]: stdout, stderr, and return code.

        Raises:
            TimeoutError: If the process exceeds the specified timeout.
        """
        env = self.create_env()
        process: Optional[subprocess.Popen[Any]] = None
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=encoding,
                errors=errors,
                env=env,
                universal_newlines=True
            )

            stdout, stderr = process.communicate(timeout=timeout or self.timeout)
            return stdout, stderr, process.returncode
        except subprocess.TimeoutExpired:
            # Handle timeout by terminating the process
            self._terminate_process(process)
            raise TimeoutError(f"Command timed out after {timeout or self.timeout} seconds: {' '.join(command)}")
        except Exception as e:
            # Log the error and ensure process is terminated
            console.print(f"[red]Error in subprocess execution: {str(e)}[/red]")
            self._terminate_process(process)
            raise
        finally:
            # Ensure process resources are cleaned up
            self._cleanup_process(process)

    def run_binary_mode(self, command: List[str], encoding: str = 'utf-8',
                        errors: str = 'replace', timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Run subprocess in binary mode with manual decoding.

        Args:
            command: Command to execute as a list of strings.
            encoding: Character encoding to use for decoding.
            errors: How to handle encoding/decoding errors.
            timeout: Maximum time in seconds to wait for the process to complete.

        Returns:
            Tuple[str, str, int]: decoded stdout, stderr, and return code.

        Raises:
            TimeoutError: If the process exceeds the specified timeout.
        """
        env = self.create_env()
        process: Optional[subprocess.Popen[Any]] = None
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            # Use a timeout for communicate to prevent hanging
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout or self.timeout)
            stdout = stdout_bytes.decode(encoding, errors=errors)
            stderr = stderr_bytes.decode(encoding, errors=errors)
            return stdout, stderr, process.returncode
        except subprocess.TimeoutExpired:
            # Handle timeout by terminating the process
            self._terminate_process(process)
            raise TimeoutError(f"Command timed out after {timeout or self.timeout} seconds: {' '.join(command)}")
        except Exception as e:
            # Log the error and ensure process is terminated
            console.print(f"[red]Error in subprocess execution: {str(e)}[/red]")
            self._terminate_process(process)
            raise
        finally:
            # Ensure process resources are cleaned up
            self._cleanup_process(process)

    def run_command(self, command: List[str], timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute a command and return its output.

        The command is executed as a subprocess and the function waits for it to complete.
        Returns stdout, stderr, and the return code as a tuple.

        Args:
            command: Command to execute as a list of strings.
            timeout: Maximum time in seconds to wait for the process to complete.

        Returns:
            Tuple[str, str, int]: stdout, stderr, and return code.

        Raises:
            TimeoutError: If the process exceeds the specified timeout.
        """
        # Set default encoding to UTF-8 with error handling for Windows compatibility
        encoding = 'utf-8'
        errors = 'replace'  # Replace invalid chars with a replacement marker

        try:
            return self.run_text_mode(command, encoding, errors, timeout)
        except UnicodeDecodeError:
            # Fall back to binary mode and manual decoding if text mode fails
            return self.run_binary_mode(command, encoding, errors, timeout)

    def _terminate_process(self, process: Optional[subprocess.Popen[Any]]) -> None:
        """Terminate a process with multiple attempts if needed.

        Args:
            process: The subprocess.Popen object to terminate.
        """
        if process is None or process.poll() is not None:
            return

        # Try to terminate the process gracefully
        try:
            process.terminate()

            # Wait for the process to terminate
            for _ in range(self.max_termination_retries):
                if process.poll() is not None:
                    return
                time.sleep(self.termination_wait)

            # If still running, kill it forcefully
            if process.poll() is None:
                process.kill()
        except OSError:
            # Process might already be gone
            pass

    def _cleanup_process(self, process: Optional[subprocess.Popen[Any]]) -> None:
        """Clean up process resources to prevent memory leaks.

        Args:
            process: The subprocess.Popen object to clean up.
        """
        if process is None:
            return

        # Close file descriptors
        for fd in [process.stdout, process.stderr]:
            if fd is not None:
                try:
                    fd.close()
                except (IOError, OSError):
                    pass

        # Ensure process is terminated
        self._terminate_process(process)