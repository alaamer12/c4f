#!/usr/bin/env python
"""
Test script for SSL workaround.

This script tests the SSL workaround by making an API call to Hugging Face
and handling any SSL renegotiation errors that occur.

Usage:
    python scripts/test_ssl_workaround.py
"""

import sys
import os
import logging
from pathlib import Path

# Add the parent directory to the path so we can import c4f
sys.path.insert(0, str(Path(__file__).parent.parent))

from c4f.ssl_utils import with_ssl_workaround
from c4f.utils import client, console
import g4f

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@with_ssl_workaround
def test_huggingface_api():
    """Test function that makes an API call to Hugging Face."""
    console.print("[bold blue]Testing API call to Hugging Face with SSL workaround...[/bold blue]")
    
    try:
        # Make the API call
        response = client.chat.completions.create(
            model=g4f.models.gpt_4o_mini,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": "Generate a simple git commit message for a bug fix."
                }
            ]
        )
        
        # Process the response
        if response and response.choices:
            message = response.choices[0].message.content
            console.print(f"[bold green]Success! Received response:[/bold green]")
            console.print(f"[green]{message}[/green]")
            return True
        else:
            console.print("[bold red]Error: Received empty response[/bold red]")
            return False
            
    except Exception as e:
        console.print(f"[bold red]Error making API call:[/bold red] {e}")
        
        # Check if it's an SSL error
        if "SSL" in str(e) and "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(e):
            console.print(
                "[yellow]This is the SSL renegotiation error we're trying to fix. "
                "The workaround was applied but didn't resolve the issue. "
                "This might be due to server-side configuration.[/yellow]"
            )
        
        return False

def test_without_workaround():
    """Test function that makes an API call without the SSL workaround."""
    console.print("[bold blue]Testing API call without SSL workaround...[/bold blue]")
    
    try:
        # Make the API call
        response = client.chat.completions.create(
            model=g4f.models.gpt_4o_mini,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": "Generate a simple git commit message for a bug fix."
                }
            ]
        )
        
        # Process the response
        if response and response.choices:
            message = response.choices[0].message.content
            console.print(f"[bold green]Success! Received response:[/bold green]")
            console.print(f"[green]{message}[/green]")
            return True
        else:
            console.print("[bold red]Error: Received empty response[/bold red]")
            return False
            
    except Exception as e:
        console.print(f"[bold red]Error making API call:[/bold red] {e}")
        
        # Check if it's an SSL error
        if "SSL" in str(e) and "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(e):
            console.print(
                "[yellow]This is the SSL renegotiation error we're trying to fix. "
                "Try running the test with the workaround to see if it helps.[/yellow]"
            )
        
        return False

def main():
    """Main function."""
    console.print("[bold]===== SSL Workaround Test =====\n[/bold]")
    
    # Print SSL information
    import ssl
    console.print(f"[bold]OpenSSL Version:[/bold] {ssl.OPENSSL_VERSION}")
    console.print(f"[bold]Default SSL Context:[/bold] {ssl.create_default_context()}\n")
    
    # Test without workaround
    console.print("[bold]Test #1: Without SSL Workaround[/bold]")
    success_without = test_without_workaround()
    
    console.print("\n[bold]Test #2: With SSL Workaround[/bold]")
    success_with = test_huggingface_api()
    
    # Print summary
    console.print("\n[bold]===== Test Summary =====\n[/bold]")
    console.print(f"Without workaround: {'[green]Success[/green]' if success_without else '[red]Failed[/red]'}")
    console.print(f"With workaround: {'[green]Success[/green]' if success_with else '[red]Failed[/red]'}")
    
    if success_with and not success_without:
        console.print("\n[bold green]The SSL workaround is working correctly![/bold green]")
    elif success_with and success_without:
        console.print("\n[bold yellow]Both tests succeeded. The SSL error might not be occurring in your environment.[/bold yellow]")
    elif not success_with and not success_without:
        console.print("\n[bold red]Both tests failed. The SSL workaround might not be effective for this specific issue.[/bold red]")
    
    return 0 if success_with else 1

if __name__ == "__main__":
    sys.exit(main())