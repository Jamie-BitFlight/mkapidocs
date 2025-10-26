"""Documentation validation orchestration."""

from pathlib import Path

from python_docs_init.reporters.console import ConsoleReporter
from python_docs_init.validators.base import ValidationResult
from python_docs_init.validators.build import BuildValidator
from python_docs_init.validators.python_api import PythonAPIValidator


def validate_documentation(repo_path: Path, min_api_coverage: float = 80.0) -> list[ValidationResult]:
    """Validate documentation for a repository.

    Args:
        repo_path: Path to repository root.
        min_api_coverage: Minimum acceptable API documentation coverage percentage.

    Returns:
        List of validation results.
    """
    validators = [BuildValidator(), PythonAPIValidator(min_coverage=min_api_coverage)]

    results = []
    for validator in validators:
        result = validator.validate(repo_path)
        results.append(result)

    return results


def run_validation_with_report(repo_path: Path, min_api_coverage: float = 80.0) -> bool:
    """Run validation and report results to console.

    Args:
        repo_path: Path to repository root.
        min_api_coverage: Minimum acceptable API documentation coverage percentage.

    Returns:
        True if all validations passed (no errors), False otherwise.
    """
    results = validate_documentation(repo_path, min_api_coverage)

    reporter = ConsoleReporter()
    reporter.report(results)

    # Return success if no errors (warnings are acceptable)
    return all(result.success for result in results)
