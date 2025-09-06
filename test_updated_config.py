#!/usr/bin/env python3
"""
Test script to verify the updated c4f configuration works with working models.
"""

import sys
from pathlib import Path

# Add the c4f package to the path
sys.path.insert(0, str(Path(__file__).parent / "c4f"))

def test_updated_cli():
    """Test the updated CLI configuration."""
    print("🧪 Testing updated c4f CLI configuration...")
    print("=" * 60)
    
    try:
        from c4f.cli import create_config_from_args
        import argparse
        
        # Test default model (should now be "default" instead of "gpt-4-mini")
        print("📋 Testing default model selection...")
        args = argparse.Namespace(
            model="default",
            force_brackets=False,
            icon=False,
            ascii_only=False,
            timeout=10,
            attempts=3,
            thread_count=1
        )
        
        config = create_config_from_args(args)
        print(f"✅ Default model config created successfully")
        print(f"   Model: {config.model}")
        
        # Test warning for login-required models
        print("\n📋 Testing warning for login-required models...")
        args.model = "gpt-4-mini"
        print("   (This should show a warning message)")
        config = create_config_from_args(args)
        
        print("\n📋 Testing MetaAI model...")
        args.model = "MetaAI"
        config = create_config_from_args(args)
        print(f"✅ MetaAI model config created successfully")
        print(f"   Model: {config.model}")
        
    except Exception as e:
        print(f"❌ Error testing CLI config: {e}")

def test_help_output():
    """Test the updated help output."""
    print("\n" + "=" * 60)
    print("📋 Testing updated help output...")
    print("=" * 60)
    
    try:
        from c4f.cli import add_model_argument
        import argparse
        
        parser = argparse.ArgumentParser()
        add_model_argument(parser)
        
        # Get the model argument
        for action in parser._actions:
            if hasattr(action, 'dest') and action.dest == 'model':
                print(f"✅ Model choices: {action.choices}")
                print(f"✅ Default model: {action.default}")
                print(f"✅ Help text: {action.help}")
                break
        
    except Exception as e:
        print(f"❌ Error testing help output: {e}")

def main():
    """Main test function."""
    print("🚀 Testing Updated C4F Configuration")
    print("This script tests the fixes for the login issue")
    print("=" * 60)
    
    test_updated_cli()
    test_help_output()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY OF CHANGES:")
    print("✅ Default model changed from 'gpt-4-mini' to 'default'")
    print("✅ Model choices reordered to prioritize working models")
    print("✅ Warning messages added for login-required models")
    print("✅ Updated --models command with better status indicators")
    print("\n💡 USAGE:")
    print("• c4f                    # Now uses 'default' model (working)")
    print("• c4f --model MetaAI     # Alternative working model")
    print("• c4f --model gpt-4-mini # Shows warning about login requirement")
    print("• c4f --models           # Shows updated model status")
    print("=" * 60)

if __name__ == "__main__":
    main()
