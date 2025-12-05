"""Tests for template rendering functions in mkapidocs.

Tests cover:
- mkdocs.yml generation with conditional plugins
- GitHub Actions workflow generation
- gen_ref_pages.py script generation
- Documentation structure creation (index.md, API reference)
- Feature-conditional template rendering (Typer, C code, private registry)
- YAML merge behavior for existing configurations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from mkapidocs.generator import (
    create_api_reference,
    create_generated_content,
    create_github_actions,
    create_index_page,
    create_mkdocs_config,
    update_gitignore,
)
from mkapidocs.models import CIProvider

if TYPE_CHECKING:
    from pathlib import Path


class TestCreateMkdocsConfig:
    """Test suite for mkdocs.yml generation.

    Tests the create_mkdocs_config function which renders the MkDocs configuration
    file with conditional plugins based on detected project features.
    """

    def test_creates_valid_yaml_basic_config(self, mock_repo_path: Path) -> None:
        """Test mkdocs.yml generation creates valid YAML with basic configuration.

        Tests: create_mkdocs_config() basic functionality
        How: Call function with minimal parameters, verify YAML structure via string checks
        Why: Generated config must be valid YAML for MkDocs to consume

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        project_name = "test-project"
        site_url = "https://test-user.github.io/test-project/"

        # Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name=project_name,
            site_url=site_url,
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        assert mkdocs_path.exists()

        content = mkdocs_path.read_text()
        # Verify key configuration values present (YAML contains Python tags, can't parse safely)
        assert f"site_name: {project_name}" in content
        assert f"site_url: {site_url}" in content
        assert "theme:" in content
        assert "name: material" in content

    def test_includes_base_plugins(self, mock_repo_path: Path) -> None:
        """Test mkdocs.yml includes mandatory base plugins.

        Tests: Base plugin configuration is always present
        How: Parse generated YAML and verify plugin list contains required plugins
        Why: All projects need search, mkdocstrings, gen-files, literate-nav

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="test-project",
            site_url="https://example.com/",
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        rendered_content = mkdocs_path.read_text()

        # Verify base plugins are present (check string content for plugin names)
        assert "search" in rendered_content

        assert "mkdocstrings" in rendered_content
        assert "mermaid2" in rendered_content
        assert "termynal" in rendered_content

    def test_adds_typer_plugin_when_detected(self, mock_repo_path: Path) -> None:
        """Test mkdocs.yml includes mkdocs-typer2 plugin when Typer detected.

        Tests: Conditional plugin inclusion for Typer CLI projects
        How: Set has_typer=True, verify mkdocs-typer2 in rendered YAML
        Why: Typer projects need mkdocs-typer2 for CLI documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="cli-project",
            site_url="https://example.com/",
            c_source_dirs=[],
            has_typer=True,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        rendered_content = mkdocs_path.read_text()

        assert "mkdocs-typer2" in rendered_content

    def test_excludes_typer_plugin_when_not_detected(
        self, mock_repo_path: Path
    ) -> None:
        """Test mkdocs.yml excludes mkdocs-typer2 plugin when Typer not detected.

        Tests: Conditional plugin exclusion for non-Typer projects
        How: Set has_typer=False, verify mkdocs-typer2 not in rendered YAML
        Why: Avoid unnecessary plugin dependencies for non-CLI projects

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="lib-project",
            site_url="https://example.com/",
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        rendered_content = mkdocs_path.read_text()

        assert "mkdocs-typer2" not in rendered_content

    def test_adds_mkdoxy_plugin_when_c_code_detected(
        self, mock_repo_path: Path
    ) -> None:
        """Test mkdocs.yml includes mkdoxy plugin when C/C++ code detected.

        Tests: Conditional plugin inclusion for C/C++ projects
        How: Set c_source_dirs=[mock_repo_path / "source"], verify mkdoxy configuration in rendered YAML
        Why: C/C++ projects need Doxygen integration via mkdoxy

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="c-project",
            site_url="https://example.com/",
            c_source_dirs=[mock_repo_path / "source"],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        rendered_content = mkdocs_path.read_text()

        assert "mkdoxy" in rendered_content
        assert "src-dirs: source" in rendered_content

    def test_excludes_mkdoxy_plugin_when_no_c_code(self, mock_repo_path: Path) -> None:
        """Test mkdocs.yml excludes mkdoxy plugin when no C/C++ code detected.

        Tests: Conditional plugin exclusion for Python-only projects
        How: Set c_source_dirs=[], verify mkdoxy not in rendered YAML
        Why: Avoid Doxygen dependency for pure Python projects

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="python-project",
            site_url="https://example.com/",
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        rendered_content = mkdocs_path.read_text()

        assert "mkdoxy" not in rendered_content

    def test_includes_all_features_when_enabled(self, mock_repo_path: Path) -> None:
        """Test mkdocs.yml includes all conditional plugins when all features enabled.

        Tests: Integration of multiple conditional features
        How: Set has_typer=True and c_source_dirs=[mock_repo_path / "source"], verify all plugins present
        Why: Projects with multiple features need all corresponding plugins

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="full-featured-project",
            site_url="https://example.com/",
            c_source_dirs=[mock_repo_path / "source"],
            has_typer=True,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        rendered_content = mkdocs_path.read_text()

        # Verify all conditional plugins are present
        assert "mkdocs-typer2" in rendered_content
        assert "mkdoxy" in rendered_content

        # Verify base plugins still present
        assert "mkdocstrings" in rendered_content

    def test_preserves_existing_config_on_update(self, mock_repo_path: Path) -> None:
        """Test mkdocs.yml merge preserves user customizations when file exists.

        Tests: Smart merge behavior for existing mkdocs.yml
        How: Create existing mkdocs.yml with custom settings, run create_mkdocs_config
        Why: User customizations must be preserved during documentation updates

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange - Create existing mkdocs.yml with custom navigation
        existing_config = """site_name: old-project
site_url: https://old-url.com/

theme:
  name: material
  custom_setting: preserved

plugins:
  - search
  - mkdocstrings

nav:
  - Home: index.md
  - Custom Page: custom.md
"""
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        mkdocs_path.write_text(existing_config)

        # Act - Update with new template
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="new-project",
            site_url="https://new-url.com/",
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert - Verify merge behavior
        content = mkdocs_path.read_text()

        # site_url is template-owned and should be updated
        assert "site_url: https://new-url.com/" in content

        # User customizations in theme should be preserved
        assert "custom_setting: preserved" in content

        # User nav customizations should be preserved
        assert "Custom Page" in content

    def test_github_provider_sets_site_dir_to_site(self, mock_repo_path: Path) -> None:
        """Test that GitHub provider configures site_dir: site in mkdocs.yml.

        Tests: site_dir configuration based on CI provider
        How: Create mkdocs.yml with GITHUB provider, verify site_dir value
        Why: GitHub Pages uses 'site' directory for artifacts

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="github-project",
            site_url="https://example.github.io/project/",
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITHUB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        content = mkdocs_path.read_text()
        assert "site_dir: site" in content
        assert "site_dir: public" not in content

    def test_gitlab_provider_sets_site_dir_to_public(
        self, mock_repo_path: Path
    ) -> None:
        """Test that GitLab provider configures site_dir: public in mkdocs.yml.

        Tests: site_dir configuration based on CI provider
        How: Create mkdocs.yml with GITLAB provider, verify site_dir value
        Why: GitLab Pages requires 'public' directory for artifacts

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_mkdocs_config(
            repo_path=mock_repo_path,
            project_name="gitlab-project",
            site_url="https://example.gitlab.io/project/",
            c_source_dirs=[],
            has_typer=False,
            ci_provider=CIProvider.GITLAB,
        )

        # Assert
        mkdocs_path = mock_repo_path / "mkdocs.yml"
        content = mkdocs_path.read_text()
        assert "site_dir: public" in content
        assert "site_dir: site" not in content


class TestCreateGitHubActions:
    """Test suite for GitHub Actions workflow generation.

    Tests the create_github_actions function which renders the GitHub Pages
    deployment workflow file.
    """

    def test_creates_workflow_file(self, mock_repo_path: Path) -> None:
        """Test GitHub Actions workflow file creation.

        Tests: create_github_actions() creates .github/workflows/pages.yml
        How: Call function, verify file exists at expected path
        Why: GitHub Pages deployment requires workflow file

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_github_actions(repo_path=mock_repo_path)

        # Assert
        workflow_path = mock_repo_path / ".github" / "workflows" / "pages.yml"
        assert workflow_path.exists()

    def test_workflow_contains_valid_yaml(self, mock_repo_path: Path) -> None:
        """Test GitHub Actions workflow contains valid YAML structure.

        Tests: Generated workflow is valid YAML
        How: Parse workflow file with yaml.safe_load
        Why: GitHub Actions requires valid YAML to execute

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_github_actions(repo_path=mock_repo_path)

        # Assert
        workflow_path = mock_repo_path / ".github" / "workflows" / "pages.yml"
        workflow_content = workflow_path.read_text()
        yaml_parser = YAML()
        parsed_yaml = yaml_parser.load(workflow_content)
        assert isinstance(parsed_yaml, dict)

        assert parsed_yaml["name"] == "Deploy Documentation"
        assert "on" in parsed_yaml
        assert "jobs" in parsed_yaml

    def test_workflow_contains_required_jobs(self, mock_repo_path: Path) -> None:
        """Test GitHub Actions workflow contains build and deploy jobs.

        Tests: Workflow includes required job definitions
        How: Parse YAML and verify job names and structure
        Why: GitHub Pages deployment requires build and deploy jobs

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_github_actions(repo_path=mock_repo_path)

        # Assert
        workflow_path = mock_repo_path / ".github" / "workflows" / "pages.yml"
        yaml_parser = YAML()
        parsed_yaml = yaml_parser.load(workflow_path.read_text())
        assert isinstance(parsed_yaml, dict)
        jobs = parsed_yaml["jobs"]
        assert isinstance(jobs, dict)

        assert "build" in jobs
        assert "deploy" in jobs

    def test_workflow_uses_local_script_command(self, mock_repo_path: Path) -> None:
        """Test GitHub Actions workflow uses local script to run mkapidocs.

        Tests: Workflow build step uses ./mkapidocs build command
        How: Parse workflow YAML and check build step commands
        Why: PEP 723 scripts are self-executing via shebang

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_github_actions(repo_path=mock_repo_path)

        # Assert
        workflow_path = mock_repo_path / ".github" / "workflows" / "pages.yml"
        workflow_content = workflow_path.read_text()

        assert "uv run mkapidocs build . --strict" in workflow_content

    def test_workflow_overwrites_existing_file(self, mock_repo_path: Path) -> None:
        """Test GitHub Actions workflow overwrites existing file.

        Tests: create_github_actions() replaces existing workflow
        How: Create existing workflow, call function, verify content replaced
        Why: GitHub Actions workflows should be template-controlled, not merged

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange - Create existing workflow
        workflow_dir = mock_repo_path / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        workflow_path = workflow_dir / "pages.yml"
        workflow_path.write_text("name: Old Workflow\n")

        # Act
        create_github_actions(repo_path=mock_repo_path)

        # Assert
        new_content = workflow_path.read_text()
        assert "name: Deploy Documentation" in new_content
        assert "name: Old Workflow" not in new_content


class TestCreateIndexPage:
    """Test suite for documentation homepage generation.

    Tests the create_index_page function which renders the docs/index.md
    file with project information and feature-specific content.
    """

    def test_creates_index_md_file(self, mock_repo_path: Path) -> None:
        """Test index.md file creation in docs/ directory.

        Tests: create_index_page() creates docs/index.md
        How: Call function, verify file exists
        Why: Every documentation site needs a homepage

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_index_page(
            repo_path=mock_repo_path,
            project_name="test-project",
            description="Test project description",
            c_source_dirs=[],
            has_typer=False,
            license_name="MIT",
            has_private_registry=False,
            private_registry_url=None,
        )

        # Assert
        index_path = mock_repo_path / "docs" / "index.md"
        assert index_path.exists()

    def test_index_contains_project_info(self, mock_repo_path: Path) -> None:
        """Test index.md contains project name and description.

        Tests: Template renders project metadata correctly
        How: Verify project name and description in rendered content
        Why: Homepage must display project information

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange
        project_name = "my-awesome-project"
        description = "This is an awesome test project"

        # Act
        create_index_page(
            repo_path=mock_repo_path,
            project_name=project_name,
            description=description,
            c_source_dirs=[],
            has_typer=False,
            license_name="Apache 2.0",
            has_private_registry=False,
            private_registry_url=None,
        )

        # Assert
        index_path = mock_repo_path / "docs" / "index.md"
        content = index_path.read_text()

        assert f"# {project_name}" in content
        assert description in content
        assert "Apache 2.0" in content

    def test_index_includes_snippets_directive(self, mock_repo_path: Path) -> None:
        """Test index.md includes MkDocs snippets for dynamic content.

        Tests: Generated content snippets are referenced via --8<--
        How: Verify snippets directive syntax in rendered markdown
        Why: Generated features list must be included via snippets

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_index_page(
            repo_path=mock_repo_path,
            project_name="test-project",
            description="Test description",
            c_source_dirs=[],
            has_typer=False,
            license_name="MIT",
            has_private_registry=False,
            private_registry_url=None,
        )

        # Assert
        index_path = mock_repo_path / "docs" / "index.md"
        content = index_path.read_text()

        # Verify snippets directives for generated content
        assert '--8<-- "generated/index-features.md"' in content
        assert '--8<-- "generated/install-registry.md"' in content

    def test_preserves_existing_index(self, mock_repo_path: Path) -> None:
        """Test index.md preservation when file already exists.

        Tests: create_index_page() preserves existing index.md
        How: Create existing index.md, call function, verify not overwritten
        Why: User customizations to homepage must be preserved

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange - Create existing index.md
        docs_dir = mock_repo_path / "docs"
        docs_dir.mkdir()
        index_path = docs_dir / "index.md"
        existing_content = "# Custom Homepage\n\nUser-customized content"
        index_path.write_text(existing_content)

        # Act
        create_index_page(
            repo_path=mock_repo_path,
            project_name="test-project",
            description="Test description",
            c_source_dirs=[],
            has_typer=False,
            license_name="MIT",
            has_private_registry=False,
            private_registry_url=None,
        )

        # Assert
        content = index_path.read_text()
        assert content == existing_content


class TestCreateAPIReference:
    """Test suite for API reference documentation generation.

    Tests the create_api_reference function which creates Python API,
    C API, and CLI reference pages based on project features.
    """

    def test_creates_python_api_reference(self, mock_repo_path: Path) -> None:
        """Test Python API reference page creation.

        Tests: create_api_reference() creates python-api.md
        How: Call function, verify file exists at docs/generated/python-api.md
        Why: All Python projects need API documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="test-project",
            c_source_dirs=[],
            cli_modules=None,
        )

        # Assert
        python_api_path = mock_repo_path / "docs" / "generated" / "python-api.md"
        assert python_api_path.exists()

    def test_python_api_contains_mkdocstrings_directive(
        self, mock_repo_path: Path
    ) -> None:
        """Test Python API reference contains mkdocstrings directive.

        Tests: Template uses ::: syntax for mkdocstrings
        How: Verify ::: directive with package name in rendered markdown
        Why: mkdocstrings requires ::: directive to generate API docs

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="my-package",
            c_source_dirs=[],
            cli_modules=None,
        )

        # Assert
        python_api_path = mock_repo_path / "docs" / "generated" / "python-api.md"
        content = python_api_path.read_text()

        # Package name with underscores (my-package -> my_package)
        assert "::: my_package" in content

    def test_creates_c_api_when_c_code_detected(self, mock_repo_path: Path) -> None:
        """Test C API reference page created when C code detected.

        Tests: Conditional C API page creation
        How: Set c_source_dirs=[mock_repo_path / "source"], verify c-api.md exists
        Why: C/C++ projects need separate API documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="c-project",
            c_source_dirs=[mock_repo_path / "source"],
            cli_modules=None,
        )

        # Assert
        c_api_path = mock_repo_path / "docs" / "generated" / "c-api.md"
        assert c_api_path.exists()

    def test_excludes_c_api_when_no_c_code(self, mock_repo_path: Path) -> None:
        """Test C API reference page not created when no C code.

        Tests: Conditional C API page exclusion
        How: Set c_source_dirs=[], verify c-api.md does not exist
        Why: Pure Python projects don't need C API documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="python-project",
            c_source_dirs=[],
            cli_modules=None,
        )

        # Assert
        c_api_path = mock_repo_path / "docs" / "generated" / "c-api.md"
        assert not c_api_path.exists()

    def test_creates_cli_api_when_module_detected(self, mock_repo_path: Path) -> None:
        """Test CLI reference page created when CLI module detected.

        Tests: Conditional CLI page creation
        How: Provide cli_modules parameter, verify cli-api.md exists
        Why: Typer CLI projects need CLI documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="cli-project",
            c_source_dirs=[],
            cli_modules=["cli_project.cli"],
        )

        # Assert
        cli_api_path = mock_repo_path / "docs" / "generated" / "cli-api.md"
        assert cli_api_path.exists()

    def test_cli_api_contains_typer_directive(self, mock_repo_path: Path) -> None:
        """Test CLI reference contains mkdocs-typer2 directive.

        Tests: Template uses correct mkdocs-typer2 syntax
        How: Verify ::: mkdocs-typer2 directive with module path
        Why: mkdocs-typer2 requires specific directive format

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="my-cli-project",
            c_source_dirs=[],
            cli_modules=["my_cli_project.cli"],
        )

        # Assert
        cli_api_path = mock_repo_path / "docs" / "generated" / "cli-api.md"
        content = cli_api_path.read_text()

        assert "::: mkdocs-typer2" in content
        assert ":module: my_cli_project.cli" in content

    def test_excludes_cli_api_when_no_module(self, mock_repo_path: Path) -> None:
        """Test CLI reference page not created when no CLI module.

        Tests: Conditional CLI page exclusion
        How: Set cli_modules=None, verify cli-api.md does not exist
        Why: Non-CLI projects don't need CLI documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_api_reference(
            repo_path=mock_repo_path,
            project_name="lib-project",
            c_source_dirs=[],
            cli_modules=None,
        )

        # Assert
        cli_api_path = mock_repo_path / "docs" / "generated" / "cli-api.md"
        assert not cli_api_path.exists()


class TestCreateGeneratedContent:
    """Test suite for generated content snippets.

    Tests the create_generated_content function which creates dynamic content
    snippets for inclusion in documentation (features list, install instructions).
    """

    def test_creates_index_features_snippet(self, mock_repo_path: Path) -> None:
        """Test index-features.md snippet creation.

        Tests: create_generated_content() creates index-features.md
        How: Call function, verify file exists
        Why: Features list is dynamically generated based on project features

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="test-project",
            c_source_dirs=[],
            cli_modules=[],
            has_private_registry=False,
            private_registry_url=None,
            has_scripts=False,
        )

        # Assert
        features_path = mock_repo_path / "docs" / "generated" / "index-features.md"
        assert features_path.exists()

    def test_features_includes_python_api_link(self, mock_repo_path: Path) -> None:
        """Test features snippet includes Python API reference link.

        Tests: Base features list always includes Python API
        How: Verify Python API reference link in generated content
        Why: All projects have Python API documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="test-project",
            c_source_dirs=[],
            cli_modules=[],
            has_private_registry=False,
            private_registry_url=None,
            has_scripts=False,
        )

        # Assert
        features_path = mock_repo_path / "docs" / "generated" / "index-features.md"
        content = features_path.read_text()

        assert "Python API Reference" in content
        assert "python-api.md" in content

    def test_features_includes_cli_link_when_typer_detected(
        self, mock_repo_path: Path
    ) -> None:
        """Test features snippet includes CLI reference when Typer detected.

        Tests: Conditional CLI reference link in features list
        How: Set cli_modules with module path, verify CLI reference link present
        Why: Typer projects should promote CLI documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="cli-project",
            c_source_dirs=[],
            cli_modules=["cli_project.cli"],
            has_private_registry=False,
            private_registry_url=None,
            has_scripts=True,
        )

        # Assert
        features_path = mock_repo_path / "docs" / "generated" / "index-features.md"
        content = features_path.read_text()

        assert "CLI Reference" in content
        assert "cli-api.md" in content

    def test_features_includes_c_api_link_when_c_code_detected(
        self, mock_repo_path: Path
    ) -> None:
        """Test features snippet includes C API reference when C code detected.

        Tests: Conditional C API reference link in features list
        How: Set c_source_dirs=[mock_repo_path / "source"], verify C API reference link present
        Why: C/C++ projects should promote C API documentation

        Args:
            mock_repo_path: Temporary repository directory
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="c-project",
            c_source_dirs=[mock_repo_path / "source"],
            cli_modules=[],
            has_private_registry=False,
            private_registry_url=None,
            has_scripts=False,
        )

        # Assert
        features_path = mock_repo_path / "docs" / "generated" / "index-features.md"
        content = features_path.read_text()

        assert "C API Reference" in content
        assert "c-api.md" in content

    def test_creates_install_command_snippet(self, mock_repo_path: Path) -> None:
        """Test install-command.md snippet creation.

        Tests: create_generated_content() creates install-command.md
        How: Call function, verify file exists
        Why: Install instructions are dynamically generated
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="test-project",
            c_source_dirs=[],
            cli_modules=[],
            has_private_registry=False,
            private_registry_url=None,
            has_scripts=False,
        )

        # Assert
        command_path = mock_repo_path / "docs" / "generated" / "install-command.md"
        assert command_path.exists()

    def test_install_command_snippet_includes_private_registry_command(
        self, mock_repo_path: Path
    ) -> None:
        """Test install command snippet includes private registry flag.

        Tests: Private registry install instructions
        How: Set has_private_registry=True with URL, verify install command
        Why: Users need specific install command for private registries
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="private-project",
            c_source_dirs=[],
            cli_modules=[],
            has_private_registry=True,
            private_registry_url="https://private.pypi.org/simple",
            has_scripts=False,
        )

        # Assert
        command_path = mock_repo_path / "docs" / "generated" / "install-command.md"
        content = command_path.read_text()

        assert "uv add" in content
        assert '--index="https://private.pypi.org/simple"' in content
        assert "private-project" in content

    def test_install_command_snippet_includes_standard_command(
        self, mock_repo_path: Path
    ) -> None:
        """Test install command snippet includes standard command when no private registry.

        Tests: Standard install instructions
        How: Set has_private_registry=False, verify standard command
        Why: Public packages use standard install command
        """
        # Arrange & Act
        create_generated_content(
            repo_path=mock_repo_path,
            project_name="public-project",
            c_source_dirs=[],
            cli_modules=[],
            has_private_registry=False,
            private_registry_url=None,
            has_scripts=False,
        )

        # Assert
        command_path = mock_repo_path / "docs" / "generated" / "install-command.md"
        content = command_path.read_text()

        assert "uv add public-project" in content
        assert "--index" not in content


class TestUpdateGitignore:
    """Tests for .gitignore update functionality."""

    def test_update_gitignore_github_creates_new_file(self, tmp_path: Path) -> None:
        """Test creating new .gitignore with GitHub provider."""
        # Arrange

        # Act
        update_gitignore(tmp_path, CIProvider.GITHUB)

        # Assert
        gitignore_path = tmp_path / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "/site/" in content
        assert ".mkdocs_cache/" in content
        assert "/public/" not in content

    def test_update_gitignore_gitlab_creates_new_file(self, tmp_path: Path) -> None:
        """Test creating new .gitignore with GitLab provider."""
        # Arrange

        # Act
        update_gitignore(tmp_path, CIProvider.GITLAB)

        # Assert
        gitignore_path = tmp_path / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "/public/" in content
        assert ".mkdocs_cache/" in content
        assert "/site/" not in content

    def test_update_gitignore_github_appends_to_existing(self, tmp_path: Path) -> None:
        """Test appending to existing .gitignore with GitHub provider."""
        # Arrange
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("# Existing content\n*.pyc\n__pycache__/\n")

        # Act
        update_gitignore(tmp_path, CIProvider.GITHUB)

        # Assert
        content = gitignore_path.read_text()
        assert "# Existing content" in content
        assert "*.pyc" in content
        assert "/site/" in content
        assert ".mkdocs_cache/" in content
        assert "/public/" not in content

    def test_update_gitignore_gitlab_appends_to_existing(self, tmp_path: Path) -> None:
        """Test appending to existing .gitignore with GitLab provider."""
        # Arrange
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("# Existing content\n*.pyc\n__pycache__/\n")

        # Act
        update_gitignore(tmp_path, CIProvider.GITLAB)

        # Assert
        content = gitignore_path.read_text()
        assert "# Existing content" in content
        assert "*.pyc" in content
        assert "/public/" in content
        assert ".mkdocs_cache/" in content
        assert "/site/" not in content

    def test_update_gitignore_github_skips_duplicate_entries(
        self, tmp_path: Path
    ) -> None:
        """Test that GitHub entries are not duplicated if already present."""
        # Arrange
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("# MkDocs documentation\n/site/\n.mkdocs_cache/\n")

        # Act
        update_gitignore(tmp_path, CIProvider.GITHUB)

        # Assert
        content = gitignore_path.read_text()
        # Count occurrences - should only appear once each
        assert content.count("/site/") == 1
        assert content.count(".mkdocs_cache/") == 1

    def test_update_gitignore_gitlab_skips_duplicate_entries(
        self, tmp_path: Path
    ) -> None:
        """Test that GitLab entries are not duplicated if already present."""
        # Arrange
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("# MkDocs documentation\n/public/\n.mkdocs_cache/\n")

        # Act
        update_gitignore(tmp_path, CIProvider.GITLAB)

        # Assert
        content = gitignore_path.read_text()
        # Count occurrences - should only appear once each
        assert content.count("/public/") == 1
        assert content.count(".mkdocs_cache/") == 1

    def test_update_gitignore_includes_generated_when_requested(
        self, tmp_path: Path
    ) -> None:
        """Test that docs/generated/ is added when include_generated=True."""
        # Arrange

        # Act
        update_gitignore(tmp_path, CIProvider.GITHUB, include_generated=True)

        # Assert
        gitignore_path = tmp_path / ".gitignore"
        content = gitignore_path.read_text()
        assert "/site/" in content
        assert ".mkdocs_cache/" in content
        assert "docs/generated/" in content

    def test_update_gitignore_excludes_generated_by_default(
        self, tmp_path: Path
    ) -> None:
        """Test that docs/generated/ is not added by default."""
        # Arrange

        # Act
        update_gitignore(tmp_path, CIProvider.GITLAB)

        # Assert
        gitignore_path = tmp_path / ".gitignore"
        content = gitignore_path.read_text()
        assert "/public/" in content
        assert ".mkdocs_cache/" in content
        assert "docs/generated/" not in content
