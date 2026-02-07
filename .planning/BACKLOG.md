# Backlog

> Sourced from codebase analysis: [.planning/codebase/](codebase/)
> Status: **Ungroomed** — items need prioritization and sizing before milestone planning.

---

## Legend

| Priority | Meaning |
|----------|---------|
| P0 | Critical — security risk or data loss |
| P1 | High — blocks reliability or maintainability |
| P2 | Medium — improves quality, worth doing soon |
| P3 | Low — nice to have, do when convenient |

| Size | Meaning |
|------|---------|
| XS | < 1 hour |
| S | 1–3 hours |
| M | 3–8 hours |
| L | 1–2 days |
| XL | 3+ days |

---

## Architecture / Tech Debt

### ARCH-1: Break up generator.py monolith
- **Source:** [CONCERNS.md — Generator Module Monolith](codebase/CONCERNS.md#generator-module-monolith)
- **Priority:** P1 | **Size:** XL
- **Description:** `generator.py` is 1,751 lines mixing git operations, feature detection, YAML merging, template rendering, and CI/CD workflow creation. Extract into focused modules (`git_utils.py`, `ci_manager.py`, separate template rendering from content generation).
- **Value:** Enables isolated testing, reduces cognitive load, unblocks further refactoring.
- **Risk if skipped:** Every new feature or bug fix in this file risks regressions.

### ARCH-2: Simplify YAML merge complexity
- **Source:** [CONCERNS.md — YAML Merge Complexity](codebase/CONCERNS.md#yaml-merge-complexity)
- **Priority:** P2 | **Size:** L
- **Description:** `yaml_utils.py` (664 lines) implements non-destructive YAML merging with ruamel.yaml's CommentedMap/CommentedSeq, manual comment attribute copying, and a recursion depth limit of 50. State tracking for template-owned keys is hard to reason about.
- **Value:** Fewer edge-case bugs when users upgrade mkdocs configs.
- **Risk if skipped:** Fragile but functional — low urgency unless merge bugs surface.

---

## Security

### SEC-1: Fix tarfile extraction path traversal on Python 3.11
- **Source:** [CONCERNS.md — Tarfile Extraction](codebase/CONCERNS.md#tarfile-extraction-with-legacy-python-support)
- **Priority:** P0 | **Size:** S
- **Description:** `validators.py:260-266` skips `filter="data"` on Python 3.11 when extracting Doxygen tarballs. Although the source is official Doxygen releases, a compromised download could exploit path traversal. Either implement a custom filter for 3.11 or validate extracted paths.
- **Value:** Closes a known supply-chain attack surface.

### SEC-2: Restrict environment variables passed to subprocesses
- **Source:** [CONCERNS.md — Process Environment Variable Inheritance](codebase/CONCERNS.md#process-environment-variable-inheritance)
- **Priority:** P2 | **Size:** S
- **Description:** `builder.py:263-264` copies entire `os.environ` to subprocesses. Construct a minimal env with only PATH, PYTHONPATH, and explicitly required variables instead.
- **Value:** Reduces attack surface if a subprocess is compromised.

### SEC-3: Improve git URL parsing robustness
- **Source:** [CONCERNS.md — Git URL Regex Parsing](codebase/CONCERNS.md#git-url-regex-parsing)
- **Priority:** P2 | **Size:** M
- **Description:** `generator.py:196-240` parses git URLs with regex. Replace with `urllib.parse` for HTTP URLs and explicit pattern matching for SSH URLs. Add comprehensive test cases for unusual formats (enterprise instances, non-standard SSH ports, nested GitLab groups).
- **Value:** Correct provider detection for non-standard repository setups.

---

## Error Handling

### ERR-1: Replace bare `except: pass` patterns with logging
- **Source:** [CONCERNS.md — Bare except with pass Pattern](codebase/CONCERNS.md#bare-except-with-pass-pattern)
- **Priority:** P1 | **Size:** XS
- **Description:** Multiple locations silently swallow errors: `yaml_utils.py:124` (YAMLError), `builder.py:113` (TimeoutExpired), `builder.py:185` (OSError/SubprocessError). Replace all with `except Exception as e: logger.debug(...)` at minimum.
- **Value:** Dramatically improves debuggability. Users and developers can see why things failed.

### ERR-2: Add retry logic and error handling to Doxygen installer
- **Source:** [CONCERNS.md — Network Requests Without Comprehensive Error Handling](codebase/CONCERNS.md#network-requests-without-comprehensive-error-handling)
- **Priority:** P1 | **Size:** M
- **Description:** `validators.py:159-208` — GitHub API calls and binary downloads have no retry logic, no resume on partial transfer, and generic error messages. Add exponential backoff retry, validate downloaded files, and distinguish network errors from platform errors.
- **Value:** Reliable automated setup in CI environments with flaky networks.

### ERR-3: Improve pyproject.toml parsing error reporting
- **Source:** [CONCERNS.md — Pyproject Parsing with Fallback to Defaults](codebase/CONCERNS.md#pyproject-parsing-with-fallback-to-defaults)
- **Priority:** P2 | **Size:** S
- **Description:** `project_detection.py:22-41` catches exceptions broadly when reading pyproject.toml and silently falls back to defaults. Warn the user when configuration is incomplete or malformed.
- **Value:** Users discover misconfigured projects early instead of getting wrong docs.

---

## Reliability

### REL-1: Make port conflict resolution cross-platform and explicit
- **Source:** [CONCERNS.md — Port Conflict Resolution via lsof](codebase/CONCERNS.md#port-conflict-resolution-via-lsof)
- **Priority:** P2 | **Size:** M
- **Description:** `builder.py:153-186` kills processes on ports using `lsof -t -i :port`. Silently fails on Windows/minimal environments. Check for `lsof` availability, log which process is being killed, provide Windows alternative, and consider requiring user confirmation.
- **Value:** Serve command works reliably across platforms.

### REL-2: Harden signal handling in builder
- **Source:** [CONCERNS.md — Signal Handler Complexity](codebase/CONCERNS.md#signal-handler-complexity)
- **Priority:** P2 | **Size:** M
- **Description:** `builder.py:85-134` implements complex signal handling for graceful subprocess termination with multiple timeouts and fallback to SIGKILL. Add integration tests that simulate signal handling and document the escalation logic.
- **Value:** Prevents orphaned processes on `serve` command interrupts.

### REL-3: Improve AST-based Typer detection resilience
- **Source:** [CONCERNS.md — AST Parsing for Typer Detection](codebase/CONCERNS.md#ast-parsing-for-typer-detection)
- **Priority:** P3 | **Size:** S
- **Description:** `generator.py:647-689` uses AST parsing to detect Typer apps. Misses dynamic imports, factory functions, and conditional imports. Add heuristic text search as fallback and document limitations.
- **Value:** Fewer false negatives in CLI documentation generation.

### REL-4: Support configurable enterprise domain patterns for provider detection
- **Source:** [CONCERNS.md — Provider Detection from Git Remote](codebase/CONCERNS.md#provider-detection-from-git-remote)
- **Priority:** P3 | **Size:** S
- **Description:** `generator.py:155-240` only detects `github`/`gitlab` in domain strings. Enterprise instances with custom domains fail detection. Allow configuration via pyproject.toml or environment variable.
- **Value:** Enterprise users don't need `--provider` flag every time.

---

## Performance

### PERF-1: Cache feature detection results
- **Source:** [CONCERNS.md — Git Operations for C Code Detection](codebase/CONCERNS.md#git-operations-for-c-code-detection)
- **Priority:** P3 | **Size:** M
- **Description:** `project_detection.py:162-169` runs `git ls-files` on every setup call, which can be slow on large monorepos (10s timeout). Cache results in `.mkapidocs_cache` or similar. Make timeout configurable.
- **Value:** Faster repeated setup/build cycles on large repos.

### PERF-2: Add download resume support to Doxygen installer
- **Source:** [CONCERNS.md — Doxygen Download Not Resumable](codebase/CONCERNS.md#doxygen-download-not-resumable)
- **Priority:** P3 | **Size:** M
- **Description:** `validators.py:183-211` downloads 50MB+ binaries without resume capability. Check for partial downloads and implement HTTP Range-based resume with progress reporting.
- **Value:** Reliable installation on slow/interrupted connections.

---

## Testing

### TEST-1: Add YAML merge edge case tests
- **Source:** [CONCERNS.md — YAML Merge Edge Cases Not Fully Tested](codebase/CONCERNS.md#yaml-merge-edge-cases-not-fully-tested)
- **Priority:** P2 | **Size:** M
- **Description:** Missing test coverage for: malformed YAML structures, mixed types at same key, deep nesting near 50-level limit, unicode/special characters in comments, trailing comment preservation.
- **Value:** Prevents YAML corruption when merging user configs.

### TEST-2: Add builder signal handling integration tests
- **Source:** [CONCERNS.md — Builder Signal Handling Not Integration-Tested](codebase/CONCERNS.md#builder-signal-handling-not-integration-tested)
- **Priority:** P1 | **Size:** L
- **Description:** Signal handlers in `builder.py` (SIGINT/SIGTERM forwarding, timeout handling, process escalation) have no integration tests. Add tests that simulate signals and verify child process cleanup.
- **Value:** Confidence that interactive `serve` command doesn't leak processes.

### TEST-3: Mock git operations consistently in tests
- **Source:** [CONCERNS.md — Git Operations Not Mocked in Tests](codebase/CONCERNS.md#git-operations-not-mocked-in-tests)
- **Priority:** P2 | **Size:** S
- **Description:** Git operations in `generator.py` (git config reading, remote URL parsing) may depend on actual git state. Tests could fail in non-git directories or CI environments with different git state. Add mocks for all git subprocess calls.
- **Value:** Reliable tests across all environments.

### TEST-4: Add network error path tests for Doxygen installer
- **Source:** [CONCERNS.md — Network Error Paths Not Exercised](codebase/CONCERNS.md#network-error-paths-not-exercised)
- **Priority:** P2 | **Size:** M
- **Description:** No tests for: slow/hanging connections, download corruption, GitHub API rate limiting, partial transfer failures. Add tests with mocked httpx responses.
- **Value:** Ensures installer fails gracefully instead of hanging or corrupting.

---

## Quick Reference

| ID | Title | Priority | Size | Category |
|----|-------|----------|------|----------|
| SEC-1 | Fix tarfile path traversal on 3.11 | P0 | S | Security |
| ARCH-1 | Break up generator.py monolith | P1 | XL | Architecture |
| ERR-1 | Replace bare except:pass with logging | P1 | XS | Error Handling |
| ERR-2 | Add retry logic to Doxygen installer | P1 | M | Error Handling |
| TEST-2 | Signal handling integration tests | P1 | L | Testing |
| ARCH-2 | Simplify YAML merge complexity | P2 | L | Architecture |
| SEC-2 | Restrict subprocess env vars | P2 | S | Security |
| SEC-3 | Improve git URL parsing | P2 | M | Security |
| ERR-3 | Improve pyproject parsing errors | P2 | S | Error Handling |
| REL-1 | Cross-platform port conflict resolution | P2 | M | Reliability |
| REL-2 | Harden signal handling in builder | P2 | M | Reliability |
| TEST-1 | YAML merge edge case tests | P2 | M | Testing |
| TEST-3 | Mock git operations in tests | P2 | S | Testing |
| TEST-4 | Network error path tests | P2 | M | Testing |
| PERF-1 | Cache feature detection results | P3 | M | Performance |
| PERF-2 | Download resume for Doxygen | P3 | M | Performance |
| REL-3 | Improve Typer detection resilience | P3 | S | Reliability |
| REL-4 | Configurable enterprise domains | P3 | S | Reliability |

---

*Generated from codebase analysis on 2026-02-07. See [codebase docs](codebase/) for full context.*
