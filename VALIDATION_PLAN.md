# Documentation Validation Plan

## Overview

This document outlines the comprehensive validation framework for ensuring documentation quality across all stages of generation and maintenance.

## Validation Requirements

### 1. Doxygen C/C++ Documentation
- **Goal**: Verify C/C++ code is properly documented
- **Checks**:
  - All public functions have `@brief` descriptions
  - All parameters have `@param` documentation
  - Return values have `@return` documentation
  - Structs and enums are documented
- **Coverage target**: 70% minimum
- **Implementation**: Parse Doxygen XML output from mkdoxy plugin

### 2. Python API Documentation
- **Goal**: Verify Python modules have complete docstrings
- **Checks**:
  - All public functions/classes/methods have docstrings
  - Docstrings follow Google-style format
  - Type hints are present and correct
  - Examples included where appropriate
- **Coverage target**: 80% minimum
- **Implementation**: Use griffe (same engine as mkdocstrings) + interrogate

### 3. CLI Documentation
- **Goal**: Verify Typer CLI is fully documented
- **Checks**:
  - All commands have help text
  - All arguments are documented
  - All options are documented
  - Examples provided for complex commands
- **Coverage target**: 100%
- **Implementation**: Introspect Typer app, compare against rendered docs

### 4. Supporting Documents
- **Required**:
  - README.md (project overview)
  - install.md (installation instructions)
  - quick-start-guide.md (getting started quickly)
  - contributing.md (contribution guidelines)
  - LICENSE (license file)
- **Optional**:
  - publishing.md (release process)
  - CHANGELOG.md (version history)
  - ARCHITECTURE.md (design documentation)
- **Implementation**: File existence checks + template generation

### 5. Navigation and Links
- **Checks**:
  - All nav items point to existing files
  - No broken internal links
  - No orphaned documentation files
  - Logical navigation hierarchy
- **Implementation**: Parse mkdocs.yml nav + HTML link checking

## Validation Stages

### Stage 1: Pre-Generation Validation
**When**: Before running `setup_documentation()`

**Checks**:
- pyproject.toml exists and is valid TOML
- Git repository is initialized
- Existing docstrings follow Google style
- C/C++ headers have documentation (if C code detected)

**Implementation**:
```python
def validate_prerequisites(repo_path: Path) -> ValidationResult:
    checks = []
    checks.append(check_pyproject_exists(repo_path))
    checks.append(check_git_repo(repo_path))
    checks.append(check_docstring_style(repo_path))
    if detect_c_code(repo_path):
        checks.append(check_c_headers(repo_path))
    return aggregate_results(checks)
```

### Stage 2: During Generation Validation
**When**: During `setup_documentation()` execution

**Checks**:
- Files created successfully
- TOML updates don't break syntax
- YAML generation is valid
- Jinja2 templates render without errors

**Implementation**: Add try/except blocks with specific error messages

### Stage 3: Post-Generation Validation
**When**: After `setup_documentation()` completes

**Checks**:
- `mkdocs build --strict` succeeds
- site/ directory structure correct
- All expected HTML files exist
- API reference pages have content
- No build warnings/errors

**Implementation**:
```python
def validate_build(repo_path: Path) -> BuildValidationResult:
    result = subprocess.run(
        ["mkdocs", "build", "--strict"],
        capture_output=True,
        text=True,
        cwd=repo_path
    )
    return parse_build_output(result)
```

### Stage 4: Continuous Validation
**When**: Ongoing during development

**Methods**:
- Pre-commit hook: Check docstring coverage on changed files
- CI/CD job: Full validation on every commit/MR
- Watch mode: Live validation during documentation writing
- Scheduled: Daily link checking for external URLs

## Implementation Structure

### File Organization
```
packages/python_docs_init/
├── validate.py              # Main validation orchestration
├── validators/
│   ├── __init__.py
│   ├── build.py            # mkdocs build validation
│   ├── python_api.py       # Python docstring validation
│   ├── c_api.py            # Doxygen/C validation
│   ├── cli.py              # Typer CLI validation
│   ├── links.py            # Link checker
│   └── coverage.py         # Coverage aggregation
├── reporters/
│   ├── __init__.py
│   ├── console.py          # Rich console output
│   ├── json.py             # JSON report format
│   ├── junit.py            # JUnit XML format
│   └── markdown.py         # Markdown report format
└── templates/
    ├── install.md.j2
    ├── quick-start-guide.md.j2
    ├── contributing.md.j2
    └── publishing.md.j2
```

### Dependencies to Add
```toml
[project.optional-dependencies]
validation = [
    "griffe>=1.0.0",          # Python API introspection
    "interrogate>=1.7.0",     # Docstring coverage
    "lxml>=5.0.0",            # XML parsing for Doxygen
    "beautifulsoup4>=4.12.0", # HTML parsing
    "watchdog>=3.0.0",        # File watching for watch mode
]
```

## CLI Commands

### validate
Comprehensive validation of existing documentation.

```bash
python_docs_init validate /path/to/repo [OPTIONS]

Options:
  --check [all|build|python|c|cli|links|coverage]  Specific check to run
  --format [console|json|junit|markdown]            Output format
  --strict                                          Fail on warnings
  --min-python-coverage INT                         Python coverage threshold
  --min-c-coverage INT                              C coverage threshold
  --output FILE                                     Write report to file
```

### generate-doc
Generate missing supporting documentation from templates.

```bash
python_docs_init generate-doc DOCNAME [OPTIONS]

Arguments:
  DOCNAME: One of install, quick-start-guide, contributing, publishing

Options:
  --template [basic|detailed]  Template variant to use
  --force                      Overwrite existing file
```

### watch
Continuous validation with live preview.

```bash
python_docs_init watch /path/to/repo [OPTIONS]

Options:
  --port INT          Port for mkdocs serve (default: 8000)
  --no-serve          Don't run mkdocs serve
```

### preview
Build and serve documentation with validation.

```bash
python_docs_init preview /path/to/repo [OPTIONS]

Options:
  --port INT          Port for server (default: 8000)
  --strict            Enable strict validation
```

## Validation Report Format

### Console Output
```
Documentation Validation Report
================================

✅ Build Status: SUCCESS
   - mkdocs build completed in 0.89s
   - 0 errors, 2 warnings

✅ Python API Documentation: 85% coverage
   - 45/50 public functions documented
   - Missing docstrings: 5 functions

   Undocumented:
     • python_picotool.flash.write_block() [line 45]
     • python_picotool.flash.read_block() [line 67]
     • python_picotool.usb.reset_device() [line 123]

   Quick fix:
     uv run interrogate -v packages/python_picotool

⚠️  C API Documentation: 65% coverage
   - 13/20 functions documented
   - Missing @brief: 3 functions
   - Missing @param: 4 functions

   Undocumented:
     • uart_init() in source/uart.c [line 34]
     • i2c_transfer() in source/i2c.c [line 67]

   Example fix:
     /**
      * @brief Initialize UART peripheral
      * @param uart_id UART peripheral ID (0 or 1)
      * @param baud_rate Baud rate in bits per second
      * @return 0 on success, -1 on error
      */

✅ CLI Documentation: 100% coverage
   - 8/8 commands documented
   - All arguments documented
   - All options documented

⚠️  Supporting Documents
   - ✅ README.md exists
   - ✅ LICENSE exists
   - ❌ install.md missing
   - ❌ quick-start-guide.md missing
   - ❌ contributing.md missing
   - ❌ publishing.md missing

   Generate missing:
     python_docs_init generate-doc install
     python_docs_init generate-doc quick-start-guide
     python_docs_init generate-doc contributing
     python_docs_init generate-doc publishing

✅ Navigation & Links
   - 0 broken internal links
   - All nav items resolve

════════════════════════════════════════════════════════════════

Overall: 4/6 checks passed, 2 warnings

Run with --strict to fail on warnings
```

### JSON Output
```json
{
  "timestamp": "2025-10-26T20:30:00Z",
  "repository": "/home/user/python_picotool",
  "overall_status": "warning",
  "checks": {
    "build": {
      "status": "pass",
      "duration": 0.89,
      "errors": 0,
      "warnings": 2
    },
    "python_api": {
      "status": "pass",
      "coverage": 85.0,
      "documented": 45,
      "total": 50,
      "missing": [
        {
          "path": "python_picotool.flash.write_block",
          "line": 45,
          "type": "function"
        }
      ]
    },
    "c_api": {
      "status": "warning",
      "coverage": 65.0,
      "documented": 13,
      "total": 20,
      "missing": [
        {
          "name": "uart_init",
          "file": "source/uart.c",
          "line": 34,
          "missing_tags": ["brief", "param"]
        }
      ]
    },
    "cli": {
      "status": "pass",
      "coverage": 100.0,
      "commands": 8,
      "documented": 8
    },
    "supporting_docs": {
      "status": "warning",
      "required": {
        "README.md": true,
        "install.md": false,
        "quick-start-guide.md": false,
        "contributing.md": false,
        "LICENSE": true
      }
    },
    "links": {
      "status": "pass",
      "broken_links": 0
    }
  }
}
```

## Configuration

Add to `pyproject.toml`:

```toml
[tool.python_docs_init]
# Validation thresholds
min_python_coverage = 80
min_c_coverage = 70
min_cli_coverage = 100

# Validation behavior
strict_mode = false
require_examples = true
check_external_links = false

# Required supporting documents
required_docs = [
    "README.md",
    "install.md",
    "quick-start-guide.md",
    "contributing.md",
]

# Optional supporting documents
optional_docs = [
    "publishing.md",
    "CHANGELOG.md",
    "ARCHITECTURE.md",
]
```

## CI/CD Integration

### GitLab CI Template
Add to `.gitlab/workflows/pages.gitlab-ci.yml`:

```yaml
docs-validate:
  stage: test
  image: python:3.11
  before_script:
    - pip install uv
    - uv sync --extra docs
  script:
    - python_docs_init validate . --strict --format junit --output validation-report.xml
    - python_docs_init validate . --format json --output validation-report.json
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  artifacts:
    reports:
      junit: validation-report.xml
    paths:
      - validation-report.json
    when: always
```

### Pre-commit Hook
Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: docstring-coverage
      name: Check docstring coverage
      entry: uv run python_docs_init validate --check python --min-coverage 80
      language: system
      pass_filenames: false
      files: \.py$
```

## Implementation Roadmap

### Phase 1: Core Validation (Week 1)
- [ ] Create validation module structure
- [ ] Implement build validator (mkdocs --strict checking)
- [ ] Implement Python API validator using griffe
- [ ] Implement basic link checker
- [ ] Add validate command to CLI
- [ ] Create console reporter with Rich
- [ ] Test on python_picotool

### Phase 2: Enhanced Validation (Week 2)
- [ ] Implement C API validator with Doxygen XML parsing
- [ ] Implement CLI validator using Typer introspection
- [ ] Add supporting docs checker
- [ ] Create JSON and JUnit reporters
- [ ] Add configuration via pyproject.toml
- [ ] Test on usb_powertools (has C code)

### Phase 3: Documentation Generation (Week 3)
- [ ] Create templates for install.md, quick-start-guide.md, contributing.md, publishing.md
- [ ] Implement generate-doc command
- [ ] Add template customization options
- [ ] Update index.md template to link supporting docs
- [ ] Enhance navigation structure in mkdocs.yml template
- [ ] Test on all 5 repositories

### Phase 4: CI/CD Integration (Week 4)
- [ ] Update gitlab-ci.yml template to include validation
- [ ] Create pre-commit hook for docstring coverage
- [ ] Add watch mode for live validation
- [ ] Create markdown and JUnit reporters
- [ ] Add validation badges
- [ ] Documentation and examples
- [ ] Final testing and deployment

## Testing Strategy

### Unit Tests
```python
# Test each validator independently
def test_python_api_validator():
    result = validate_python_api(fixture_project)
    assert result.coverage >= 80
    assert len(result.missing) == 0

def test_c_api_validator():
    result = validate_c_api(fixture_project_with_c)
    assert result.coverage >= 70
```

### Integration Tests
```python
# Test on real projects
def test_validate_python_picotool():
    result = validate_documentation(python_picotool_path)
    assert result.overall_status in ["pass", "warning"]

def test_validate_usb_powertools():
    result = validate_documentation(usb_powertools_path)
    assert result.c_api_coverage >= 70
```

### Test Fixtures
Create sample projects:
- `tests/fixtures/complete_project/` - 100% coverage, all docs
- `tests/fixtures/minimal_project/` - bare minimum
- `tests/fixtures/missing_python_docs/` - missing Python docstrings
- `tests/fixtures/missing_c_docs/` - missing C documentation
- `tests/fixtures/broken_links/` - internal link issues

## Success Criteria

✅ **Build Validation**
- mkdocs build --strict succeeds
- Zero build errors
- Warnings reported but don't fail

✅ **Coverage Validation**
- Python API ≥ 80% documented
- C API ≥ 70% documented (if applicable)
- CLI 100% documented (if applicable)

✅ **Document Validation**
- All required supporting docs exist
- No broken internal links
- Navigation structure complete

✅ **Integration Validation**
- CI/CD pipeline includes validation
- Pre-commit hooks work
- Reports generated in multiple formats

✅ **User Experience**
- Clear, actionable error messages
- Suggestions for fixes provided
- Quick commands to generate missing docs
