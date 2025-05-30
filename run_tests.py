#!/usr/bin/env python3
"""
Run all tests for the FastAPI JWT Auth application
"""
import subprocess
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """Run pytest with appropriate settings"""
    cmd = [
        "pytest",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--color=yes",  # Colored output
        "-p", "no:warnings",  # Disable warnings
        "tests/"  # Test directory
    ]
    
    # Run with coverage if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--coverage":
        cmd.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html"
        ])
    
    # Run specific test file if provided
    if len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
        cmd[-1] = sys.argv[1]
    
    print("Running tests...")
    print(" ".join(cmd))
    
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())