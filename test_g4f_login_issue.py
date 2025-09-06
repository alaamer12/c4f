#!/usr/bin/env python3
"""
Test script to reproduce the "Login to continue using" issue with g4f library.

This script demonstrates the login requirement issue that occurs when using
the g4f library to access free AI providers.
"""

import sys
import time
from pathlib import Path

# Add the c4f package to the path
sys.path.insert(0, str(Path(__file__).parent / "c4f"))

try:
    from g4f.client import Client
    import g4f
except ImportError:
    print("❌ g4f library not found. Install it with: pip install g4f")
    sys.exit(1)

def test_simple_g4f_request():
    """Test a simple g4f request to see the login issue."""
    print("🔍 Testing g4f library with different models...")
    print("=" * 60)
    
    client = Client()
    test_prompt = "Hello, can you help me write a git commit message?"
    
    # Test different models that might show the login issue
    models_to_test = [
        ("gpt-4o-mini", g4f.models.gpt_4o_mini),
        ("gpt-4o", g4f.models.gpt_4o),
        ("default", g4f.models.default),
        ("meta", g4f.models.meta),
    ]
    
    for model_name, model in models_to_test:
        print(f"\n🧪 Testing model: {model_name}")
        print("-" * 40)
        
        try:
            print(f"📤 Sending request to {model_name}...")
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": test_prompt}
                ],
                timeout=10  # Short timeout to see failures quickly
            )
            
            if response and response.choices:
                result = response.choices[0].message.content
                print(f"✅ SUCCESS: {result[:100]}...")
            else:
                print("❌ FAILED: No response received")
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ ERROR: {error_msg}")
            
            # Check for specific login-related errors
            if "login" in error_msg.lower():
                print("🔑 This is the LOGIN ISSUE you're experiencing!")
            elif "authentication" in error_msg.lower():
                print("🔐 Authentication required by provider")
            elif "rate limit" in error_msg.lower():
                print("⏱️ Rate limited by provider")
            
        print(f"⏳ Waiting 2 seconds before next test...")
        time.sleep(2)

def test_c4f_integration():
    """Test the actual c4f integration to see the issue in context."""
    print("\n" + "=" * 60)
    print("🔧 Testing c4f integration...")
    print("=" * 60)
    
    try:
        from c4f.config import Config
        from c4f.main import get_model_response
        import g4f
        
        # Create a test config similar to what c4f uses
        config = Config(
            model=g4f.models.gpt_4o_mini,
            fallback_timeout=5,
            thread_count=1  # Use single thread for clearer output
        )
        
        # Test prompt similar to what c4f generates
        test_prompt = """
        Generate a conventional commit message for these changes:
        M README.md
        A test_file.py
        
        Files changed: 2
        """
        
        # Test tool calls similar to c4f
        tool_calls = {
            "function": {
                "name": "generate_commit",
                "arguments": {
                    "files": "M README.md\nA test_file.py",
                    "style": "conventional",
                    "format": "inline",
                    "max_length": 72
                }
            },
            "type": "function"
        }
        
        print("📤 Testing c4f model response function...")
        result = get_model_response(test_prompt, tool_calls, config)
        
        if result:
            print(f"✅ SUCCESS: {result}")
        else:
            print("❌ FAILED: No response from c4f integration")
            
    except ImportError as e:
        print(f"❌ Cannot import c4f modules: {e}")
    except Exception as e:
        error_msg = str(e)
        print(f"❌ ERROR in c4f integration: {error_msg}")
        
        if "login" in error_msg.lower():
            print("🔑 Found the LOGIN ISSUE in c4f integration!")

def main():
    """Main test function."""
    print("🚀 G4F Login Issue Test Script")
    print("This script will help you see the 'Login to continue using' issue")
    print("=" * 60)
    
    # Test 1: Simple g4f requests
    test_simple_g4f_request()
    
    # Test 2: c4f integration
    test_c4f_integration()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    print("If you see 'Login to continue using' messages above,")
    print("that's the issue you're experiencing with c4f.")
    print("\n💡 SOLUTIONS:")
    print("1. Try: c4f --model MetaAI")
    print("2. Try: c4f --model default")
    print("3. Try: pip install --upgrade g4f")
    print("4. Try: c4f --timeout 30 --threads 1")
    print("=" * 60)

if __name__ == "__main__":
    main()
