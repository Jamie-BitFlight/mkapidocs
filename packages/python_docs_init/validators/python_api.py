"""Python API validator - checks API documentation coverage."""

import subprocess  # noqa: S404
import time
from pathlib import Path

from python_docs_init.validators.base import ValidationIssue, ValidationResult, ValidationStatus


class PythonAPIValidator:
    """Validator that checks Python API documentation coverage using interrogate."""

    name = "python_api"

    def __init__(self, min_coverage: float = 80.0) -> None:
        """Initialize Python API validator.

        Args:
            min_coverage: Minimum acceptable docstring coverage percentage.
        """
        self.min_coverage = min_coverage

    def validate(self, repo_path: Path) -> ValidationResult:
        """Run Python API documentation coverage checks.

        Args:
            repo_path: Path to repository root.

        Returns:
            ValidationResult with API coverage status.
        """
        start_time = time.time()

        # Find Python source directories
        source_paths = self._find_source_paths(repo_path)
        if not source_paths:
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.SKIPPED,
                message="No Python source directories found",
                execution_time=time.time() - start_time,
            )

        try:
            # S603, S607: interrogate is a trusted tool from our dependencies
            result = subprocess.run(  # noqa: S603
                ["interrogate", "-v", *[str(p) for p in source_paths]],  # noqa: S607
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            coverage, issues = self._parse_interrogate_output(result.stdout)

            if coverage >= self.min_coverage:
                status = ValidationStatus.SUCCESS
                message = f"API documentation coverage: {coverage:.1f}% (target: {self.min_coverage:.1f}%)"
            else:
                status = ValidationStatus.WARNING
                message = f"API documentation coverage below target: {coverage:.1f}% (target: {self.min_coverage:.1f}%)"

            return ValidationResult(
                validator_name=self.name,
                status=status,
                message=message,
                issues=issues,
                execution_time=time.time() - start_time,
                metadata={"coverage": coverage, "target": self.min_coverage},
            )

        except subprocess.TimeoutExpired:
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.ERROR,
                message="API documentation check timed out after 30 seconds",
                issues=[
                    ValidationIssue(
                        message="interrogate took too long - possible very large codebase",
                        severity=ValidationStatus.ERROR,
                    )
                ],
                execution_time=time.time() - start_time,
            )

        except FileNotFoundError:
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.ERROR,
                message="interrogate command not found - install validation dependencies with: uv sync --extra validation",
                issues=[
                    ValidationIssue(
                        message="interrogate is not installed in the current environment",
                        severity=ValidationStatus.ERROR,
                    )
                ],
                execution_time=time.time() - start_time,
            )

    def _find_source_paths(self, repo_path: Path) -> list[Path]:
        """Find Python source directories in repository.

        Args:
            repo_path: Path to repository root.

        Returns:
            List of paths to Python source directories.
        """
        candidate_paths = [repo_path / "src", repo_path / "packages"]

        # Add subdirectories of packages/ if it exists
        packages_dir = repo_path / "packages"
        if packages_dir.exists():
            candidate_paths.extend(packages_dir.glob("*"))

        python_paths = []
        for path in candidate_paths:
            if path.exists() and path.is_dir() and any(path.rglob("*.py")):
                python_paths.append(path)

        return python_paths

    def _parse_interrogate_output(self, stdout: str) -> tuple[float, list[ValidationIssue]]:
        """Parse interrogate output to extract coverage and issues.

        Args:
            stdout: Standard output from interrogate.

        Returns:
            Tuple of (coverage_percentage, list_of_issues).
        """
        import re

        coverage = 0.0
        issues = []

        # Extract overall coverage from output like "Overall coverage: 75.0%"
        coverage_match = re.search(r"Overall coverage:\s+([\d.]+)%", stdout)
        if coverage_match:
            coverage = float(coverage_match.group(1))

        # Extract missing docstring information
        for line in stdout.splitlines():
            if "missing docstring" in line.lower():
                issues.append(ValidationIssue(message=line.strip(), severity=ValidationStatus.WARNING))

        return coverage, issues
