"""SSL utilities for handling SSL-related issues in c4f.

This module provides utilities for handling SSL-related issues, particularly
the legacy SSL renegotiation error that can occur when connecting to APIs.

The main issue addressed is the "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" error
that occurs when connecting to certain APIs that still use legacy SSL renegotiation,
which is disabled by default in recent OpenSSL versions for security reasons.

Example:
    To apply the SSL workaround to a function that makes API calls:

    ```python
    from c4f.ssl_utils import with_ssl_workaround

    @with_ssl_workaround
    def my_api_function():
        # Make API calls here
        response = requests.get('https://api.example.com')
        return response.json()
    ```

Note:
    This workaround should be considered temporary. The proper solution is for
    the API provider to update their server configuration to not rely on legacy
    SSL renegotiation.
"""

import os
import sys
import tempfile
import logging
import functools
import ssl
from pathlib import Path
from typing import Optional, Dict, Any, Callable, TypeVar, cast, Union

T = TypeVar('T')

# Configure logging
logger = logging.getLogger(__name__)

# Check if we're running on a system with OpenSSL
HAS_OPENSSL = hasattr(ssl, 'OPENSSL_VERSION')
OPENSSL_VERSION = ssl.OPENSSL_VERSION if HAS_OPENSSL else "Unknown"

# Log OpenSSL version at module import time
logger.debug(f"SSL Module Info - OpenSSL: {HAS_OPENSSL}, Version: {OPENSSL_VERSION}")

def is_ssl_renegotiation_error(error: Exception) -> bool:
    """Check if an exception is related to SSL renegotiation issues.
    
    Args:
        error: The exception to check
        
    Returns:
        bool: True if the error is related to SSL renegotiation, False otherwise
    """
    error_str = str(error).lower()
    return (
        "ssl" in error_str and 
        "unsafe_legacy_renegotiation_disabled" in error_str
    )

def create_ssl_config_file() -> str:
    """Create a temporary OpenSSL configuration file that enables legacy renegotiation.
    
    Returns:
        str: Path to the created configuration file
    """
    config_content = """
openssl_conf = openssl_init

[openssl_init]
ssl_conf = ssl_sect

[ssl_sect]
system_default = ssl_default_sect

[ssl_default_sect]
Options = UnsafeLegacyRenegotiation
"""
    
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix='.cnf', prefix='openssl_')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        logger.debug(f"Created SSL config file at {path}")
        return path
    except Exception as e:
        logger.error(f"Failed to create SSL config file: {e}")
        # Close the file descriptor if an error occurs
        try:
            os.close(fd)
        except:
            pass
        return ""

def with_ssl_workaround(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to apply SSL workaround for functions that make API calls.
    
    This decorator temporarily sets the OPENSSL_CONF environment variable to use
    a custom configuration that enables legacy SSL renegotiation, which can help
    resolve SSL errors when connecting to certain APIs.
    
    Args:
        func: The function to wrap
        
    Returns:
        Callable: The wrapped function with SSL workaround applied
    """
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Save the original environment variable if it exists
        original_openssl_conf = os.environ.get('OPENSSL_CONF')
        config_path = None
        
        try:
            # Create a temporary OpenSSL config file
            config_path = create_ssl_config_file()
            if config_path:
                # Set the environment variable to use our config
                os.environ['OPENSSL_CONF'] = config_path
                logger.debug(f"Applied SSL workaround with config at {config_path}")
            
            # Call the original function
            return func(*args, **kwargs)
        
        except Exception as e:
            # If it's an SSL error, log a helpful message
            if "SSL" in str(e) and "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(e):
                logger.error(
                    "SSL renegotiation error occurred. The SSL workaround was applied "
                    "but did not resolve the issue. This might be due to server-side "
                    "configuration or other SSL-related issues."
                )
            # Re-raise the exception
            raise
        
        finally:
            # Clean up: restore the original environment variable
            if original_openssl_conf:
                os.environ['OPENSSL_CONF'] = original_openssl_conf
            else:
                os.environ.pop('OPENSSL_CONF', None)
            
            # Remove the temporary config file
            if config_path and Path(config_path).exists():
                try:
                    os.remove(config_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary SSL config file: {e}")
    
    return cast(Callable[..., T], wrapper)