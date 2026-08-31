# Architecture

**Analysis Date:** 2026-02-07

## Pattern Overview

**Overall:** Layered command-line application with two-phase execution model

**Key Characteristics:**
- Typer-based CLI with 5 commands (version, info, setup, build, serve)
- Two-phase execution model for CLI imports: external call triggers internal call in target environment
- Feature-detection-driven template rendering (Jinja2)
- Non-destructive YAML merging preserving formatting and user customizations
- Modular separation of concerns: detection, generation, validation, building, UI

## Layers

**CLI Layer:**
- Purpose: Command entry points and user interaction
- Location: `packages/mkapidocs/cli.py`
- Contains: Typer app, command handlers, error handling, logging configuration
- Depends on: generator, builder, validators, models, yaml_utils
- Used by: User via `mkapidocs` command

**Generation Layer:**
- Purpose: Orchestrate documentation setup, feature detection, content generation
- Location: `packages/mkapidocs/generator.py`
- Contains: setup_documentation(), create_* functions, YAML merging, git URL parsing, CI provider detection, GitLab API queries
- Depends on: project_detection, models, templates, yaml_utils, tomlkit, jinja2
- Used by: CLI setup command

**Detection Layer:**
- Purpose: Detect project features and read configuration
- Location: `packages/mkapidocs/project_detection.py`
- Contains: detect_c_code(), detect_typer_dependency(), read_pyproject(), detect_private_registry(), detect_ci_provider()
- Depends on: models, console
- Used by: generator, validators

**Build/Serve Layer:**
- Purpose: Execute MkDocs builds/serves, handle two-phase execution
- Location: `packages/mkapidocs/builder.py`
- Contains: build_docs(), serve_docs(), is_mkapidocs_in_target_env(), is_running_in_target_env(), subprocess management, signal handling
- Depends on: console, subprocess, os, signal
- Used by: CLI build/serve commands

**Validation Layer:**
- Purpose: Validate environment, check dependencies, auto-install tools
- Location: `packages/mkapidocs/validators.py`
- Contains: validate_environment(), display_validation_results(), DoxygenInstaller, ValidationResult
- Depends on: project_detection, models, httpx, subprocess
- Used by: CLI setup/build/serve commands

**Data Models Layer:**
- Purpose: Type-safe configuration and data structures
- Location: `packages/mkapidocs/models.py`
- Contains: Pydantic models (PyprojectConfig, ProjectConfig, GitLabCIConfig), enums (CIProvider, MessageType), TOML type aliases
- Depends on: pydantic, yaml_utils, tomlkit
- Used by: All layers for structured data

**YAML Handling Layer:**
- Purpose: Centralized YAML operations preserving formatting
- Location: `packages/mkapidocs/yaml_utils.py`
- Contains: load_yaml(), load_yaml_from_path(), merge_mkdocs_yaml(), append_to_yaml_list(), display_file_changes()
- Depends on: ruamel.yaml, rich
- Used by: generator, models, validators

**UI Layer:**
- Purpose: Consistent console output and display helpers
- Location: `packages/mkapidocs/console.py`
- Contains: Shared console instance, display helpers (get_rendered_width, print_table, print_panel)
- Depends on: rich
- Used by: All modules for output

**Template Layer:**
- Purpose: Provide template strings and content
- Location: `packages/mkapidocs/templates/`
- Contains: Python modules (index_md_template.py, install_md_template.py, cli_md_template.py, c_api_md_template.py, python_api_md_template.py) and static files (mkdocs.yml.j2, pages.yml, gitlab-ci.yml)
- Depends on: None (pure content)
- Used by: generator for rendering documentation and CI workflows

## Data Flow

**Setup Flow (mkapidocs setup /path/to/project):**

1. CLI.setup() validates input arguments
2. validate_environment() checks Python, uv, git, pyproject.toml
3. setup_documentation() orchestrates:
   - read_pyproject() reads target's pyproject.toml → PyprojectConfig
   - detect_c_code() scans for C/C++ files
   - detect_typer_dependency() checks dependencies
   - detect_ci_provider() detects GitHub/GitLab from git remote or filesystem
   - detect_gitlab_url_base() or query_gitlab_pages_url() gets Pages URL
   - Render mkdocs.yml.j2 with detected features
   - merge_mkdocs_yaml() merges with existing mkdocs.yml (non-destructive)
   - create_github_actions() or create_gitlab_ci() generates CI workflows
   - create_index_page(), create_api_reference(), create_supporting_docs() generate markdown pages
4. Display success message with next steps

**Build Flow (mkapidocs build /path/to/project):**

1. CLI.build() validates target environment
2. is_mkapidocs_in_target_env() checks if mkapidocs is in target's dev dependencies
3. If yes (internal phase):
   - build_docs() calls mkdocs build directly
   - MKAPIDOCS_INTERNAL_CALL=1 in environment (prevents recursion)
4. If no (external phase):
   - build_docs() calls `uv run mkapidocs build .` to trigger internal phase
   - target environment's mkdocs-typer2 imports target's CLI module
5. Exit with status code

**Serve Flow (mkapidocs serve /path/to/project):**

1. Similar to build flow but calls mkdocs serve
2. Signal handler forwards SIGINT to child process for graceful shutdown

**State Management:**

- No persistent state between commands
- Configuration read from target project's pyproject.toml and mkdocs.yml
- Features detected fresh on each setup call
- MKAPIDOCS_INTERNAL_CALL environment variable coordinates two-phase execution
- Validation results stored in ValidationResult dataclass for UI display

## Key Abstractions

**SetupResult:**
- Purpose: Encapsulates setup() output and messaging context
- Properties: provider (CIProvider), is_first_run (bool), mkapidocs_installed (bool)
- Used by: CLI to determine success message content

**ValidationResult:**
- Purpose: Type-safe result from a single validation check
- Properties: check_name, passed (bool), message, value (optional), required (bool)
- Used by: Validation layer for collecting and displaying results

**PyprojectConfig:**
- Purpose: Typed access to target project's pyproject.toml
- Properties: project (ProjectConfig), tool (dict), uv_index, ruff_lint_select, cmake_source_dir, has_scripts, script_names
- Pattern: Pydantic model wrapping tomlkit data, provides property accessors for tool-specific config

**CIProvider (Enum):**
- Values: GITHUB, GITLAB
- Used throughout for branching logic and template selection

**GitLabCIConfig:**
- Purpose: Type-safe parsing of .gitlab-ci.yml with include validation
- Methods: load(), from_dict(), add_include_and_save(), add_stage_and_save()
- Pattern: Dataclass with classmethods for file I/O and modification

**GitLabPagesResult:**
- Purpose: Result of GitLab Pages API query
- Properties: url, no_deployments (bool), error (optional)
- Used by: generator to detect GitLab Pages URLs via GraphQL API

## Entry Points

**CLI Entry:**
- Location: `packages/mkapidocs/cli.py` main() → app (Typer instance)
- Triggers: `mkapidocs` command with subcommand
- Responsibilities: Parse arguments, validate input, delegate to appropriate handler

**Setup Command:**
- Location: `packages/mkapidocs/cli.py` setup()
- Triggers: `mkapidocs setup [directory] [--provider ...] [--site-url ...]`
- Responsibilities: Validate environment, call setup_documentation(), display result

**Build Command:**
- Location: `packages/mkapidocs/cli.py` build()
- Triggers: `mkapidocs build [directory] [--strict] [--output-dir ...]`
- Responsibilities: Validate environment, call build_docs(), handle exit code

**Serve Command:**
- Location: `packages/mkapidocs/cli.py` serve()
- Triggers: `mkapidocs serve [directory] [--host ...] [--port ...]`
- Responsibilities: Validate environment, call serve_docs(), handle exit code

**Two-Phase Execution:**
- External: User calls `mkapidocs build /path/to/project` (no env var set)
- Internal: mkapidocs calls `uv run mkapidocs build .` with MKAPIDOCS_INTERNAL_CALL=1
- Detection: builder.is_running_in_target_env() checks MKAPIDOCS_INTERNAL_CALL env var

## Error Handling

**Strategy:** Exception propagation with user-friendly messages

**Patterns:**

- **Validation Failures:** validate_environment() returns (bool, results); CLI displays ValidationResult table then exits(1)
- **File I/O:** FileNotFoundError → handle_error() displays message + exits(1)
- **TOML Parsing:** TOMLKitError → handle_error() displays message + exits(1)
- **YAML Parsing:** YAMLError → handle_error() displays message + exits(1)
- **Network Errors:** httpx.RequestError → handle_error() displays message + exits(1)
- **Provider Detection:** ValueError if provider cannot be detected → handle_error() + exits(1)
- **Typer CLI:** typer.Exit(code) for clean command termination
- **Subprocess Failures:** RuntimeError from builder if subprocess fails

## Cross-Cutting Concerns

**Logging:**
- Rich console for formatted output
- display_message() shows panels with color-coded message types
- Quiet mode via --quiet flag sets console.quiet = True globally
- Four message types: ERROR (red), SUCCESS (green), INFO (blue), WARNING (yellow)

**Validation:**
- validate_environment() checks before any operation
- Checks: Python version ≥3.11, uv installed, git repo, pyproject.toml, mkdocs.yml (optional), Doxygen (auto-install)
- Required vs optional checks (required failures exit, optional are warnings)

**Authentication:**
- CLI commands with --provider override auto-detection
- GitLab API: tries GITLAB_TOKEN env var first, falls back to CI_JOB_TOKEN
- Git credentials: uses system git config for remote operations

---

*Architecture analysis: 2026-02-07*
