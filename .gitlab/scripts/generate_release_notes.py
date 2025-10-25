#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["generate-changelog>=0.16.0"]
# ///
"""Generate release notes using generate-changelog with patch release logic."""

import re
import shutil
import subprocess
import sys

from click.testing import CliRunner
from generate_changelog import cli

if not (git := shutil.which("git")):
    raise RuntimeError("git command not found")

if not (len(sys.argv) >= 2 and (version := sys.argv[1])):
    version = subprocess.run(
        [git, "describe", "--tags", "--exact-match"], check=True, capture_output=True, text=True
    ).stdout.strip()

if not re.match(r"^v?\d+\.\d+\.\d+.*", version):
    raise RuntimeError(f"Invalid version: {version}")
# Calculate base minor version (v0.1.3 -> v0.1.0, v0.2.0 -> v0.2.0)
base_minor = re.sub(r"^v?(\d+\.\d+).*", r"v\1.0", version)

result = subprocess.run(
    [git, "describe", "--tags", "--abbrev=0", "--first-parent", f"{base_minor}^"],
    check=True,
    capture_output=True,
    text=True,
)
if not re.match(r"^v?\d+\.\d+\.\d+.*", starting_tag := result.stdout.strip()):
    raise RuntimeError(f"Invalid starting tag: {result.stdout}")

print("Starting tag:", starting_tag)
print("Base minor:", base_minor)
runner = CliRunner()
click_result = runner.invoke(cli.cli, ["--starting-tag", starting_tag])
if click_result.exit_code != 0:
    raise RuntimeError(f"Failed to generate release notes: {click_result.stderr}")
print(click_result.stdout)
