"""Base types and protocols for documentation validation."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class ValidationStatus(Enum):
    """Status of a validation check."""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class ValidationIssue:
    """Individual validation issue or finding."""

    message: str
    severity: ValidationStatus
    file_path: Path | None = None
    line_number: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    validator_name: str
    status: ValidationStatus
    message: str
    issues: list[ValidationIssue] = field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if validation passed (no errors)."""
        return self.status in {ValidationStatus.SUCCESS, ValidationStatus.WARNING, ValidationStatus.SKIPPED}

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for issue in self.issues if issue.severity == ValidationStatus.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for issue in self.issues if issue.severity == ValidationStatus.WARNING)


class Validator(Protocol):
    """Protocol for documentation validators."""

    name: str

    def validate(self, repo_path: Path) -> ValidationResult:
        """Run validation checks.

        Args:
            repo_path: Path to repository root.

        Returns:
            ValidationResult with findings.
        """
        ...
