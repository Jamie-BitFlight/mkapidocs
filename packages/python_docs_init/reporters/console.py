"""Rich console reporter for validation results."""

from python_docs_init.validators.base import ValidationResult, ValidationStatus
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class ConsoleReporter:
    """Rich console reporter for validation results."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize console reporter.

        Args:
            console: Rich Console instance. Creates new one if None.
        """
        self.console = console or Console()

    def report(self, results: list[ValidationResult]) -> None:
        """Report validation results to console.

        Args:
            results: List of validation results to report.
        """
        if not results:
            self.console.print("[yellow]No validation results to report[/yellow]")
            return

        # Create summary table
        table = Table(title="Validation Summary", show_header=True, header_style="bold cyan")
        table.add_column("Validator", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Message")
        table.add_column("Time", justify="right")

        for result in results:
            status_str = self._format_status(result.status)
            time_str = f"{result.execution_time:.2f}s"
            table.add_row(result.validator_name, status_str, result.message, time_str)

        self.console.print(table)
        self.console.print()

        # Display detailed issues for failed validators
        for result in results:
            if result.issues:
                self._report_issues(result)

        # Display overall summary
        self._report_overall_summary(results)

    def _format_status(self, status: ValidationStatus) -> str:
        """Format validation status with color.

        Args:
            status: Validation status.

        Returns:
            Formatted status string with Rich markup.
        """
        match status:
            case ValidationStatus.SUCCESS:
                return "[bold green]✓ PASS[/bold green]"
            case ValidationStatus.WARNING:
                return "[bold yellow]⚠ WARN[/bold yellow]"
            case ValidationStatus.ERROR:
                return "[bold red]✗ FAIL[/bold red]"
            case ValidationStatus.SKIPPED:
                return "[dim]○ SKIP[/dim]"

    def _report_issues(self, result: ValidationResult) -> None:
        """Report detailed issues for a validation result.

        Args:
            result: Validation result with issues.
        """
        title = f"{result.validator_name} - {len(result.issues)} Issue(s)"
        border_style = self._get_border_style(result.status)

        issue_text = []
        for issue in result.issues:
            severity_icon = "✗" if issue.severity == ValidationStatus.ERROR else "⚠"
            severity_color = "red" if issue.severity == ValidationStatus.ERROR else "yellow"

            location = ""
            if issue.file_path:
                location = f" ({issue.file_path}"
                if issue.line_number:
                    location += f":{issue.line_number}"
                location += ")"

            issue_text.append(f"[{severity_color}]{severity_icon}[/{severity_color}] {issue.message}{location}")

        self.console.print(Panel("\n".join(issue_text), title=title, border_style=border_style, padding=(1, 2)))
        self.console.print()

    def _get_border_style(self, status: ValidationStatus) -> str:
        """Get border style for panel based on status.

        Args:
            status: Validation status.

        Returns:
            Rich style string.
        """
        match status:
            case ValidationStatus.SUCCESS:
                return "green"
            case ValidationStatus.WARNING:
                return "yellow"
            case ValidationStatus.ERROR:
                return "red"
            case ValidationStatus.SKIPPED:
                return "dim"

    def _report_overall_summary(self, results: list[ValidationResult]) -> None:
        """Report overall validation summary.

        Args:
            results: All validation results.
        """
        passed = sum(1 for r in results if r.status == ValidationStatus.SUCCESS)
        warnings = sum(1 for r in results if r.status == ValidationStatus.WARNING)
        failed = sum(1 for r in results if r.status == ValidationStatus.ERROR)
        skipped = sum(1 for r in results if r.status == ValidationStatus.SKIPPED)

        total_time = sum(r.execution_time for r in results)

        summary_parts = []
        if passed:
            summary_parts.append(f"[green]{passed} passed[/green]")
        if warnings:
            summary_parts.append(f"[yellow]{warnings} warnings[/yellow]")
        if failed:
            summary_parts.append(f"[red]{failed} failed[/red]")
        if skipped:
            summary_parts.append(f"[dim]{skipped} skipped[/dim]")

        summary_text = f"{' | '.join(summary_parts)} ({total_time:.2f}s total)"

        if failed > 0:
            style = "red"
            title = "Validation Failed"
        elif warnings > 0:
            style = "yellow"
            title = "Validation Passed with Warnings"
        else:
            style = "green"
            title = "All Validations Passed"

        self.console.print(Panel(summary_text, title=title, border_style=style, padding=(1, 2)))
