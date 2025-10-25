#!/usr/bin/env -S uv --quiet run --active --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv"]
# ///
"""Create GitLab release with semantic versioning."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Import our utility functions
sys.path.insert(0, str(Path(__file__).parent))
from gitlab_ci_utilities import can_push_to_git_remote, ensure_ci_variables


def task_completed(task: str) -> None:
    """Print task completed message."""
    print(f"TASK Completed: {task}")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run command and return result."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def setup_git_for_ci(git: str) -> None:
    """Configure git user and remote URL for CI environment."""
    # Set git config if not already configured
    git_email = subprocess.run([git, "config", "user.email"], capture_output=True, text=True).stdout.strip()
    if not git_email:
        git_email = os.environ.get("GITLAB_USER_EMAIL", "ci@assaabloy.com")
        run([git, "config", "user.email", git_email])
        task_completed(f"Set git user.email: {git_email}")

    git_name = subprocess.run([git, "config", "user.name"], capture_output=True, text=True).stdout.strip()
    if not git_name:
        git_name = os.environ.get("GITLAB_USER_NAME", "Sourcery CI Bot")
        run([git, "config", "user.name", git_name])
        task_completed(f"Set git user.name: {git_name}")

    # Only replace remote URL if current remote doesn't work
    if can_push_to_git_remote():
        task_completed(f"Git configured: {git_name} <{git_email}> (remote already accessible)")
        return

    # Setup authenticated remote URL (CI variables ensured by ensure_ci_variables())
    # Prefer GITLAB_TOKEN/GL_TOKEN (broader permissions) over CI_JOB_TOKEN
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GL_TOKEN") or os.environ.get("CI_JOB_TOKEN")
    if not token:
        raise RuntimeError("Missing GITLAB_TOKEN, GL_TOKEN, or CI_JOB_TOKEN")

    remote_url = f"https://gitlab-ci-token:{token}@{os.environ['CI_SERVER_HOST']}/{os.environ['CI_PROJECT_PATH']}.git"
    run([git, "remote", "set-url", "origin", remote_url])
    task_completed(f"Git configured: {git_name} <{git_email}>")


def ensure_on_branch(git: str) -> None:
    """Ensure git is on a branch, not in detached HEAD state.

    What: Checks if running in GitLab CI and in detached HEAD state, then checks out
          the branch specified by CI_COMMIT_REF_NAME. This is required because
          semantic-release cannot operate in detached HEAD state.

    Expects:
    - git executable path
    - CI environment variable set (indicates GitLab CI)
    - CI_COMMIT_REF_NAME environment variable with branch name
    - Git repository initialized

    Success: Repository is on the specified branch, not detached HEAD.
    Exit code: 0 on success, non-zero if git checkout fails.
    """
    # Only run in CI environment
    if not os.environ.get("CI"):
        return

    # Get branch name from CI environment
    branch_name = os.environ.get("CI_COMMIT_REF_NAME")
    if not branch_name:
        raise RuntimeError("CI_COMMIT_REF_NAME not found in CI environment")

    # Check current branch
    result = subprocess.run([git, "branch", "--show-current"], capture_output=True, text=True)
    current_branch = result.stdout.strip()

    # If already on the correct branch, nothing to do
    if current_branch == branch_name:
        task_completed(f"Already on branch: {branch_name}")
        return

    # Create or reset branch to current HEAD, then switch to it
    # -B creates the branch if it doesn't exist, or resets it to current HEAD if it does
    run([git, "checkout", "-B", branch_name])
    task_completed(f"Checked out branch: {branch_name}")


def calculate_next_version(uv: str) -> str | None:
    """Calculate next semantic version from commit history.

    What: Runs semantic-release in --noop mode to determine if a release is needed
          and what the next version would be based on conventional commits.

    Expects:
    - uv executable path
    - Git repository with conventional commit history (feat:, fix:, etc.)
    - pyproject.toml with [tool.semantic_release] configuration

    Success: Returns version string (e.g., "v0.1.3") if release needed, None if not.
    Exit code: 0 on success. Returns None when "No release will be made" in stderr.
    """
    result = run([uv, "run", "semantic-release", "--noop", "version", "--print-tag"])
    if "No release will be made" in result.stderr:
        return None
    version: str = result.stdout.strip()
    return version


def create_lightweight_tag(git: str, version: str) -> None:
    """Create lightweight git tag for version.

    What: Creates an initial lightweight tag that will be replaced with annotated tag
          after release notes are generated.

    Expects:
    - git executable path
    - version string (e.g., "v0.1.3")
    - Clean git working directory

    Success: Tag visible in `git tag -l`, points to HEAD commit.
    Exit code: 0 on success, non-zero if tag already exists or git fails.
    """
    run([git, "tag", version])
    task_completed(f"Created preliminary tag: {version}")


def generate_changelog(uv: str, version: str, script_dir: Path) -> None:
    """Generate CHANGELOG.md with historical version breakdown.

    What: Runs generate_release_notes.py to create changelog showing all releases
          since the base minor version (e.g., for v0.1.3, shows v0.1.0-v0.1.3).

    Expects:
    - uv executable path
    - version string (e.g., "v0.1.3")
    - script_dir path containing generate_release_notes.py
    - Git tags for historical versions
    - .changelog-config.yaml configuration file

    Success: CHANGELOG.md file created with markdown content, grouped by version.
    Exit code: 0 on success, non-zero if generate-changelog fails or config missing.

    NOTE: uv run is used so that PEP723 can be taken advantage of.
    """
    run([uv, "run", str(script_dir / "generate_release_notes.py"), version])
    task_completed("CHANGELOG.md generated with release notes")


def create_annotated_tag(git: str, version: str) -> None:
    """Replace lightweight tag with annotated tag containing release notes.

    What: Reads CHANGELOG.md and creates an annotated tag with -f (force) to replace
          the lightweight tag created earlier. This stores release notes in git.

    Expects:
    - git executable path
    - version string (e.g., "v0.1.3")
    - CHANGELOG.md file exists with markdown content
    - Lightweight tag already exists

    Success: Annotated tag replaces lightweight tag, `git show <tag>` displays notes.
    Exit code: 0 on success, non-zero if CHANGELOG.md missing or git fails.
    """
    changelog_content = Path("CHANGELOG.md").read_text()
    run([git, "tag", "-f", "-a", version, "-m", changelog_content])
    task_completed(f"Updated to annotatedtag with release notes: {version}")


def build_package(uv: str) -> None:
    """Build Python package distributions.

    What: Runs `uv build` to create wheel and source distribution in dist/ directory.

    Expects:
    - uv executable path
    - pyproject.toml with [build-system] and [project] configuration
    - hatch-vcs for version detection from git tags

    Success: dist/ directory contains .whl and .tar.gz files.
    Exit code: 0 on success, non-zero if build fails or pyproject.toml invalid.
    """
    env = os.environ.copy()
    env["HATCH_BUILD_CLEAN"] = "true"
    run([uv, "build"], env=env)
    task_completed("Built package")


def publish_package(uv: str) -> None:
    """Publish package to GitLab Package Registry."""
    # Prefer GITLAB_TOKEN/GL_TOKEN (broader permissions) over CI_JOB_TOKEN
    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GL_TOKEN") or os.environ.get("CI_JOB_TOKEN")
    if not token:
        raise RuntimeError("Missing GITLAB_TOKEN, GL_TOKEN, or CI_JOB_TOKEN")

    env = os.environ.copy()
    env.update({
        "UV_PUBLISH_URL": f"{os.environ['CI_API_V4_URL']}/projects/{os.environ['CI_PROJECT_ID']}/packages/pypi",
        "UV_PUBLISH_USERNAME": "gitlab-ci-token",
        "UV_PUBLISH_PASSWORD": token,
    })
    run([uv, "publish"], env=env)
    task_completed("Published package")


def push_tag(git: str, version: str) -> None:
    """Push annotated tag to remote repository.

    What: Pushes the version tag to origin, triggering GitLab to recognize the release.

    Expects:
    - git executable path
    - version string (e.g., "v0.1.3")
    - Authenticated remote URL (set by setup_git_for_ci in CI)
    - Annotated tag exists locally

    Success: Tag visible on GitLab repository tags page.
    Exit code: 0 on success, non-zero if push fails (auth, network, conflicts).
    """
    run([git, "push", "origin", version])
    print(f"TASK Completed: Pushed tag: {version}")


def create_gitlab_release(glab: str, version: str) -> None:
    """Create GitLab release with changelog and package artifacts.

    What: Uses glab CLI to create a GitLab release entry with CHANGELOG.md as
          description and attaches dist/ files as release assets.

    Expects:
    - glab executable path
    - version string (e.g., "v0.1.3")
    - CHANGELOG.md file with release notes
    - dist/ directory with .whl and .tar.gz files
    - Tag pushed to remote repository
    - GITLAB_TOKEN in environment or glab auth configured

    Success: Release visible on GitLab project releases page with attached files.
    Exit code: 0 on success, non-zero if glab fails (auth, tag missing, network).
    """
    dist_files = list(Path("dist").glob("*"))
    cmd = [glab, "release", "create", version, "-F", "CHANGELOG.md"] + [str(f) for f in dist_files]
    run(cmd)
    print(f"TASK Completed: Created GitLab release: {version}")


def main() -> None:
    """Execute release workflow.

    Orchestrates the complete release process:
    1. Ensure CI variables are correct (handles gitlab-ci-local)
    2. Check prerequisites (git, glab, uv)
    3. Configure git auth (if token available)
    4. Calculate next version with semantic-release
    5. Create tag, generate changelog, build, publish, and release

    Exit codes:
    - 0: Success or no release needed
    - 1: Error during execution (see stderr)
    """
    # Load environment variables from .env files
    load_dotenv()  # Searches for .env in cwd and parents
    load_dotenv(find_dotenv(".gitlab-ci-local-env"))  # Search for gitlab-ci-local specific file in parents

    # Ensure CI variables are correct (fixes gitlab-ci-local fake values)
    ensure_ci_variables()

    # Check prerequisites
    if not (git := shutil.which("git")):
        raise RuntimeError("git not found")
    if not (glab := shutil.which("glab")):
        raise RuntimeError("glab not found")
    if not (uv := shutil.which("uv")):
        raise RuntimeError("uv not found")

    # Setup git auth if we have a token (CI or local with GITLAB_TOKEN)
    if os.environ.get("GITLAB_TOKEN") or os.environ.get("GL_TOKEN") or os.environ.get("CI_JOB_TOKEN"):
        setup_git_for_ci(git)
        print("Git authentication configured")
    else:
        print("WARNING: No GITLAB_TOKEN, GL_TOKEN, or CI_JOB_TOKEN found - push operations may fail")

    # Ensure we're on a branch (not detached HEAD) before running semantic-release
    ensure_on_branch(git)

    # Calculate next version
    next_version = calculate_next_version(uv)
    if not next_version:
        print("No release needed")
        sys.exit(0)

    print(f"Next version: {next_version}")

    # Create lightweight tag
    create_lightweight_tag(git, next_version)

    # Generate release notes
    generate_changelog(uv, next_version, Path(__file__).parent)

    # Update to annotated tag with release notes
    create_annotated_tag(git, next_version)

    # Build package
    build_package(uv)

    # Publish package if we have credentials
    if os.environ.get("GITLAB_TOKEN") or os.environ.get("GL_TOKEN") or os.environ.get("CI_JOB_TOKEN"):
        try:
            publish_package(uv)
        except Exception as e:
            print(f"WARNING: Package publish failed: {e}")
            print("Continuing with release...")

    # Push tag
    push_tag(git, next_version)

    # Create GitLab release
    create_gitlab_release(glab, next_version)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}", file=sys.stderr)
        sys.exit(1)
