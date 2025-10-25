#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv"]
# ///
"""GitLab CI utility functions."""

import json
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from shutil import which
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import find_dotenv, load_dotenv


@lru_cache(maxsize=1)
def git_path() -> Path:
    """Get the path to git binary (cached, max 1 entry)."""
    if path := which("git"):
        return Path(path)
    raise RuntimeError("git command not found")


@lru_cache(maxsize=1)
def glab_path() -> Path:
    """Get the path to glab binary (cached, max 1 entry)."""
    if path := which("glab"):
        return Path(path)
    raise RuntimeError("glab command not found")


@lru_cache(maxsize=1)
def get_git_origin_url() -> str:
    """Get git origin remote URL (cached)."""
    git = git_path()
    return subprocess.check_output([git, "remote", "get-url", "origin"], text=True).strip()


def parse_git_origin() -> tuple[str, str]:
    """Parse hostname and project path from git origin URL.

    Returns:
        tuple[hostname, project_path]: e.g., ("github.com", "user/repo")
    """
    url = get_git_origin_url()
    # Handle URLs with credentials: https://user:pass@host/path or git@host:path
    if match := re.search(r"(?:@|://(?:[^@]+@)?)([^:/]+)[:/](.+?)(?:\.git)?$", url):
        return match.group(1), match.group(2)
    raise ValueError(f"Could not parse git origin URL: {url}")


def get_git_remote_hostname() -> str:
    """Extract hostname from git origin remote URL."""
    return parse_git_origin()[0]


def get_git_project_path() -> str:
    """Extract project path from git origin remote URL."""
    return parse_git_origin()[1]


@lru_cache(maxsize=1)
def get_gitlab_project_id() -> int:
    """Get GitLab project ID using glab CLI or API."""
    # Try glab first (fastest)
    try:
        glab = glab_path()
        output = subprocess.check_output([glab, "api", "projects/:id"], text=True)
        return int(json.loads(output)["id"])
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        pass  # Fall through to API method

    # Fallback to API
    host, project_path = parse_git_origin()
    api_url = f"https://{host}/api/v4/projects/{quote(project_path, safe='')}"
    req = Request(api_url, headers={"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]})  # noqa: S310
    with urlopen(req) as response:  # noqa: S310
        return int(json.loads(response.read())["id"])


def can_push_to_git_remote() -> bool:
    """Check if git push to remote will succeed with current authentication."""
    git = git_path()
    result = subprocess.run(
        [git, "push", "--dry-run", "--porcelain", "origin", "HEAD"], capture_output=True, text=True, timeout=10
    )
    return result.returncode == 0


def ensure_ci_variables() -> None:
    """Ensure CI variables are correct, fixing gitlab-ci-local fake values."""
    # gitlab-ci-local sets GITLAB_CI="false" and CI_PROJECT_ID="1217"
    if os.environ.get("GITLAB_CI") == "false" or os.environ.get("CI_PROJECT_ID") == "1217":
        host, project_path = parse_git_origin()
        os.environ["CI_PROJECT_ID"] = str(get_gitlab_project_id())
        os.environ["CI_SERVER_HOST"] = host
        os.environ["CI_PROJECT_PATH"] = project_path
        os.environ["CI_API_V4_URL"] = f"https://{host}/api/v4"

    # Set missing variables
    if not os.environ.get("CI_PROJECT_ID"):
        os.environ["CI_PROJECT_ID"] = str(get_gitlab_project_id())
    if not os.environ.get("CI_SERVER_HOST"):
        os.environ["CI_SERVER_HOST"] = get_git_remote_hostname()
    if not os.environ.get("CI_PROJECT_PATH"):
        os.environ["CI_PROJECT_PATH"] = get_git_project_path()
    if not os.environ.get("CI_API_V4_URL"):
        os.environ["CI_API_V4_URL"] = f"https://{os.environ['CI_SERVER_HOST']}/api/v4"


if __name__ == "__main__":
    # Load environment variables from .env files
    load_dotenv()  # Searches for .env in cwd and parents
    load_dotenv(find_dotenv(".gitlab-ci-local-env"))  # Search for gitlab-ci-local specific file in parents

    # Test functions
    print(f"Hostname: {get_git_remote_hostname()}")
    try:
        print(f"Project ID: {get_gitlab_project_id()}")
    except KeyError:
        print("Project ID: (GITLAB_TOKEN not set)")
