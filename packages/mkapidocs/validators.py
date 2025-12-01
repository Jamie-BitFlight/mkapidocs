"""Validation logic for mkapidocs."""

from __future__ import annotations

import os
import platform
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import ClassVar, TypedDict, cast

import httpx
import tomlkit
from rich import box
from rich.console import Console
from rich.measure import Measurement
from rich.table import Table

# PyprojectConfig imported by detect_c_code and detect_typer_dependency in generator.py
# which are called from check_c_code and check_typer_dependency methods

# Initialize Rich console for local output
console = Console()


@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        check_name: Name of the validation check
        passed: Whether the check passed
        message: Status message or error details
        value: Optional value (e.g., version string)
        required: Whether this check is required for operation
    """

    check_name: str
    passed: bool
    message: str
    value: str | None = None
    required: bool = True


class GitHubAsset(TypedDict):
    """GitHub release asset structure."""

    name: str
    browser_download_url: str


class GitHubRelease(TypedDict):
    """GitHub release API response structure."""

    assets: list[GitHubAsset]


class DoxygenInstaller:
    """Handles automatic Doxygen installation from GitHub releases."""

    GITHUB_API_URL: ClassVar[str] = "https://api.github.com/repos/doxygen/doxygen/releases/latest"
    CACHE_DIR: ClassVar[Path] = Path.home() / ".cache" / "doxygen-binaries"
    INSTALL_DIR: ClassVar[Path] = Path.home() / ".local" / "bin"

    @classmethod
    def is_installed(cls) -> tuple[bool, str | None]:
        """Check if Doxygen is installed and get version.

        Returns:
            Tuple of (is_installed, version_string)
        """
        doxygen_path = which("doxygen")
        if not doxygen_path:
            return False, None

        try:
            result = subprocess.run([doxygen_path, "--version"], capture_output=True, text=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False, None
        else:
            version = result.stdout.strip()
            return True, version

    @classmethod
    def get_platform_asset_name(cls) -> str | None:
        """Determine correct Doxygen asset name for current platform.

        Returns:
            Asset name pattern to match, or None if platform not supported
        """
        system = platform.system().lower()
        machine = platform.machine().lower()

        match system:
            case "linux":
                if "x86_64" in machine or "amd64" in machine:
                    return "doxygen-*.linux.bin.tar.gz"
                return None
            case "windows":
                if "x86_64" in machine or "amd64" in machine:
                    return "doxygen-*-setup.exe"
                return None
            case "darwin":
                # macOS requires Homebrew, can't auto-install DMG
                return None
            case _:
                return None

    @classmethod
    def download_and_install(cls) -> tuple[bool, str]:
        """Download and install Doxygen from GitHub releases.

        Returns:
            Tuple of (success, message)
        """
        import fnmatch

        asset_pattern = cls.get_platform_asset_name()
        if asset_pattern is None:
            system = platform.system()
            if system == "Darwin":
                return False, "macOS detected: Please install Doxygen via Homebrew: brew install doxygen"
            return False, f"Unsupported platform: {system} {platform.machine()}"

        try:
            # Fetch latest release info
            console.print("[blue]Fetching Doxygen release information...[/blue]")
            with httpx.Client(timeout=30.0) as client:
                response = client.get(cls.GITHUB_API_URL)
                _ = response.raise_for_status()
                release_data = cast(GitHubRelease, response.json())

            # Find matching asset
            asset: GitHubAsset | None = None
            for asset_item in release_data.get("assets", []):
                if fnmatch.fnmatch(asset_item["name"], asset_pattern):
                    asset = asset_item
                    break

            if not asset:
                return False, f"No matching asset found for pattern: {asset_pattern}"

            asset_name: str = asset["name"]
            asset_url: str = asset["browser_download_url"]

            # Extract SHA256 from API response (GitHub stores it in the API metadata)
            # Note: GitHub doesn't provide checksums in the public API for releases
            # We'll download but warn about verification
            console.print(f"[blue]Downloading {asset_name}...[/blue]")

            cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            download_path: Path = cls.CACHE_DIR / asset_name

            # Download file (follow redirects)
            with (
                httpx.Client(timeout=300.0, follow_redirects=True) as client,
                client.stream("GET", asset_url) as dl_response,
            ):
                _ = dl_response.raise_for_status()
                with download_path.open("wb") as f:
                    for chunk in dl_response.iter_bytes(chunk_size=8192):
                        _ = f.write(chunk)

            console.print(f"[green]Downloaded to {download_path}[/green]")

            # Extract and install (Linux only, Windows requires manual setup)
            if platform.system().lower() == "linux":
                return cls._install_linux_binary(download_path)
            else:
                return False, "Downloaded, but automatic installation only supported on Linux"

        except httpx.HTTPError as e:
            return False, f"HTTP error downloading Doxygen: {e}"
        except Exception as e:
            return False, f"Failed to install Doxygen: {e}"

    @classmethod
    def _install_linux_binary(cls, tarball_path: Path) -> tuple[bool, str]:
        """Extract and install Linux Doxygen binary.

        Args:
            tarball_path: Path to downloaded tar.gz file

        Returns:
            Tuple of (success, message)
        """
        try:
            # Extract tarball
            extract_dir = cls.CACHE_DIR / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            console.print(f"[blue]Extracting {tarball_path.name}...[/blue]")
            with tarfile.open(tarball_path, "r:gz") as tar:
                # S202: Trusted source (GitHub release), ignoring Zip Slip warning
                tar.extractall(extract_dir)

            # Find doxygen binary in extracted files
            doxygen_bin = None
            for root, _dirs, files in os.walk(extract_dir):
                if "doxygen" in files:
                    doxygen_bin = Path(root) / "doxygen"
                    break

            if not doxygen_bin or not doxygen_bin.exists():
                return False, "Could not find doxygen binary in extracted archive"

            # Copy to install directory
            cls.INSTALL_DIR.mkdir(parents=True, exist_ok=True)
            install_path = cls.INSTALL_DIR / "doxygen"

            import shutil

            _ = shutil.copy2(doxygen_bin, install_path)
            install_path.chmod(0o755)

            # Add to PATH for current process
            if str(cls.INSTALL_DIR) not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{cls.INSTALL_DIR}:{os.environ.get('PATH', '')}"

            console.print(f"[green]Installed Doxygen to {install_path}[/green]")
        except Exception as e:
            return False, f"Failed to extract/install: {e}"
        else:
            return True, f"Doxygen installed to {install_path}"


class SystemValidator:
    """Validates system-level requirements."""

    @staticmethod
    def _check_command(
        name: str, binary: str, version_arg: str = "--version", strip_prefix: str = "", install_msg: str = "Not found"
    ) -> ValidationResult:
        """Generic command validation helper.

        Args:
            name: Display name of the check.
            binary: Binary name to look for.
            version_arg: Argument to get version.
            strip_prefix: Prefix to strip from version output.
            install_msg: Message to show if not found.

        Returns:
            ValidationResult.
        """
        path = which(binary)
        if not path:
            return ValidationResult(check_name=name, passed=False, message=install_msg, required=True)

        try:
            result = subprocess.run([path, version_arg], capture_output=True, text=True, check=True, timeout=5)
            version = result.stdout.strip()
            if strip_prefix and version.startswith(strip_prefix):
                version = version[len(strip_prefix) :]
            return ValidationResult(check_name=name, passed=True, message="Installed", value=version, required=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ValidationResult(
                check_name=name, passed=False, message="Found but version check failed", required=True
            )

    @staticmethod
    def check_git() -> ValidationResult:
        """Check if git is installed.

        Returns:
            Validation result.
        """
        return SystemValidator._check_command(
            name="Git", binary="git", strip_prefix="git version ", install_msg="Not found - install git"
        )

    @staticmethod
    def check_uv() -> ValidationResult:
        """Check if uv/uvx is installed.

        Returns:
            Validation result.
        """
        return SystemValidator._check_command(
            name="uv/uvx",
            binary="uvx",
            strip_prefix="uvx ",
            install_msg="Not found - install uv from https://docs.astral.sh/uv/",
        )

    @staticmethod
    def check_doxygen() -> ValidationResult:
        """Check if Doxygen is installed.

        Returns:
            Validation result.
        """
        is_installed, version = DoxygenInstaller.is_installed()

        if is_installed:
            return ValidationResult(
                check_name="Doxygen", passed=True, message="Installed", value=version, required=False
            )

        return ValidationResult(
            check_name="Doxygen",
            passed=False,
            message="Not found (can auto-install if C/C++ code detected)",
            required=False,
        )


class ProjectValidator:
    """Validates target project requirements."""

    repo_path: Path

    def __init__(self, repo_path: Path):
        """Initialize validator with target repository path.

        Args:
            repo_path: Path to target repository
        """
        self.repo_path = repo_path

    def check_path_exists(self) -> ValidationResult:
        """Check if repository path exists and is a directory.

        Returns:
            Validation result
        """
        if not self.repo_path.exists():
            return ValidationResult(
                check_name="Path exists", passed=False, message=f"Path does not exist: {self.repo_path}", required=True
            )

        if not self.repo_path.is_dir():
            return ValidationResult(
                check_name="Path exists",
                passed=False,
                message=f"Path is not a directory: {self.repo_path}",
                required=True,
            )

        return ValidationResult(check_name="Path exists", passed=True, message="Valid directory", required=True)

    def check_git_repository(self) -> ValidationResult:
        """Check if path is a git repository.

        Returns:
            Validation result
        """
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            return ValidationResult(
                check_name="Git repository",
                passed=False,
                message="Not a git repository (no .git directory)",
                required=True,
            )

        return ValidationResult(check_name="Git repository", passed=True, message="Valid git repository", required=True)

    def check_pyproject_toml(self) -> ValidationResult:
        """Check if pyproject.toml exists.

        Returns:
            Validation result
        """
        pyproject_path = self.repo_path / "pyproject.toml"
        if not pyproject_path.exists():
            return ValidationResult(check_name="pyproject.toml", passed=False, message="File not found", required=True)

        # Try to parse it
        try:
            with open(pyproject_path, encoding="utf-8") as f:
                _ = tomlkit.load(f)
            return ValidationResult(check_name="pyproject.toml", passed=True, message="Valid TOML file", required=True)
        except Exception as e:
            return ValidationResult(
                check_name="pyproject.toml", passed=False, message=f"Invalid TOML: {e}", required=True
            )

    def check_c_code(self) -> ValidationResult:
        """Check if repository contains C/C++ source code.

        Returns:
            Validation result
        """
        # Note: We need to import these here to avoid circular imports
        # or we need to refactor generator.py to be importable
        # For now, we'll assume the functions are available or move them to a common place
        # But wait, detect_c_code is in generator.py which we haven't created yet.
        # This creates a circular dependency if we're not careful.
        # Ideally, detection logic should be in a separate module or here.
        # Let's import from generator if possible, but generator imports models.
        # So models -> validators -> generator -> models is a cycle.
        # Solution: Move detection logic to a separate module or keep it in generator
        # and import inside the method.
        from mkapidocs.generator import detect_c_code, read_pyproject

        try:
            pyproject = read_pyproject(self.repo_path)
        except FileNotFoundError:
            pyproject = None

        c_source_dirs = detect_c_code(self.repo_path, pyproject=pyproject)

        if c_source_dirs:
            # Get relative paths for display
            relative_dirs = [str(d.relative_to(self.repo_path)) for d in c_source_dirs]
            dirs_display = ", ".join(relative_dirs)
            return ValidationResult(
                check_name="C/C++ code",
                passed=True,
                message=f"Found in: {dirs_display}",
                value="Doxygen required",
                required=False,
            )

        return ValidationResult(
            check_name="C/C++ code", passed=True, message="Not found", value="Doxygen not needed", required=False
        )

    def check_typer_dependency(self) -> ValidationResult:
        """Check if project depends on Typer.

        Returns:
            Validation result
        """
        from mkapidocs.generator import detect_typer_dependency, read_pyproject

        try:
            pyproject = read_pyproject(self.repo_path)
            has_typer = detect_typer_dependency(pyproject)

            if has_typer:
                return ValidationResult(
                    check_name="Typer dependency", passed=True, message="Found in dependencies", required=False
                )

            return ValidationResult(check_name="Typer dependency", passed=True, message="Not found", required=False)
        except Exception as e:
            return ValidationResult(
                check_name="Typer dependency", passed=False, message=f"Could not check: {e}", required=False
            )

    def check_mkdocs_yml(self) -> ValidationResult:
        """Check if mkdocs.yml exists (for build/serve commands).

        Returns:
            Validation result
        """
        mkdocs_path = self.repo_path / "mkdocs.yml"
        if not mkdocs_path.exists():
            return ValidationResult(
                check_name="mkdocs.yml", passed=False, message="File not found - run setup command first", required=True
            )

        return ValidationResult(check_name="mkdocs.yml", passed=True, message="Found", required=True)


def _get_table_width(table: Table) -> int:
    """Get the natural width of a table using a temporary wide console.

    Args:
        table: The Rich table to measure

    Returns:
        The width in characters needed to display the table
    """
    temp_console = Console(width=9999)
    measurement = Measurement.get(temp_console, temp_console.options, table)
    return int(measurement.maximum)


def display_validation_results(results: list[ValidationResult], title: str = "Environment Validation") -> None:
    """Display validation results in a Rich formatted table.

    Args:
        results: List of validation results
        title: Table title
    """
    table = Table(title=f":mag: {title}", box=box.MINIMAL_DOUBLE_HEAD, title_style="bold cyan", show_header=True)

    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Details", style="dim")
    table.add_column("Version/Info", style="magenta")

    for result in results:
        # Determine status icon using emoji tokens
        if result.passed:
            status = ":white_check_mark:"
            status_style = "green"
        else:
            status = ":x:" if result.required else ":warning:"
            status_style = "red" if result.required else "yellow"

        # Format details with color
        details = f"[{status_style}]{result.message}[/{status_style}]"

        # Add row
        table.add_row(result.check_name, status, details, result.value or "")

    # Set table width to natural size
    table_width = _get_table_width(table)
    table.width = table_width

    # Display table
    console.print(table, crop=False, overflow="ignore", no_wrap=True, soft_wrap=True)


def validate_environment(
    repo_path: Path, check_mkdocs: bool = False, auto_install_doxygen: bool = False
) -> tuple[bool, list[ValidationResult]]:
    """Validate system and project requirements.

    Args:
        repo_path: Path to target repository
        check_mkdocs: Whether to check for mkdocs.yml
        auto_install_doxygen: Whether to auto-install Doxygen if needed

    Returns:
        Tuple of (all_required_passed, list of results)
    """
    results: list[ValidationResult] = []

    # System checks
    sys_validator = SystemValidator()
    results.append(sys_validator.check_git())
    results.append(sys_validator.check_uv())
    doxygen_result = sys_validator.check_doxygen()
    results.append(doxygen_result)

    # Project checks
    proj_validator = ProjectValidator(repo_path)
    path_result = proj_validator.check_path_exists()
    results.append(path_result)

    # Only continue with further checks if path exists
    if path_result.passed:
        results.append(proj_validator.check_git_repository())
        results.append(proj_validator.check_pyproject_toml())
        c_code_result = proj_validator.check_c_code()
        results.append(c_code_result)
        results.append(proj_validator.check_typer_dependency())

        if check_mkdocs:
            results.append(proj_validator.check_mkdocs_yml())

        # Auto-install Doxygen if needed
        if (
            auto_install_doxygen
            and c_code_result.passed
            and c_code_result.value
            and "required" in c_code_result.value.lower()
            and not doxygen_result.passed
        ):
            console.print("\n[yellow]C/C++ code detected but Doxygen not installed.[/yellow]")
            console.print("[blue]Attempting automatic Doxygen installation...[/blue]\n")

            success, message = DoxygenInstaller.download_and_install()

            if success:
                # Re-check Doxygen
                doxygen_result = sys_validator.check_doxygen()
                # Update the result in the list
                for i, r in enumerate(results):
                    if r.check_name == "Doxygen":
                        results[i] = doxygen_result
                        break
                console.print(f"\n[green]:white_check_mark: {message}[/green]\n")
            else:
                console.print(f"\n[yellow]:warning: {message}[/yellow]\n")
                console.print("[yellow]Documentation will be generated without C/C++ API reference.[/yellow]\n")

    # Check if all required checks passed
    all_required_passed = all(r.passed or not r.required for r in results)

    return all_required_passed, results
