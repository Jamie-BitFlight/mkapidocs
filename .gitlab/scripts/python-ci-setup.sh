#!/bin/sh
# POSIX-compliant sourceable CI setup script for GitLab pipelines
# This script is designed to be sourced, NOT executed directly
#
# Usage in GitLab CI:
#   before_script:
#     - . .gitlab/scripts/python-ci-setup.sh
#
# Configuration via environment variables:
#   INSTALL_PACKAGES      - Space-separated list of system packages to install
#   INSTALL_UV           - Set to "true" to install uv
#   DETECT_CHANGES       - Comma-separated file patterns for change detection (e.g., "*.py")
#   ARTIFACTS_DIR        - Base directory for artifacts (default: .artifacts)
#   ARTIFACT_SUBDIRS     - Comma-separated list of subdirectories to create
#
# Exported variables (available after sourcing):
#   CHANGED_FILES        - Space-separated list of changed files matching pattern
#   COMPARISON_POINT     - Description of git comparison point used

# Guard against accidental direct execution
case "${0}" in
    *python-ci-setup.sh)
        printf '\033[0;31m%s\033[0m\n' "ERROR: This script must be sourced, not executed directly" >&2
        printf '\033[1;33m%s\033[0m\n' "Usage: . .gitlab/scripts/python-ci-setup.sh" >&2
        exit 1
        ;;
esac

# Set error handling for sourced script
set -eu

# Script metadata
SCRIPT_NAME="python-ci-setup.sh"
SCRIPT_VERSION="1.1.0"

# Color definitions (no associative arrays in POSIX sh)
color_green='\033[0;32m'
color_red='\033[0;31m'
color_yellow='\033[1;33m'
color_blue='\033[0;34m'
color_reset='\033[0m'

# Emoji definitions
emoji_success='✅'
emoji_error='❌'
emoji_warning='⚠️'
emoji_info='ℹ️'

# Logging functions
print_success() { printf '%b %b%s%b\n' "$emoji_success" "$color_green" "$*" "$color_reset"; }
print_error() { printf '%b %b%s%b\n' "$emoji_error" "$color_red" "$*" "$color_reset" >&2; }
print_warning() { printf '%b %b%s%b\n' "$emoji_warning" "$color_yellow" "$*" "$color_reset"; }
print_info() { printf '%b %s\n' "$emoji_info" "$*"; }

# Utility function to check command existence
command_exists() { command -v "$1" >/dev/null 2>&1; }

# Note: POSIX sh doesn't support ERR trap, so we rely on 'set -e' instead

# ============================================================================
# FUNCTION DEFINITIONS
# ============================================================================

# Validate GitLab CI environment
validate_gitlab_env() {
    print_info "Validating GitLab CI environment..."

    # Check required variables (space-separated list instead of array)
    missing_vars=""

    if [ -z "${CI_COMMIT_BRANCH:-}" ]; then
        missing_vars="CI_COMMIT_BRANCH"
    fi
    if [ -z "${CI_DEFAULT_BRANCH:-}" ]; then
        if [ -z "$missing_vars" ]; then
            missing_vars="CI_DEFAULT_BRANCH"
        else
            missing_vars="$missing_vars CI_DEFAULT_BRANCH"
        fi
    fi

    if [ -n "$missing_vars" ]; then
        print_error "Missing required GitLab CI variables: $missing_vars"
        print_error "This script must run in a GitLab CI environment"
        return 1
    fi

    print_success "GitLab CI environment validated"
}

# Install system packages
install_packages() {
    # Packages passed as space-separated arguments
    if [ $# -eq 0 ]; then
        return 0
    fi

    print_info "Checking required packages: $*"

    # Check for missing packages
    missing_packages=""
    for package in "$@"; do
        if ! command_exists "$package"; then
            if [ -z "$missing_packages" ]; then
                missing_packages="$package"
            else
                missing_packages="$missing_packages $package"
            fi
        fi
    done

    if [ -z "$missing_packages" ]; then
        print_success "All required packages already installed"
        return 0
    fi

    print_info "Installing missing packages: $missing_packages"

    if command_exists apt-get; then
        apt-get -yq update
        # shellcheck disable=SC2086
        apt-get install -yq $missing_packages
    elif command_exists apk; then
        # shellcheck disable=SC2086
        apk add --no-cache $missing_packages
    else
        print_error "No supported package manager found (apt-get or apk)"
        print_error "Please install manually: $missing_packages"
        return 1
    fi

    print_success "Packages installed successfully"
}

# Install uv if not present
install_uv() {
    if command_exists uv; then
        print_success "uv is already installed ($(uv --version))"
        return 0
    fi

    print_info "Installing uv..."

    # Auto-install curl if needed
    if ! command_exists curl; then
        print_info "curl not found, installing it first..."
        install_packages curl
    fi

    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add to PATH if needed
    case ":${PATH}:" in
        *:"${HOME}/.local/bin":*)
            # Already in PATH
            ;;
        *)
            export PATH="${HOME}/.local/bin:${PATH}"
            print_info "Added ~/.local/bin to PATH"
            ;;
    esac

    if command_exists uv; then
        print_success "uv installed successfully ($(uv --version))"
    else
        print_error "uv installation failed"
        return 1
    fi
}

# Install Python dependencies
install_python_deps() {
    # Auto-install uv if needed
    if ! command_exists uv; then
        print_info "uv not found, installing it first..."
        install_uv
    fi
    export UV_LINK_MODE="copy"
    print_info "Installing Python dependencies..."

    # Determine dependency file
    deps_file="pyproject.toml"
    if [ -f "requirements.txt" ]; then
        deps_file="requirements.txt"
    fi

    if [ ! -f "$deps_file" ]; then
        print_error "No pyproject.toml or requirements.txt found"
        return 1
    fi

    print_info "Using dependency file: $deps_file"
    if [ "${UV_SYSTEM_PYTHON:-false}" = "true" ]; then
        print_info "Using system Python"
    else
        if [ -z "${VIRTUAL_ENV:-}" ] && [ ! -f ".venv/bin/activate" ]; then
            print_info "No virtual environment found, creating one..."
            uv venv
        fi
        set +eu
        . "${VIRTUAL_ENV:-.venv}/bin/activate"
        set -eu
    fi

    # Try to install with --group dev, fallback without if that fails
    if ! uv pip install -q --group dev -r "$deps_file"; then
        uv pip install -q -r "$deps_file"
    fi
}

# Strip leading/trailing whitespace from a string
strip_whitespace() {
    # Use sed for stripping whitespace (POSIX compatible)
    echo "$1" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Detect changed files based on git context
detect_file_changes() {
    patterns="$1"

    # Auto-install git if needed
    if ! command_exists git; then
        print_info "git not found, installing it first..."
        install_packages git
    fi

    print_info "Detecting changed files matching: $patterns"

    # Build grep pattern for file extensions
    grep_pattern=""
    old_ifs="$IFS"
    IFS=','
    for pattern in $patterns; do
        IFS="$old_ifs"
        # Strip whitespace
        pattern=$(strip_whitespace "$pattern")

        # Convert glob pattern to regex (e.g., *.py -> \.py$)
        # First replace * with .*
        regex_pattern=$(echo "$pattern" | sed 's/\*/\.\*/g')
        # Then escape dots
        regex_pattern=$(echo "$regex_pattern" | sed 's/\./\\./g')

        if [ -z "$grep_pattern" ]; then
            grep_pattern="$regex_pattern"
        else
            grep_pattern="$grep_pattern|$regex_pattern"
        fi
    done
    IFS="$old_ifs"

    changed_files=""
    comparison_point=""

    if [ -n "${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-}" ]; then
        # In a merge request - check files changed vs merge base
        print_info "Context: Merge request to $CI_MERGE_REQUEST_TARGET_BRANCH_NAME"

        merge_base=$(git merge-base HEAD "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME")

        changed_files=$(git diff --name-only "$merge_base...HEAD" | grep -E "$grep_pattern" || true)
        comparison_point="merge base ($merge_base)"

    elif [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then
        # On default branch - check files changed since last tag
        print_info "Context: Default branch ($CI_DEFAULT_BRANCH)"

        last_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

        if [ -n "$last_tag" ]; then
            changed_files=$(git diff --name-only "$last_tag...HEAD" | grep -E "$grep_pattern" || true)
            comparison_point="last tag ($last_tag)"
        else
            # No tags yet - list all files matching patterns
            print_warning "No tags found, checking all files"
            # Convert comma-separated patterns to space-separated for git ls-files
            pattern_list=$(echo "$patterns" | sed 's/,/ /g')
            # shellcheck disable=SC2086
            changed_files=$(git ls-files $pattern_list)
            comparison_point="all files (no tags found)"
        fi

    else
        # Regular branch - check files changed vs default branch
        print_info "Context: Branch $CI_COMMIT_BRANCH"

        changed_files=$(git diff --name-only "origin/$CI_DEFAULT_BRANCH...HEAD" | grep -E "$grep_pattern" || true)
        comparison_point="default branch ($CI_DEFAULT_BRANCH)"
    fi

    # Export variables for use in CI scripts
    export CHANGED_FILES="$changed_files"
    export COMPARISON_POINT="$comparison_point"

    # Print summary
    if [ -z "$changed_files" ]; then
        print_warning "No files changed matching patterns since $comparison_point"
    else
        file_count=$(echo "$changed_files" | wc -l)
        print_success "Found $file_count changed file(s) since $comparison_point:"
        echo "$changed_files" | sed 's/^/  - /'
    fi
}

# Create artifact directories
create_artifact_dirs() {
    artifacts_dir="${ARTIFACTS_DIR:-.artifacts}"
    subdirs="$1"

    if [ -z "$subdirs" ]; then
        return 0
    fi

    print_info "Creating artifact directories in $artifacts_dir..."

    # Process comma-separated subdirs
    old_ifs="$IFS"
    IFS=','
    for subdir in $subdirs; do
        IFS="$old_ifs"
        # Strip whitespace
        subdir=$(strip_whitespace "$subdir")

        full_path="$artifacts_dir/$subdir"
        mkdir -p "$full_path"
        print_info "Created: $full_path"
    done
    IFS="$old_ifs"

    print_success "Artifact directories created"
}

# ============================================================================
# AUTOMATIC EXECUTION BASED ON ENVIRONMENT VARIABLES
# ============================================================================
# This section runs automatically when the script is sourced

# Validate GitLab CI environment
validate_gitlab_env

# Execute requested operations based on environment variables
if [ -n "${INSTALL_PACKAGES:-}" ]; then
    # shellcheck disable=SC2086
    install_packages ${INSTALL_PACKAGES}
fi

if [ "${INSTALL_UV:-false}" = "true" ]; then
    install_uv
fi

# Always install Python dependencies for CI
install_python_deps

if [ -n "${DETECT_CHANGES:-}" ]; then
    detect_file_changes "${DETECT_CHANGES}"
fi

if [ -n "${ARTIFACT_SUBDIRS:-}" ]; then
    create_artifact_dirs "${ARTIFACT_SUBDIRS}"
fi

print_success "CI setup completed successfully"
