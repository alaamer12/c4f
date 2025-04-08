"""Utility functions and classes for the Commit For Free (c4f) application.

This module provides core functionality for the c4f application, including:

Classes:
    - SubprocessHandler: Base class for handling subprocess execution
    - SecureSubprocess: Enhanced version with security features
    - FileChange: Data class for tracking file changes
    
Example:
    To use the secure subprocess handler:

    ```python
    >>> from c4f.utils import SecureSubprocess

    # Create a secure subprocess handler
    >>> handler = SecureSubprocess(
    >>>    timeout=30,
    >>>    allowed_commands={"git"},
    >>>    restricted_env=False
    >>> )

    # Run a command
    >>> stdout, stderr, code = handler.run_command(["git", "status"])
    ```

Note:
    This module requires psutil for resource monitoring features.
    If psutil is not available, resource monitoring will be disabled.
"""

import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Literal, Any, Set, Union, TypeVar, NoReturn, Callable

from g4f.client import Client  # type: ignore
from rich.console import Console

# Try to import psutil for cross-platform process management
try:
    import psutil  # type: ignore

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

__all__ = ["console", "client", "SubprocessHandler", "SecureSubprocess", "FileChange"]

console = Console()

client = Client()

# Configure logging for subprocess operations
logger = logging.getLogger("subprocess_handler")
logger.setLevel(logging.INFO)

# Type variable for subprocess.Popen
T = TypeVar('T', str, bytes)


@dataclass
class FileChange:
    path: Path
    status: Literal["M", "A", "D", "R"]
    diff: str
    type: Optional[str] = None  # 'feat', 'fix', 'docs', etc.
    diff_lines: int = 0
    last_modified: float = 0.0

    def __post_init__(self) -> None:
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

    def create_env(self, restricted: bool = False) -> Dict[str, str]:
        """Create environment with explicit encoding settings for subprocess.

        Args:
            restricted: Whether to use a restricted set of environment variables.
                       In the base class this parameter has no effect.

        Returns:
            Dict[str, str]: Environment variables dictionary with encoding settings.
        """
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        return env

    def _execute_subprocess(self, command: List[str], popen_kwargs: Dict[str, Any],
                            timeout: Optional[int], is_text_mode: bool,
                            encoding: str = 'utf-8', errors: str = 'replace') -> Tuple[str, str, int]:
        """Execute a subprocess with the given parameters."""
        process = self._start_process(command, popen_kwargs)
        try:
            stdout, stderr = self._communicate_with_process(process, timeout)
            return self._process_output(stdout, stderr, is_text_mode, encoding, errors, process)
        except subprocess.TimeoutExpired:
            self._handle_timeout(process, command, timeout)
        except Exception as e:
            self._handle_execution_error(process, e)
        finally:
            self._cleanup_process(process)
        return '', '', -1

    def _start_process(self, command: List[str], popen_kwargs: Dict[str, Any]) -> subprocess.Popen[Any]:
        """Start a subprocess with the given command and parameters."""
        return subprocess.Popen(command, **popen_kwargs)

    def _communicate_with_process(self, process: subprocess.Popen[Any],
                                  timeout: Optional[int]) -> Tuple[Union[str, bytes], Union[str, bytes]]:
        """Communicate with the process and get its output."""
        return process.communicate(timeout=timeout or self.timeout)

    @staticmethod
    def _process_output(stdout: Union[str, bytes], stderr: Union[str, bytes],
                        is_text_mode: bool, encoding: str, errors: str, process: subprocess.Popen[Any]) -> Tuple[
        str, str, int]:
        """Process and decode the subprocess output.
        
        Args:
            stdout: The standard output from the process.
            stderr: The standard error from the process.
            is_text_mode: Whether the output is in text mode.
            encoding: Character encoding to use for decoding.
            errors: How to handle encoding/decoding errors.
            process: The subprocess.Popen object.
            
        Returns:
            Tuple[str, str, int]: Processed stdout, stderr, and return code.
        """
        if not is_text_mode and isinstance(stdout, bytes) and isinstance(stderr, bytes):
            stdout = stdout.decode(encoding, errors=errors)
            stderr = stderr.decode(encoding, errors=errors)
        return str(stdout), str(stderr), int(process.returncode)

    def _handle_timeout(self, process: Optional[subprocess.Popen[Any]], command: List[str],
                        timeout: Optional[int]) -> None:
        """Handle a timeout scenario."""
        self._terminate_process(process)
        raise TimeoutError(f"Command timed out after {timeout or self.timeout} seconds: {' '.join(command)}")

    def _handle_execution_error(self, process: Optional[subprocess.Popen[Any]], error: Exception, ) -> None:
        """Handle execution errors."""
        console.print(f"[red]Error in subprocess execution: {str(error)}[/red]")
        self._terminate_process(process)
        raise error  # Re-raise the original exception after cleanup

    def run_text_mode(self, command: List[str], encoding: str = 'utf-8',
                      errors: str = 'replace', timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Run subprocess in text mode with specified encoding.

        Returns:
            Tuple[str, str, int]: stdout, stderr, and return code.

        Raises:
            TimeoutError: If the process exceeds the specified timeout.
        """
        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'encoding': encoding,
            'errors': errors,
            'env': self.create_env(),
            'universal_newlines': True
        }
        return self._execute_subprocess(command, popen_kwargs, timeout, is_text_mode=True)

    def run_binary_mode(self, command: List[str], encoding: str = 'utf-8',
                        errors: str = 'replace', timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Run subprocess in binary mode with manual decoding.
        Returns:
            Tuple[str, str, int]: decoded stdout, stderr, and return code.

        Raises:
            TimeoutError: If the process exceeds the specified timeout.
        """
        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'env': self.create_env()
        }
        return self._execute_subprocess(command, popen_kwargs, timeout, is_text_mode=False, encoding=encoding,
                                        errors=errors)

    def run_command(self, command: List[str], timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute a command and return its output.

        The command is executed as a subprocess and the function waits for it to complete.
        Returns stdout, stderr, and the return code as a tuple.

        Args:
            command: Command to execute as a list of strings.
            timeout: Maximum time in seconds to wait for the process to complete.

        Returns:
            Tuple[str, str, int]: stdout, stderr, and return code.
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


class ProcessResourceMonitor:
    """Class for monitoring process resource usage."""

    def __init__(self, process: subprocess.Popen[Any],
                 cpu_limit: Optional[float],
                 memory_limit: Optional[int],
                 monitor_interval: float,
                 terminate_callback: Callable) -> None:
        self.process = process
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.monitor_interval = monitor_interval
        self.terminate_callback = terminate_callback

    def start_monitoring(self) -> None:
        """Start monitoring the process resources."""
        if not PSUTIL_AVAILABLE or self.process is None or self.process.pid is None:
            return

        try:
            p = psutil.Process(self.process.pid)
            self._monitor_process_tree(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
            # Process may have disappeared
            pass
        except Exception as e:
            logger.error(f"Error monitoring process resources: {str(e)}")

    def _monitor_process_tree(self, p: "psutil.Process") -> None:
        """Monitor a process tree for resource usage.

        Args:
            p: The psutil.Process object for the subprocess.
        """
        # Monitor child processes too
        processes = [p]
        children = []

        while True:
            if self.process.poll() is not None:
                # Process has completed, no need to continue monitoring
                break

            try:
                # Refresh the list of child processes
                children = p.children(recursive=True)
                processes = [p] + children
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process may have disappeared
                break

            if self._check_resource_limits(processes, p):
                return

            time.sleep(self.monitor_interval)

    def _check_resource_limits(self, processes: List["psutil.Process"], parent: "psutil.Process") -> bool:
        """Check if any process in the list exceeds resource limits.

        Args:
            processes: List of psutil.Process objects to check.
            parent: The parent process to terminate if limits are exceeded.

        Returns:
            bool: True if limits were exceeded and processes were terminated, False otherwise.
        """
        for proc in processes:
            try:
                if self._check_cpu_limit(proc, parent):
                    return True

                if self._check_memory_limit(proc, parent):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process may have disappeared
                continue

        return False

    def _check_cpu_limit(self, proc: "psutil.Process", parent: "psutil.Process") -> bool:
        """Check if a process exceeds the CPU usage limit.

        Args:
            proc: The psutil.Process object to check.
            parent: The parent process to terminate if limits are exceeded.

        Returns:
            bool: True if CPU limit was exceeded and processes were terminated, False otherwise.
        """
        if self.cpu_limit is not None:
            cpu_percent = proc.cpu_percent(interval=0.1)
            if cpu_percent > self.cpu_limit:
                logger.warning(f"Process {proc.pid} exceeded CPU limit: {cpu_percent}% > {self.cpu_limit}%")
                self.terminate_callback(parent)
                return True
        return False

    def _check_memory_limit(self, proc: "psutil.Process", parent: "psutil.Process") -> bool:
        """Check if a process exceeds the memory usage limit.

        Args:
            proc: The psutil.Process object to check.
            parent: The parent process to terminate if limits are exceeded.

        Returns:
            bool: True if memory limit was exceeded and processes were terminated, False otherwise.
        """
        if self.memory_limit is not None:
            mem_info = proc.memory_info()
            if mem_info.rss > self.memory_limit:
                logger.warning(f"Process {proc.pid} exceeded memory limit: {mem_info.rss} > {self.memory_limit}")
                self.terminate_callback(parent)
                return True
        return False


class SecureSubprocessTermination:
    """Class responsible for safely terminating processes and their child processes."""

    def __init__(self, termination_wait: float = 0.5) -> None:
        """Initialize the termination handler.
        
        Args:
            termination_wait: Time to wait between termination attempts in seconds.
        """
        self.termination_wait = termination_wait

    def terminate_process_and_children(self, proc: "psutil.Process") -> None:
        """Terminate a process and all its children.
        
        Args:
            proc: The psutil.Process object to terminate.
        """
        if not PSUTIL_AVAILABLE:
            return

        try:
            children = self._get_child_processes(proc)
            self._terminate_children(children)
            self._terminate_parent(proc)
            self._handle_remaining_processes(proc, children)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
            # Process may have disappeared
            pass
        except Exception as e:
            logger.error(f"Error terminating process tree: {str(e)}")

    @staticmethod
    def _get_child_processes(proc: "psutil.Process") -> List["psutil.Process"]:
        """Get all child processes recursively."""
        return proc.children(recursive=True)

    @staticmethod
    def _terminate_children(children: List["psutil.Process"]) -> None:
        """Terminate all child processes."""
        for child in children:
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    @staticmethod
    def _terminate_parent(proc: "psutil.Process") -> None:
        """Terminate the parent process."""
        proc.terminate()

    def _handle_remaining_processes(self, proc: "psutil.Process",
                                    children: List["psutil.Process"]) -> None:
        """Wait for processes to terminate and kill any remaining ones.
        
        Args:
            proc: The parent process.
            children: List of child processes.
        """
        gone, still_alive = psutil.wait_procs([proc] + children, timeout=self.termination_wait)
        self._kill_remaining_processes(still_alive)

    @staticmethod
    def _kill_remaining_processes(processes: List["psutil.Process"]) -> None:
        """Forcefully kill processes that didn't terminate gracefully."""
        for p in processes:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def terminate_process(self, process: subprocess.Popen[Any],
                          max_termination_retries: int = 3,
                          termination_wait: Optional[float] = None) -> None:
        """Terminate a process with multiple attempts if needed.
        
        Enhanced to use psutil for more thorough termination if available.

        Args:
            process: The subprocess.Popen object to terminate.
            max_termination_retries: Maximum number of attempts to terminate a process.
            termination_wait: Time to wait between termination attempts in seconds.
        """
        if self._is_process_already_terminated(process):
            return

        if self._try_psutil_termination(process):
            return

        # Fall back to standard termination if psutil failed or is unavailable
        self._perform_standard_termination(process, max_termination_retries, termination_wait)

    @staticmethod
    def _is_process_already_terminated(process: Optional[subprocess.Popen[Any]]) -> bool:
        """Check if the process is None or already terminated."""
        return process is None or process.poll() is not None

    def _try_psutil_termination(self, process: subprocess.Popen[Any]) -> bool:
        """Attempt to terminate the process using psutil if available.
        
        Args:
            process: The subprocess.Popen object to terminate.
            
        Returns:
            bool: True if psutil termination was successful, False otherwise.
        """
        if not (PSUTIL_AVAILABLE and process.pid is not None):
            return False

        try:
            p = psutil.Process(process.pid)
            self.terminate_process_and_children(p)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
            # Fall back to standard termination
            return False
        except Exception as e:
            logger.error(f"Error during psutil termination: {str(e)}")
            return False

    def _perform_standard_termination(self, process: subprocess.Popen[Any],
                                      max_termination_retries: int,
                                      termination_wait: Optional[float]) -> None:
        """Perform standard process termination with retries.
        
        Args:
            process: The subprocess.Popen object to terminate.
            max_termination_retries: Maximum number of attempts to terminate a process.
            termination_wait: Time to wait between termination attempts in seconds.
        """
        wait_time = termination_wait or self.termination_wait

        try:
            self._terminate_and_wait(process, max_termination_retries, wait_time)
        except OSError:
            # Process might already be gone
            pass

    @staticmethod
    def _terminate_and_wait(process: subprocess.Popen[Any],
                            max_retries: int, wait_time: float) -> None:
        """Terminate a process and wait for it to exit, with force kill if needed.
        
        Args:
            process: The subprocess.Popen object to terminate.
            max_retries: Maximum number of attempts to terminate a process.
            wait_time: Time to wait between termination attempts in seconds.
        """
        process.terminate()

        # Wait for the process to terminate
        for _ in range(max_retries):
            if process.poll() is not None:
                return
            time.sleep(wait_time)

        # If still running, kill it forcefully
        if process.poll() is None:
            process.kill()


class SecureSubprocess(SubprocessHandler):
    """Enhanced version of SubprocessHandler with additional security measures.

    This class extends SubprocessHandler with security features such as:
    - Command validation and sanitization
    - Restricted environment variables
    - Working directory control
    - Resource limits using psutil (cross-platform)
    - Output size limits
    - Audit logging
    - Shell execution control
    """

    def __init__(self, timeout: Optional[int] = None,
                 max_termination_retries: Optional[int] = None,
                 termination_wait: Optional[float] = None,
                 allowed_commands: Optional[Set[str]] = None,
                 working_dir: Optional[Union[str, Path]] = None,
                 max_output_size: int = 10 * 1024 * 1024,  # 10MB default
                 cpu_limit: Optional[float] = None,  # Percentage (0-100)
                 memory_limit: Optional[int] = None,  # In bytes
                 enable_shell: bool = False,
                 restricted_env: bool = True,
                 monitor_interval: float = 0.5) -> None:

        super().__init__(timeout, max_termination_retries, termination_wait)
        self.allowed_commands: Set[str] = allowed_commands or set()
        self.working_dir: Optional[Path] = Path(working_dir) if working_dir else None
        self.max_output_size: int = max_output_size
        self.cpu_limit: Optional[float] = cpu_limit
        self.memory_limit: Optional[int] = memory_limit
        self.enable_shell: bool = enable_shell
        self.restricted_env: bool = restricted_env
        self.monitor_interval: float = monitor_interval

        # Create a termination handler
        self.termination_handler = SecureSubprocessTermination(termination_wait or self.termination_wait)

        # Validate working directory if provided
        if self.working_dir and not self.working_dir.exists():
            raise ValueError(f"Working directory does not exist: {self.working_dir}")

        # Warn if psutil is not available but resource limits are specified
        if not PSUTIL_AVAILABLE and (cpu_limit is not None or memory_limit is not None):
            logger.warning("Resource limiting requires psutil, but it's not installed. "
                           "Install it with: pip install psutil")

    def create_env(self, restricted: bool = True) -> Dict[str, str]:
        """Create environment with explicit encoding settings for subprocess.

        Args:
            restricted: Whether to use a restricted set of environment variables.

        Returns:
            Dict[str, str]: Environment variables dictionary with encoding settings.
        """
        if restricted:
            # Create a minimal environment with only essential variables
            env = self._get_env()
            # Add only essential paths and variables

            # Add system-specific environment variables
            self._handle_win32_env(env)
        else:
            # Use full environment but still set encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

        return env

    @staticmethod
    def _get_env() -> Dict[str, str]:
        """Get essential environment variables.
        
        This method is kept for backward compatibility.
        
        Returns:
            Dict[str, str]: Dictionary of essential environment variables.
        """
        return {
            'PATH': os.environ.get('PATH', ''),
            'PYTHONIOENCODING': 'utf-8',
            'LANG': os.environ.get('LANG', 'en_US.UTF-8'),
            'LC_ALL': os.environ.get('LC_ALL', 'en_US.UTF-8'),
        }

    @staticmethod
    def _handle_win32_env(env: Dict[str, str]) -> None:
        """Add Windows-specific environment variables.
        
        This method is kept for backward compatibility.
        
        Args:
            env: Environment dictionary to update.
        """
        if sys.platform == "win32":
            env.update({
                'SYSTEMROOT': os.environ.get('SYSTEMROOT', 'C:\\Windows'),
                'TEMP': os.environ.get('TEMP', ''),
                'TMP': os.environ.get('TMP', ''),
                'PATHEXT': os.environ.get('PATHEXT', '.COM;.EXE;.BAT;.CMD'),
                'COMSPEC': os.environ.get('COMSPEC', 'C:\\Windows\\system32\\cmd.exe'),
            })

    def validate_command(self, command: List[str]) -> bool:
        """Validate that the command is allowed to be executed.
        
        Args:
            command: Command to validate as a list of strings.
            
        Returns:
            bool: True if command is valid, False otherwise.
        """
        if not command:
            return False

        # Extract the base command without arguments
        base_cmd = os.path.basename(command[0])

        # On Windows, executables often have extensions (.exe, .bat, etc.)
        if sys.platform == "win32":
            # Remove the extension for command validation
            base_cmd = os.path.splitext(base_cmd)[0]

        # If allowed_commands is empty, all commands are allowed
        if not self.allowed_commands:
            return True

        # Check if the base command is in the allowed list
        return base_cmd in self.allowed_commands

    @staticmethod
    def sanitize_command(command: List[str]) -> List[str]:
        """Sanitize command arguments to prevent injection attacks.
        
        Args:
            command: Command to sanitize as a list of strings.
            
        Returns:
            List[str]: Sanitized command.
        """
        if not command:
            return []

        # Keep the first element (command) as is
        sanitized = [command[0]]

        # Sanitize each argument using platform-specific approach
        for arg in command[1:]:
            if sys.platform == "win32":
                # Windows-specific sanitization
                # Remove characters that could be dangerous in Windows commands
                sanitized_arg = re.sub(r'[&|^<>()]', '', arg)
            else:
                # Unix-like sanitization
                sanitized_arg = re.sub(r'[;&|`$<>]', '', arg)

            sanitized.append(sanitized_arg)

        return sanitized

    def _start_resource_monitoring(self, process: subprocess.Popen[Any]) -> None:
        """Start resource monitoring for the process if limits are set.

        Args:
            process: The subprocess.Popen object to monitor.
        """
        if PSUTIL_AVAILABLE and (self.cpu_limit is not None or self.memory_limit is not None):
            import threading
            monitor = ProcessResourceMonitor(
                process=process,
                cpu_limit=self.cpu_limit,
                memory_limit=self.memory_limit,
                monitor_interval=self.monitor_interval,
                terminate_callback=self.termination_handler.terminate_process_and_children
            )
            monitor_thread = threading.Thread(
                target=monitor.start_monitoring,
                daemon=True
            )
            monitor_thread.start()

    # Delegate process termination to the termination handler
    def _terminate_process_and_children(self, proc: "psutil.Process") -> None:
        """Delegate to termination handler."""
        self.termination_handler.terminate_process_and_children(proc)

    def _terminate_process(self, process: Optional[subprocess.Popen[Any]]) -> None:
        """Delegate to termination handler."""
        self.termination_handler.terminate_process(
            process,  # type: ignore
            max_termination_retries=self.max_termination_retries,
            termination_wait=self.termination_wait
        )

    def _run_secure_subprocess(self, command: List[str], is_text_mode: bool,
                               encoding: str = 'utf-8', errors: str = 'replace',
                               timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Common secure subprocess execution logic for both text and binary modes.

        Returns:
            Tuple[str, str, int]: stdout, stderr, and return code.
        """
        # Validate and prepare command
        sanitized_command = self._prepare_command(command)

        # Prepare Popen arguments based on mode
        popen_kwargs = (self._prepare_text_mode_kwargs(encoding, errors) if is_text_mode
                        else self._prepare_binary_mode_kwargs())

        return self._execute_subprocess(sanitized_command, popen_kwargs, timeout,
                                        is_text_mode=is_text_mode, encoding=encoding, errors=errors)

    def run_text_mode(self, command: List[str], encoding: str = 'utf-8',
                        errors: str = 'replace', timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Run subprocess in text mode with specified encoding and security measures."""
        return self._run_secure_subprocess(command, is_text_mode=True,
                                            encoding=encoding, errors=errors, timeout=timeout)

    def run_binary_mode(self, command: List[str], encoding: str = 'utf-8',
                        errors: str = 'replace', timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Run subprocess in binary mode with manual decoding and security measures."""
        return self._run_secure_subprocess(command, is_text_mode=False,
                                            encoding=encoding, errors=errors, timeout=timeout)

    def _prepare_command(self, command: List[str]) -> List[str]:
        """Validate and sanitize the command.
        
        Args:
            command: Command to execute as a list of strings.
            
        Returns:
            List[str]: Sanitized command.
            
        Raises:
            ValueError: If the command is not allowed.
        """
        if not self.validate_command(command):
            raise ValueError(f"Command not allowed: {command[0]}")

        sanitized_command = self.sanitize_command(command)

        # Log command execution for audit purposes
        logger.info(f"Executing command: {' '.join(sanitized_command)}")

        return sanitized_command

    def _prepare_text_mode_kwargs(self, encoding: str, errors: str) -> Dict[str, Any]:
        """Prepare kwargs for text mode subprocess.
        
        Args:
            encoding: Character encoding to use.
            errors: How to handle encoding/decoding errors.
            
        Returns:
            Dict[str, Any]: Keyword arguments for subprocess.Popen.
        """
        env = self.create_env(restricted=self.restricted_env)

        popen_kwargs: Dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": encoding,
            "errors": errors,
            "env": env,
            "universal_newlines": True,
        }

        self._add_optional_popen_args(popen_kwargs)
        return popen_kwargs

    def _prepare_binary_mode_kwargs(self) -> Dict[str, Any]:
        """Prepare kwargs for binary mode subprocess.
        
        Returns:
            Dict[str, Any]: Keyword arguments for subprocess.Popen.
        """
        env = self.create_env(restricted=self.restricted_env)

        popen_kwargs: Dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": env,
        }

        self._add_optional_popen_args(popen_kwargs)
        return popen_kwargs

    def _add_optional_popen_args(self, popen_kwargs: Dict[str, Any]) -> None:
        """Add optional arguments to Popen kwargs if they have values.
        
        Args:
            popen_kwargs: Dictionary of keyword arguments to modify.
        """
        if self.working_dir:
            popen_kwargs["cwd"] = self.working_dir

        if self.enable_shell:
            popen_kwargs["shell"] = True

    def _truncate_output(self, output: Union[str, bytes]) -> Union[str, bytes]:
        """Truncate output if it exceeds the maximum size.
        
        Args:
            output: The output to truncate.
            
        Returns:
            Union[str, bytes]: Truncated output.
        """
        if isinstance(output, str):
            if len(output) > self.max_output_size:
                return output[:self.max_output_size] + "... (truncated)"
        elif isinstance(output, bytes):
            if len(output) > self.max_output_size:
                return output[:self.max_output_size] + b"... (truncated)"
        return output

    def _execute_subprocess(self, command: List[str], popen_kwargs: Dict[str, Any],
                            timeout: Optional[int], is_text_mode: bool,
                            encoding: str = 'utf-8', errors: str = 'replace') -> Tuple[str, str, int]:
        """Execute the subprocess with the given parameters.
        
        Args:
            command: Command to execute as a list of strings.
            popen_kwargs: Keyword arguments for subprocess.Popen.
            timeout: Maximum time in seconds to wait for the process to complete.
            is_text_mode: Whether to run in text mode or binary mode.
            encoding: Character encoding to use for decoding (binary mode only).
            errors: How to handle encoding/decoding errors (binary mode only).
            
        Returns:
            Tuple[str, str, int]: stdout, stderr, and return code.
            
        Raises:
            TimeoutError: If the process exceeds the specified timeout.
        """
        process = None

        try:
            process = self._start_process(command, popen_kwargs)
            stdout, stderr = self._communicate_with_process(process, timeout)
            processed_stdout, processed_stderr, returncode = self._process_output(stdout, stderr, is_text_mode,
                                                                                  encoding, errors, process)

            # Log completion
            logger.info(f"Command completed with return code: {returncode}")

            return processed_stdout, processed_stderr, returncode
        except subprocess.TimeoutExpired:
            self._handle_timeout(process, command, timeout)
        except Exception as e:
            self._handle_execution_error(process, e)
        finally:
            self._cleanup_process(process)

    def _start_process(self, command: List[str], popen_kwargs: Dict[str, Any]) -> subprocess.Popen[Any]:
        """Start a subprocess with the given command and parameters.
        
        Args:
            command: Command to execute as a list of strings.
            popen_kwargs: Keyword arguments for subprocess.Popen.
            
        Returns:
            subprocess.Popen: The started process.
        """
        process = subprocess.Popen(command, **popen_kwargs)
        self._start_resource_monitoring(process)
        return process

    def _communicate_with_process(self, process: subprocess.Popen[Any],
                                  timeout: Optional[int]) -> Tuple[Union[str, bytes], Union[str, bytes]]:
        """Communicate with the process and get its output."""
        return process.communicate(timeout=timeout or self.timeout)

    def _handle_timeout(self, process: Optional[subprocess.Popen[Any]],
                        command: List[str], timeout: Optional[int]) -> NoReturn:
        """Handle a subprocess timeout.
            
        Raises:
            TimeoutError: Always raised to indicate the timeout.
        """
        self._terminate_process(process)
        logger.warning(f"Command timed out: {' '.join(command)}")
        raise TimeoutError(f"Command timed out after {timeout or self.timeout} seconds: {' '.join(command)}")

    def _handle_execution_error(self, process: Optional[subprocess.Popen[Any]], error: Exception, ) -> None:
        """Handle execution errors."""
        console.print(f"[red]Error in subprocess execution: {str(error)}[/red]")
        self._terminate_process(process)
        raise error  # Re-raise the original exception after cleanup

    def _process_output(self, stdout: Union[str, bytes], stderr: Union[str, bytes],  # type: ignore
                        is_text_mode: bool, encoding: str, errors: str,
                        process: subprocess.Popen[Any]) -> Tuple[str, str, int]:
        """Process and decode the subprocess output with truncation.

        Args:
            stdout: The standard output from the process.
            stderr: The standard error from the process.
            is_text_mode: Whether the output is in text mode.
            encoding: Character encoding to use for decoding.
            errors: How to handle encoding/decoding errors.
            process: The subprocess.Popen object.

        Returns:
            Tuple[str, str, int]: Processed stdout, stderr, and return code.
        """
        if is_text_mode:
            stdout_str = str(self._truncate_output(stdout))
            stderr_str = str(self._truncate_output(stderr))
        else:
            # Binary mode needs decoding
            stdout_bytes = self._truncate_output(stdout)
            stderr_bytes = self._truncate_output(stderr)
            # Handle proper type conversion
            stdout_str = (stdout_bytes.decode(encoding, errors=errors)
                          if isinstance(stdout_bytes, bytes) else str(stdout_bytes))
            stderr_str = (stderr_bytes.decode(encoding, errors=errors)
                          if isinstance(stderr_bytes, bytes) else str(stderr_bytes))

        return stdout_str, stderr_str, process.returncode
