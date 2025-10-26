"""Build validator - checks if documentation builds without errors."""

import subprocess  # noqa: S404
import time
from pathlib import Path

from python_docs_init.validators.base import ValidationIssue, ValidationResult, ValidationStatus


class BuildValidator:
    """Validator that runs mkdocs build --strict to check for build errors."""

    name = "build"

    def validate(self, repo_path: Path) -> ValidationResult:
        """Run mkdocs build --strict validation.

        Args:
            repo_path: Path to repository root.

        Returns:
            ValidationResult with build status.
        """
        start_time = time.time()
        mkdocs_config = repo_path / "mkdocs.yml"

        if not mkdocs_config.exists():
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.SKIPPED,
                message="mkdocs.yml not found - documentation not set up",
                execution_time=time.time() - start_time,
            )

        try:
            # S607: mkdocs is a trusted tool from our dependencies
            result = subprocess.run(
                ["mkdocs", "build", "--strict", "--clean"],  # noqa: S607
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.SUCCESS,
                message="Documentation builds successfully with no errors",
                execution_time=time.time() - start_time,
                metadata={"build_time": self._extract_build_time(result.stdout)},
            )

        except subprocess.TimeoutExpired:
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.ERROR,
                message="Documentation build timed out after 60 seconds",
                issues=[
                    ValidationIssue(
                        message="Build took too long - possible infinite loop or very large documentation",
                        severity=ValidationStatus.ERROR,
                    )
                ],
                execution_time=time.time() - start_time,
            )

        except subprocess.CalledProcessError as e:
            issues = self._parse_build_errors(e.stderr)
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.ERROR,
                message=f"Documentation build failed with {len(issues)} error(s)",
                issues=issues,
                execution_time=time.time() - start_time,
                metadata={"stderr": e.stderr, "returncode": e.returncode},
            )

        except FileNotFoundError:
            return ValidationResult(
                validator_name=self.name,
                status=ValidationStatus.ERROR,
                message="mkdocs command not found - install documentation dependencies with: uv sync --extra docs",
                issues=[
                    ValidationIssue(
                        message="mkdocs is not installed in the current environment", severity=ValidationStatus.ERROR
                    )
                ],
                execution_time=time.time() - start_time,
            )

    def _parse_build_errors(self, stderr: str) -> list[ValidationIssue]:
        """Parse mkdocs error output into structured issues.

        Args:
            stderr: Standard error output from mkdocs build.

        Returns:
            List of ValidationIssue objects.
        """
        issues = []
        for line in stderr.splitlines():
            if "ERROR" in line or "CRITICAL" in line:
                issues.append(ValidationIssue(message=line.strip(), severity=ValidationStatus.ERROR))
            elif "WARNING" in line:
                issues.append(ValidationIssue(message=line.strip(), severity=ValidationStatus.WARNING))
        return issues

    def _extract_build_time(self, stdout: str) -> float | None:
        """Extract build time from mkdocs output.

        Args:
            stdout: Standard output from mkdocs build.

        Returns:
            Build time in seconds, or None if not found.
        """
        import re

        match = re.search(r"Documentation built in ([\d.]+) seconds", stdout)
        return float(match.group(1)) if match else None
