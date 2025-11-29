#!/usr/bin/env -S uv --quiet run --active --script
# /// script
# dependencies = [
#   "pytest>=8.4.2",
#   "pytest-cov>=7.0.0",
#   "pytest-mock>=3.14.0",
#   # mkapidocs runtime deps (needed for test imports)
#   "typer>=0.19.2",
#   "jinja2>=3.1.6",
#   "pyyaml>=6.0",
#   "tomli-w>=1.2.0",
#   "python-dotenv>=1.1.1",
#   "pydantic>=2.12.2",
#   "rich>=13.9.4",
#   "httpx>=0.28.1",
#   "types-pyyaml>=6.0",
# ]
# ///
"""Test runner for mkapidocs test suite.

This PEP 723 standalone script runs the pytest test suite with all dependencies
declared inline. No installation required - just execute directly.

Usage:
    ./run-pytest.py              # Run all tests
    ./run-pytest.py -xvs         # Verbose mode with stop on first failure
    ./run-pytest.py tests/test_feature_detection.py  # Run specific test file
    ./run-pytest.py --cov        # Run with coverage report
"""

import sys

import pytest


def main() -> int:
    """Run pytest with all provided arguments.

    Uses pytest.main() for direct invocation instead of subprocess to avoid
    process overhead and naming conflicts with pytest module resolution.

    Returns:
        Exit code from pytest execution (0 for success, non-zero for failures)
    """
    return pytest.main(args=sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
