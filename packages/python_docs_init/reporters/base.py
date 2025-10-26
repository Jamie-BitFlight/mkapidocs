"""Base types and protocols for validation reporters."""

from typing import Protocol

from python_docs_init.validators.base import ValidationResult


class Reporter(Protocol):
    """Protocol for validation result reporters."""

    def report(self, results: list[ValidationResult]) -> None:
        """Report validation results.

        Args:
            results: List of validation results to report.
        """
        ...
