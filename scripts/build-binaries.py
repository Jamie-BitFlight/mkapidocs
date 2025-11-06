#!/usr/bin/env -S uv --quiet run --active --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.19.2",
#   "pydantic>=2.0.0",
# ]
# ///
"""Binary build orchestrator for CMake-based projects.

This script reads build configuration from [tool.pypis_delivery_service] in pyproject.toml
and orchestrates the build process either on the host (via Docker Compose) or inside a
container (direct CMake execution).

Architecture:
    - Uses Pydantic models for configuration validation
    - Follows SOLID principles with abstract interfaces
    - Dependency injection for flexibility and testability
    - Generic and project-agnostic design

SOLID Principles Applied:
    S: Single Responsibility - Each class has one clear purpose
    O: Open/Closed - Extensible via interfaces without modification
    L: Liskov Substitution - Implementations are interchangeable
    I: Interface Segregation - Specific interfaces for each concern
    D: Dependency Inversion - Depends on abstractions, not concretions
"""

import subprocess  # noqa: S404 - subprocess required for build orchestration with validated inputs
import tomllib
from abc import ABC, abstractmethod
from pathlib import Path

import typer
from pydantic import BaseModel, Field, field_validator
from rich.console import Console

console = Console()
app = typer.Typer(help="Generic binary build orchestrator for CMake projects")

# ==============================================================================
# PYDANTIC MODELS - Configuration with validation
# ==============================================================================


class BuildConfig(BaseModel):
    """Build configuration from pyproject.toml [tool.pypis_delivery_service]."""

    source_dir: str = Field(..., description="Directory containing CMakeLists.txt")
    binary_names: list[str] = Field(..., description="List of binary names to build")
    architectures: list[str] = Field(..., description="Target architectures (e.g., x86_64, aarch64)")
    build_types: list[str] = Field(..., description="Build types (e.g., Release, Debug)")
    build_dir_template: str = Field(..., description="Build directory template with placeholders")
    compose_build_service: str = Field(..., description="Docker Compose service name")
    cmake_extra_init_args: list[str] = Field(..., description="Additional CMake arguments with placeholders")
    cmake_required_apt_packages: list[str] = Field(default_factory=list, description="Required apt packages")

    @field_validator("architectures")
    @classmethod
    def validate_architectures(cls, v: list[str]) -> list[str]:
        """Validate that architectures list is not empty.

        Returns:
            The validated list of architectures.
        """
        if not v:
            raise ValueError("At least one architecture must be specified")
        return v

    @field_validator("build_types")
    @classmethod
    def validate_build_types(cls, v: list[str]) -> list[str]:
        """Validate that build_types list is not empty.

        Returns:
            The validated list of build types.
        """
        if not v:
            raise ValueError("At least one build type must be specified")
        return v


class BuildOptions(BaseModel):
    """Command-line build options."""

    verbose: bool = Field(default=False, description="Enable verbose output")
    clean: bool = Field(default=False, description="Clean build directories before building")
    no_cache: bool = Field(default=False, description="Build Docker image without cache")
    dry_run: bool = Field(default=False, description="Check packages without installing")


class BuildTarget(BaseModel):
    """Single build target specification."""

    architecture: str
    build_type: str
    source_dir: Path
    build_dir: Path
    cmake_args: list[str]


# ==============================================================================
# INTERFACES - Abstract base classes following Interface Segregation Principle
# ==============================================================================


class IContainerDetector(ABC):
    """Interface for detecting container environment."""

    @abstractmethod
    def is_inside_container(self) -> bool:
        """Check if running inside a container.

        Returns:
            True if inside container, False if on host
        """
        pass


class IPackageManager(ABC):
    """Interface for system package management."""

    @abstractmethod
    def check_and_install(self, packages: list[str], dry_run: bool = False) -> None:
        """Check for required packages and install missing ones.

        Args:
            packages: List of package names to ensure are installed
            dry_run: If True, only check without installing
        """
        pass


class ICMakeBuilder(ABC):
    """Interface for CMake build execution."""

    @abstractmethod
    def build(self, target: BuildTarget, verbose: bool = False) -> None:
        """Execute CMake configuration and build for a target.

        Args:
            target: Build target specification
            verbose: Enable verbose build output
        """
        pass


class IContainerRunner(ABC):
    """Interface for running builds inside containers."""

    @abstractmethod
    def run_in_container(self, config: BuildConfig, options: BuildOptions) -> None:
        """Execute build inside Docker Compose container.

        Args:
            config: Build configuration
            options: Build options
        """
        pass


class IConfigLoader(ABC):
    """Interface for configuration loading."""

    @abstractmethod
    def load_config(self, pyproject_path: Path) -> BuildConfig:
        """Load and validate build configuration.

        Args:
            pyproject_path: Path to pyproject.toml

        Returns:
            Validated build configuration
        """
        pass


# ==============================================================================
# CONCRETE IMPLEMENTATIONS - Following Single Responsibility Principle
# ==============================================================================


class ContainerDetector(IContainerDetector):
    """Detect if running inside Docker/Podman container."""

    def is_inside_container(self) -> bool:
        """Check for container environment indicators.

        Returns:
            True if running inside a container, False otherwise.
        """
        # Check for /.dockerenv file (Docker)
        if Path("/.dockerenv").exists():
            return True

        # Check for DOCKER_CONTAINER environment variable
        import os

        if os.getenv("DOCKER_CONTAINER") == "true":
            return True

        # Check /proc/1/cgroup for container indicators
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            content = cgroup_path.read_text()
            if any(indicator in content for indicator in ["docker", "lxc", "kubepods"]):
                return True

        return False


class AptPackageManager(IPackageManager):
    """Manage apt packages inside Debian-based containers."""

    def check_and_install(self, packages: list[str], dry_run: bool = False) -> None:
        """Check and install missing apt packages."""
        if not packages:
            console.print("[blue]INFO:[/blue] No packages to check")
            return

        print("🔍 Checking required packages...")

        # Verify apt-get is available
        try:
            subprocess.run(["which", "apt-get"], check=True, capture_output=True)  # noqa: S607
        except subprocess.CalledProcessError as e:
            raise RuntimeError("apt-get not available - cannot install packages") from e

        # Check which packages are missing
        missing_packages = []
        for package in packages:
            result = subprocess.run(["dpkg", "-s", package], capture_output=True)  # noqa: S603,S607 - dpkg with validated package names from config
            if result.returncode != 0:
                missing_packages.append(package)

        if not missing_packages:
            print("✓ All required packages are installed")
            return

        if dry_run:
            print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
            print("   (would install in non-dry-run mode)")
            return

        print(f"📦 Installing missing packages: {', '.join(missing_packages)}")

        # Update package lists
        subprocess.run(["apt-get", "update", "-qq"], check=True)  # noqa: S607

        # Install missing packages
        install_cmd = ["apt-get", "install", "-y", "-qq", "--no-install-recommends", *missing_packages]
        subprocess.run(install_cmd, check=True)  # noqa: S603 - apt-get with validated package names from config

        print("✓ All required packages installed")


class CMakeBuilder(ICMakeBuilder):
    """Execute CMake configuration and build."""

    def build(self, target: BuildTarget, verbose: bool = False) -> None:
        """Run CMake configure and build for target."""
        print(f"\n{'=' * 70}")
        print(f"Building {target.architecture} ({target.build_type})")
        print(f"{'=' * 70}")

        # Create build directory
        target.build_dir.mkdir(parents=True, exist_ok=True)

        # CMake configuration
        self._configure(target, verbose)

        # CMake build
        self._compile(target, verbose)

        # List built binaries
        self._list_artifacts(target.build_dir)

    def _configure(self, target: BuildTarget, verbose: bool) -> None:
        """Run CMake configuration step."""
        print("⚙️  Configuring CMake...")
        print(f"   Source: {target.source_dir}")
        print(f"   Build:  {target.build_dir}")

        config_cmd = [
            "cmake",
            "-S",
            str(target.source_dir),
            "-B",
            str(target.build_dir),
            f"-DCMAKE_BUILD_TYPE={target.build_type}",
            *target.cmake_args,
        ]

        if verbose:
            config_cmd.append("-DCMAKE_VERBOSE_MAKEFILE=ON")

        print(f"   Command: {' '.join(config_cmd)}")
        subprocess.run(config_cmd, check=True)  # noqa: S603 - cmake with validated paths and build configuration
        print("✓ CMake configuration complete")

    def _compile(self, target: BuildTarget, verbose: bool) -> None:
        """Run CMake build step."""
        print("🔨 Building binaries...")
        build_cmd = ["cmake", "--build", str(target.build_dir), "--parallel"]

        if verbose:
            build_cmd.append("--verbose")

        subprocess.run(build_cmd, check=True)  # noqa: S603 - cmake build with validated build directory
        print("✓ Build complete")

    def _list_artifacts(self, build_dir: Path) -> None:
        """List built binary artifacts."""
        import os

        print("\n📦 Build artifacts:")
        for item in sorted(build_dir.iterdir()):
            if item.is_file() and os.access(item, os.X_OK):
                size = item.stat().st_size
                size_kb = size / 1024
                print(f"   {item.name}: {size_kb:.1f} KB")


class DockerComposeRunner(IContainerRunner):
    """Run CMake builds inside Docker Compose containers."""

    def run_in_container(self, config: BuildConfig, options: BuildOptions) -> None:
        """Execute CMake builds directly via Docker Compose."""
        service_name = config.compose_build_service
        console.print(f"[cyan]🐳 Running builds inside Docker Compose service:[/cyan] {service_name}")

        # Build container image
        self._build_image(service_name, options.no_cache)

        # Start service in background
        self._start_service(service_name)

        try:
            # Check and install required packages in container
            if config.cmake_required_apt_packages:
                self._ensure_packages_installed(service_name, config.cmake_required_apt_packages, options.dry_run)

            if options.dry_run:
                return

            # Build all targets via direct cmake commands
            self._build_all_targets(service_name, config, options)

            console.print("[green]✓ Container builds completed[/green]")
        finally:
            # Always stop the service
            self._stop_service(service_name)

    def _build_image(self, service_name: str, no_cache: bool) -> None:
        """Build Docker Compose service image."""
        console.print("[blue]📦 Ensuring container image is ready...[/blue]")
        build_cmd = ["docker", "compose", "build", service_name]
        if no_cache:
            build_cmd.append("--no-cache")

        subprocess.run(build_cmd, check=True)  # noqa: S603 - docker compose with validated service name from config

    def _start_service(self, service_name: str) -> None:
        """Start Docker Compose service in background."""
        console.print("[blue]🚀 Starting service in background...[/blue]")
        start_cmd = ["docker", "compose", "up", "-d", service_name]
        subprocess.run(start_cmd, check=True)  # noqa: S603 - docker compose with validated service name from config

    def _stop_service(self, service_name: str) -> None:
        """Stop Docker Compose service."""
        console.print("[blue]🛑 Stopping service...[/blue]")
        stop_cmd = ["docker", "compose", "stop", service_name]
        subprocess.run(stop_cmd, check=True)  # noqa: S603 - docker compose with validated service name from config

    def _ensure_packages_installed(self, service_name: str, packages: list[str], dry_run: bool) -> None:
        """Check and install required packages in container."""
        if not packages:
            return

        console.print("[blue]🔍 Checking required packages in container...[/blue]")

        # Check which packages are missing
        missing_packages = []
        for package in packages:
            check_cmd = ["docker", "compose", "exec", "-T", service_name, "dpkg", "-s", package]
            result = subprocess.run(check_cmd, capture_output=True)  # noqa: S603 - docker compose exec with validated service and package names
            if result.returncode != 0:
                missing_packages.append(package)

        if not missing_packages:
            console.print("[green]✓ All required packages are installed[/green]")
            return

        if dry_run:
            console.print(f"[yellow]⚠️  Missing packages: {', '.join(missing_packages)}[/yellow]")
            console.print("[dim]   (would install in non-dry-run mode)[/dim]")
            return

        console.print(f"[yellow]📦 Installing missing packages: {', '.join(missing_packages)}[/yellow]")

        # Update package lists
        update_cmd = ["docker", "compose", "exec", "-T", "--user", "root", service_name, "apt-get", "update", "-qq"]
        subprocess.run(update_cmd, check=True)  # noqa: S603 - docker compose exec with validated service name from config

        # Install missing packages
        install_cmd = [
            "docker",
            "compose",
            "exec",
            "-T",
            "--user",
            "root",
            service_name,
            "apt-get",
            "install",
            "-y",
            "-qq",
            "--no-install-recommends",
            *missing_packages,
        ]
        subprocess.run(install_cmd, check=True)  # noqa: S603 - docker compose exec with validated service and package names

        console.print("[green]✓ All required packages installed[/green]")

    def _build_all_targets(self, service_name: str, config: BuildConfig, options: BuildOptions) -> None:
        """Build all architecture/build_type combinations."""
        git_root = Path.cwd()
        source_dir = git_root / config.source_dir

        # Clean build directories if requested
        if options.clean:
            self._clean_build_directories(git_root, config, service_name)

        # Build each target
        for architecture in config.architectures:
            for build_type in config.build_types:
                build_dir_name = config.build_dir_template.format(architecture=architecture, build_type=build_type)
                build_dir = git_root / build_dir_name

                # Format CMake arguments
                cmake_args = [
                    arg.format(architecture=architecture, build_type=build_type) for arg in config.cmake_extra_init_args
                ]

                # Run cmake configure
                self._run_cmake_configure(
                    service_name, source_dir, build_dir, build_type, cmake_args, architecture, options.verbose
                )

                # Run cmake build
                self._run_cmake_build(service_name, build_dir, architecture, build_type, options.verbose)

    def _clean_build_directories(self, git_root: Path, config: BuildConfig, service_name: str) -> None:
        """Clean build directories via container."""
        console.print("[yellow]🧹 Cleaning build directories...[/yellow]")
        for architecture in config.architectures:
            for build_type in config.build_types:
                build_dir_name = config.build_dir_template.format(architecture=architecture, build_type=build_type)
                build_dir = git_root / build_dir_name
                if build_dir.exists():
                    console.print(f"   Removing {build_dir}")
                    import shutil

                    shutil.rmtree(build_dir)

    def _run_cmake_configure(
        self,
        service_name: str,
        source_dir: Path,
        build_dir: Path,
        build_type: str,
        cmake_args: list[str],
        architecture: str,
        verbose: bool,
    ) -> None:
        """Run CMake configuration inside container."""
        console.print(f"\n[bold cyan]{'=' * 70}[/bold cyan]")
        console.print(f"[bold]Configuring {architecture} ({build_type})[/bold]")
        console.print(f"[bold cyan]{'=' * 70}[/bold cyan]")

        # Create build directory on host
        build_dir.mkdir(parents=True, exist_ok=True)

        # Construct cmake configure command
        configure_cmd = [
            "docker",
            "compose",
            "exec",
            "-T",
            service_name,
            "cmake",
            "-S",
            str(source_dir),
            "-B",
            str(build_dir),
            f"-DCMAKE_BUILD_TYPE={build_type}",
            *cmake_args,
        ]

        if verbose:
            configure_cmd.append("-DCMAKE_VERBOSE_MAKEFILE=ON")

        console.print(f"[dim]   Command: {' '.join(configure_cmd[5:])}[/dim]")  # Skip docker compose parts
        subprocess.run(configure_cmd, check=True)  # noqa: S603 - docker compose exec cmake with validated paths and config
        console.print("[green]✓ Configuration complete[/green]")

    def _run_cmake_build(
        self, service_name: str, build_dir: Path, architecture: str, build_type: str, verbose: bool
    ) -> None:
        """Run CMake build inside container."""
        console.print("[blue]🔨 Building binaries...[/blue]")

        # Construct cmake build command
        build_cmd = ["docker", "compose", "exec", "-T", service_name, "cmake", "--build", str(build_dir), "--parallel"]

        if verbose:
            build_cmd.append("--verbose")

        subprocess.run(build_cmd, check=True)  # noqa: S603 - docker compose exec cmake with validated build directory
        console.print("[green]✓ Build complete[/green]")

        # List artifacts
        self._list_artifacts(build_dir)

    def _list_artifacts(self, build_dir: Path) -> None:
        """List built binary artifacts."""
        import os

        console.print("\n[bold]📦 Build artifacts:[/bold]")
        for item in sorted(build_dir.iterdir()):
            if item.is_file() and os.access(item, os.X_OK):
                size = item.stat().st_size
                size_kb = size / 1024
                console.print(f"   [green]{item.name}:[/green] {size_kb:.1f} KB")


class TomlConfigLoader(IConfigLoader):
    """Load configuration from pyproject.toml."""

    def load_config(self, pyproject_path: Path) -> BuildConfig:
        """Load and validate configuration from TOML file.

        Returns:
            Validated build configuration loaded from pyproject.toml.
        """
        if not pyproject_path.exists():
            raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        if "tool" not in data or "pypis_delivery_service" not in data["tool"]:
            raise KeyError("Missing [tool.pypis_delivery_service] section in pyproject.toml")

        return BuildConfig(**data["tool"]["pypis_delivery_service"])


# ==============================================================================
# BUILD ORCHESTRATOR - Coordinates workflow with Dependency Inversion
# ==============================================================================


class BuildOrchestrator:
    """Orchestrate the build process with injected dependencies."""

    def __init__(
        self,
        config_loader: IConfigLoader,
        container_detector: IContainerDetector,
        package_manager: IPackageManager,
        cmake_builder: ICMakeBuilder,
        container_runner: IContainerRunner,
    ):
        """Initialize with dependency injection.

        Args:
            config_loader: Configuration loading implementation
            container_detector: Container detection implementation
            package_manager: Package management implementation
            cmake_builder: CMake build implementation
            container_runner: Container runner implementation
        """
        self.config_loader = config_loader
        self.container_detector = container_detector
        self.package_manager = package_manager
        self.cmake_builder = cmake_builder
        self.container_runner = container_runner

    def orchestrate_build(self, pyproject_path: Path, options: BuildOptions) -> None:
        """Orchestrate the complete build workflow.

        Args:
            pyproject_path: Path to pyproject.toml
            options: Build options from command line
        """
        # Load and validate configuration
        config = self.config_loader.load_config(pyproject_path)

        # Determine execution environment
        inside_container = self.container_detector.is_inside_container()

        if inside_container:
            # Running inside container (e.g., GitLab CI) - run cmake directly
            self._build_in_container(config, options)
        else:
            # Running on host - delegate to Docker Compose
            self._build_on_host(config, options)

    def _build_in_container(self, config: BuildConfig, options: BuildOptions) -> None:
        """Execute builds directly inside container."""
        print("🏗️  Container mode: Building binaries directly")

        # Ensure required packages are installed
        if config.cmake_required_apt_packages:
            self.package_manager.check_and_install(config.cmake_required_apt_packages, dry_run=options.dry_run)

        if options.dry_run:
            return

        # Build all targets
        self._build_all_targets(config, options)

    def _build_on_host(self, config: BuildConfig, options: BuildOptions) -> None:
        """Delegate build to container."""
        print("🖥️  Host mode: Delegating to Docker Compose")
        self.container_runner.run_in_container(config, options)

    def _build_all_targets(self, config: BuildConfig, options: BuildOptions) -> None:
        """Build for all configured architectures and build types."""
        git_root = Path.cwd()
        source_dir = git_root / config.source_dir

        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        # Clean build directories if requested
        if options.clean:
            self._clean_build_directories(git_root, config)

        # Build all targets
        for architecture in config.architectures:
            for build_type in config.build_types:
                target = self._create_build_target(git_root, source_dir, config, architecture, build_type)
                self.cmake_builder.build(target, verbose=options.verbose)

        print(f"\n{'=' * 70}")
        print("✓ All builds completed successfully")
        print(f"{'=' * 70}")

    def _clean_build_directories(self, git_root: Path, config: BuildConfig) -> None:
        """Clean all build directories."""
        import shutil

        print("🧹 Cleaning build directories...")
        for architecture in config.architectures:
            for build_type in config.build_types:
                build_dir_name = config.build_dir_template.format(architecture=architecture, build_type=build_type)
                build_dir = git_root / build_dir_name
                if build_dir.exists():
                    print(f"   Removing {build_dir}")
                    shutil.rmtree(build_dir)

    def _create_build_target(
        self, git_root: Path, source_dir: Path, config: BuildConfig, architecture: str, build_type: str
    ) -> BuildTarget:
        """Create a build target specification.

        Returns:
            A configured BuildTarget instance for the specified architecture and build type.
        """
        build_dir_name = config.build_dir_template.format(architecture=architecture, build_type=build_type)
        build_dir = git_root / build_dir_name

        cmake_args = [
            arg.format(architecture=architecture, build_type=build_type) for arg in config.cmake_extra_init_args
        ]

        return BuildTarget(
            architecture=architecture,
            build_type=build_type,
            source_dir=source_dir,
            build_dir=build_dir,
            cmake_args=cmake_args,
        )


# ==============================================================================
# DEPENDENCY INJECTION FACTORY
# ==============================================================================


def create_orchestrator() -> BuildOrchestrator:
    """Create build orchestrator with concrete implementations.

    This factory method demonstrates Dependency Inversion - we create
    concrete implementations here but inject them as abstractions.

    Returns:
        Configured BuildOrchestrator instance
    """
    return BuildOrchestrator(
        config_loader=TomlConfigLoader(),
        container_detector=ContainerDetector(),
        package_manager=AptPackageManager(),
        cmake_builder=CMakeBuilder(),
        container_runner=DockerComposeRunner(),
    )


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================


@app.command()
def build(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose build output"),
    clean: bool = typer.Option(False, "--clean", "-c", help="Clean build directories before building"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Build Docker image without cache"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check packages without installing (container mode only)"),
) -> None:
    """Build binaries for all configured architectures.

    Reads configuration from [tool.pypis_delivery_service] in pyproject.toml and
    builds for all architectures (x86_64, aarch64) and build types (Release, Debug).

    On host: Delegates to Docker Compose container
    In container: Installs packages and runs CMake builds directly
    """
    try:
        # Create build options
        options = BuildOptions(verbose=verbose, clean=clean, no_cache=no_cache, dry_run=dry_run)

        # Find pyproject.toml
        pyproject_path = Path.cwd() / "pyproject.toml"

        # Create orchestrator with dependency injection
        orchestrator = create_orchestrator()

        # Execute build workflow
        orchestrator.orchestrate_build(pyproject_path, options)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()
