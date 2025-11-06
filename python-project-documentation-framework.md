# Python Project Documentation Framework
## Automated MkDocs Documentation Generation and GitLab Pages Deployment

**Version:** 1.0
**Last Updated:** October 2025
**Status:** Production Ready

---

## Executive Summary

This framework standardizes documentation generation for Python projects using MkDocs Material, mkdocstrings, and GitLab CI/CD. It enables automatic API documentation generation from Python docstrings, professional documentation websites, and seamless GitLab Pages deployment.

**Key Benefits:**
- **Zero-maintenance API docs**: Automatically generated from Python docstrings
- **Professional appearance**: Material Design theme with search, navigation, and social cards
- **CI/CD integration**: Automatic deployment to GitLab Pages on every commit
- **Developer-friendly**: Write docs in Markdown alongside code
- **Type-safe**: Integrates with Python type hints for accurate documentation

**Sources:**
- MkDocs official documentation: `/mkdocs/mkdocs` (Context7, 529 code snippets, trust score 7.6)
- Material for MkDocs: `/squidfunk/mkdocs-material` (932 code snippets)
- MkDocstrings: `/mkdocstrings/mkdocstrings` (91 code snippets, trust score 7.5)
- GitLab CI/CD YAML reference: https://docs.gitlab.com/ci/yaml/#pages
- Real-world implementations: Typer (fastapi/typer), multiple production deployments

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Core Configuration](#core-configuration)
5. [GitLab CI/CD Setup](#gitlab-cicd-setup)
6. [Advanced Features](#advanced-features)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Alternative Approaches](#alternative-approaches)

---

## 1. Architecture Overview

### Documentation Stack

```
┌─────────────────────────────────────────┐
│   Python Source Code + Docstrings      │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│        mkdocstrings Plugin               │
│   (Extracts API documentation)          │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│          MkDocs Core                     │
│  (Static site generator)                │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│      Material for MkDocs Theme          │
│  (UI/UX, navigation, search)            │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│         GitLab CI/CD Pipeline           │
│  (Build + Deploy to Pages)              │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│         GitLab Pages                     │
│  (Public documentation site)            │
└─────────────────────────────────────────┘
```

### How It Works

1. **Write Code**: Document your Python code using Google-style docstrings
2. **Write Guides**: Create Markdown files in `docs/` for tutorials and guides
3. **Configure MkDocs**: Define navigation and plugin options in `mkdocs.yml`
4. **Commit Changes**: Push to main branch
5. **Automatic Build**: GitLab CI runs `mkdocs build`
6. **Automatic Deploy**: Built site deploys to GitLab Pages
7. **Access Docs**: Visit `https://<namespace>.gitlab.io/<project>/`

---

## 2. Prerequisites

### Required Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.5.0",
    "mkdocstrings[python]>=0.26.0",
    "mkdocs-material-extensions>=1.3.0",
]
```

**Rationale:**
- **mkdocs-material**: Most popular theme, 5M+ monthly downloads (verified from Exa search)
- **mkdocstrings[python]**: Auto-generates API docs from Python code
- **Version pinning**: Use `>=` for minor updates, test major versions separately

### Installation

```bash
# Install documentation dependencies
uv pip install -e ".[docs]"

# Or with pip
pip install -e ".[docs]"
```

---

## 3. Project Structure

### Standard Directory Layout

```
project_root/
├── docs/                          # Documentation source files
│   ├── index.md                   # Homepage
│   ├── getting-started.md         # Installation & quickstart
│   ├── user-guide/                # User-facing documentation
│   │   ├── installation.md
│   │   ├── cli-reference.md
│   │   └── troubleshooting.md
│   ├── api-reference/             # API documentation (auto-generated)
│   │   └── index.md               # API overview page
│   ├── developer-guide/           # Contributing, architecture
│   │   ├── contributing.md
│   │   └── architecture.md
│   ├── assets/                    # Images, CSS, JS
│   │   ├── images/
│   │   ├── stylesheets/
│   │   └── javascripts/
│   └── .pages                     # Optional: mkdocs-awesome-pages config
│
├── packages/your_package/         # Python source code
│   ├── __init__.py
│   ├── cli.py
│   └── core/
│       ├── __init__.py
│       └── module.py
│
├── mkdocs.yml                     # MkDocs configuration
├── .gitlab-ci.yml                 # CI/CD pipeline
├── pyproject.toml                 # Project metadata
└── README.md                      # Repository README
```

**Key Principles:**
- Keep docs/ separate from source code
- Use semantic folder names (user-guide/, api-reference/)
- Place assets in docs/assets/ for proper resolution

---

## 4. Core Configuration

### Complete mkdocs.yml Template

```yaml
# Site metadata
site_name: Your Project Name
site_description: Brief project description (appears in meta tags)
site_author: Your Name or Organization
site_url: https://<namespace>.gitlab.io/<project>/

# Repository
repo_url: https://gitlab.com/<namespace>/<project>
repo_name: <namespace>/<project>
edit_uri: -/edit/main/docs/  # GitLab edit path

# Copyright
copyright: Copyright &copy; 2025 Your Organization

# Theme configuration
theme:
  name: material
  language: en

  # Color scheme
  palette:
    # Light mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode

    # Dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode

  # Font configuration
  font:
    text: Roboto
    code: Roboto Mono

  # Icon configuration
  icon:
    repo: fontawesome/brands/gitlab
    edit: material/pencil
    view: material/eye

  # Features
  features:
    - announce.dismiss              # Dismissable announcements
    - content.action.edit           # Edit button on pages
    - content.action.view           # View source button
    - content.code.copy             # Copy button for code blocks
    - content.code.annotate         # Code annotations
    - content.tabs.link             # Link tabs across pages
    - content.tooltips              # Improved tooltips
    - navigation.expand             # Expand navigation by default
    - navigation.footer             # Footer navigation
    - navigation.indexes            # Section index pages
    - navigation.instant            # Instant loading (SPA-like)
    - navigation.instant.prefetch   # Prefetch pages for speed
    - navigation.instant.progress   # Show loading progress bar
    - navigation.path               # Breadcrumb navigation
    - navigation.sections           # Group navigation sections
    - navigation.tabs               # Top-level tabs
    - navigation.tabs.sticky        # Sticky navigation tabs
    - navigation.top                # Back-to-top button
    - navigation.tracking           # Anchor tracking in URL
    - search.highlight              # Highlight search terms
    - search.share                  # Share search link
    - search.suggest                # Search suggestions
    - toc.follow                    # Follow TOC with scroll
    - toc.integrate                 # Integrate TOC in navigation

# Plugins
plugins:
  - search:
      separator: '[\s\-,:!=\[\]()"`/]+|\.(?!\d)|&[lg]t;|(?!\b)(?=[A-Z][a-z])'
      lang:
        - en

  - mkdocstrings:
      default_handler: python
      handlers:
        python:
          options:
            # General options
            show_source: true
            show_root_heading: true
            show_root_full_path: false
            show_object_full_path: false
            show_category_heading: true
            show_symbol_type_heading: true
            show_symbol_type_toc: true

            # Members options
            members_order: source
            group_by_category: true
            show_submodules: true

            # Docstrings options
            docstring_style: google
            docstring_section_style: table
            merge_init_into_class: true
            show_if_no_docstring: false

            # Signatures options
            show_signature: true
            show_signature_annotations: true
            separate_signature: true
            line_length: 80

            # Additional options
            show_bases: true
            show_inheritance_diagram: false

  - git-revision-date-localized:
      enable_creation_date: true
      type: date

# Markdown extensions
markdown_extensions:
  # Python Markdown extensions
  - abbr                    # Abbreviations
  - admonition              # Call-outs
  - attr_list               # Add HTML attributes
  - def_list                # Definition lists
  - footnotes               # Footnotes
  - md_in_html              # Markdown in HTML
  - tables                  # Tables
  - toc:
      permalink: true
      permalink_title: Anchor link to this section
      toc_depth: 3

  # PyMdown Extensions
  - pymdownx.arithmatex:
      generic: true
  - pymdownx.betterem:
      smart_enable: all
  - pymdownx.caret          # Superscript
  - pymdownx.mark           # Highlighting
  - pymdownx.tilde          # Strikethrough
  - pymdownx.critic         # Track changes
  - pymdownx.details        # Collapsible admonitions
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
      use_pygments: true
  - pymdownx.inlinehilite   # Inline code highlighting
  - pymdownx.keys           # Keyboard keys
  - pymdownx.magiclink:
      repo_url_shortener: true
      repo_url_shorthand: true
      social_url_shorthand: true
      normalize_issue_symbols: true
  - pymdownx.smartsymbols   # Smart symbols
  - pymdownx.snippets:
      check_paths: true
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.tasklist:
      custom_checkbox: true

# Navigation structure
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - User Guide:
      - user-guide/installation.md
      - user-guide/cli-reference.md
      - user-guide/troubleshooting.md
  - API Reference:
      - api-reference/index.md
      - Core: api-reference/core.md
      - Models: api-reference/models.md
  - Developer Guide:
      - developer-guide/contributing.md
      - developer-guide/architecture.md

# Extra configuration
extra:
  version:
    provider: mike  # Optional: versioning support
  social:
    - icon: fontawesome/brands/gitlab
      link: https://gitlab.com/<namespace>/<project>
    - icon: fontawesome/brands/python
      link: https://pypi.org/project/<project>/
  generator: false  # Hide "Made with Material for MkDocs"

# Extra CSS/JS (optional)
extra_css:
  - assets/stylesheets/extra.css

extra_javascript:
  - assets/javascripts/extra.js
```

**Configuration Breakdown:**

- **site_url**: REQUIRED for GitLab Pages (pattern: `https://<namespace>.gitlab.io/<project>/`)
- **repo_url/edit_uri**: Enables "Edit this page" links
- **theme.features**: Modern UX features from Material theme
- **plugins.mkdocstrings**: Auto-generates API docs from Python docstrings
- **markdown_extensions**: Enhanced Markdown capabilities (tables, admonitions, code highlighting)
- **nav**: Explicit navigation structure (order matters)

---

## 5. GitLab CI/CD Setup

### Complete .gitlab-ci.yml Template

```yaml
# Workflow rules - when to run pipeline
workflow:
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH  # Only on main/master
      when: always
    - if: $CI_MERGE_REQUEST_IID                     # On merge requests
      when: always
    - when: never                                    # Explicit deny for other cases

# Stages definition
stages:
  - build
  - deploy

# Variables
variables:
  PYTHON_VERSION: "3.11"

# Build documentation job
build:docs:
  stage: build
  image: python:${PYTHON_VERSION}-slim

  before_script:
    # Install uv for fast dependency management
    - pip install uv
    # Install project with documentation dependencies
    - uv pip install --system -e ".[docs]"

  script:
    # Build documentation
    - mkdocs build --strict --verbose
    # Verify build output
    - test -f site/index.html || (echo "Build failed - no index.html" && exit 1)

  artifacts:
    paths:
      - site/
    expire_in: 1 hour

  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_MERGE_REQUEST_IID

  tags:
    - docker

# Deploy to GitLab Pages
pages:
  stage: deploy
  image: alpine:latest

  script:
    # GitLab Pages requires 'public/' directory
    - mv site public
    # Verify deployment artifact
    - ls -la public/

  artifacts:
    paths:
      - public
    expire_in: never  # Pages artifacts don't expire

  pages:
    path_prefix: ""  # No path prefix (root deployment)

  environment:
    name: production
    url: https://<namespace>.gitlab.io/<project>/

  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: on_success

  needs:
    - build:docs

  tags:
    - docker
```

**Key GitLab Pages Requirements (from GitLab CI YAML reference):**

1. **Job name**: Either `pages` or job with `pages: true` property
2. **Artifact path**: Must publish `public/` directory
3. **Branch restriction**: Typically `$CI_DEFAULT_BRANCH` (main/master)
4. **index.html**: Must exist in root of published directory

**Pipeline Flow:**
1. `build:docs` stage: Install deps, run `mkdocs build`, save `site/` artifact
2. `pages` stage: Rename `site/` to `public/`, publish as GitLab Pages artifact
3. GitLab automatically deploys `public/` to Pages infrastructure

---

## 6. Advanced Features

### 6.1 API Documentation with mkdocstrings

**Create API reference pages** (e.g., `docs/api-reference/core.md`):

```markdown
# Core Module Reference

## PicoDeviceDiscovery

::: python_picotool.core.device.PicoDeviceDiscovery
    options:
      show_source: true
      members:
        - find_device
        - list_devices
      show_root_heading: false
      heading_level: 3

## PicobootFlasher

::: python_picotool.core.flasher.PicobootFlasher
    options:
      show_source: true
      members: true
      show_root_heading: false
      heading_level: 3
```

**Syntax:** `::: <module_path>`

**Options:**
- `show_source`: Include source code
- `members`: Auto-document members (True/False/list)
- `show_root_heading`: Include class/module heading
- `heading_level`: Markdown heading level (1-6)

### 6.2 Social Cards (Material for MkDocs Insiders)

Material Insiders feature for professional social media previews:

```yaml
plugins:
  - social:
      cards_layout: default/variant
      cards_layout_options:
        background_color: "#4051b5"
        background_image: docs/assets/images/background.png
        font_family: "Roboto"
        logo: docs/assets/images/logo.png
```

**Requires**: Material for MkDocs Insiders (paid sponsorship)
**Generates**: Open Graph images for every page
**Benefit**: Professional appearance when shared on social media

### 6.3 Documentation Versioning (Mike)

For versioned API documentation:

```bash
# Install mike
pip install mike

# Deploy version
mike deploy --push --update-aliases 1.0 latest

# Set default version
mike set-default latest
```

```yaml
# mkdocs.yml
extra:
  version:
    provider: mike
    default: latest
```

**Use case**: Maintain docs for multiple release versions

### 6.4 Custom Styling

**docs/assets/stylesheets/extra.css**:

```css
/* Brand color overrides */
:root {
  --md-primary-fg-color: #4051b5;
  --md-accent-fg-color: #ff1744;
}

/* Code block styling */
.highlight code {
  font-size: 0.9rem;
  line-height: 1.5;
}

/* Custom admonition */
.admonition.note {
  border-left-color: var(--md-primary-fg-color);
}
```

---

## 7. Best Practices

### 7.1 Docstring Style

**Use Google-style docstrings** (configured in mkdocs.yml):

```python
def flash_firmware(
    device: DeviceInfo,
    firmware_path: Path,
    *,
    dry_run: bool = False,
    no_reboot: bool = False,
) -> bool:
    """Flash UF2 firmware to Pico device.

    Validates firmware compatibility, uploads to device memory,
    and optionally reboots device into application mode.

    Args:
        device: Target device information including serial and USB port.
        firmware_path: Path to UF2 firmware file to flash.
        dry_run: Validate firmware without flashing (default: False).
        no_reboot: Skip automatic reboot after flashing (default: False).

    Returns:
        True if flash succeeded, False otherwise.

    Raises:
        DeviceNotFoundError: Device not in BOOTSEL mode or disconnected.
        FirmwareValidationError: UF2 file invalid or incompatible chip family.
        FlashOperationError: Flash operation failed mid-transfer.

    Example:
        >>> device = PicoDeviceDiscovery.find_device(identifier)
        >>> flash_firmware(device, Path("firmware.uf2"))
        True

    Note:
        Firmware validation checks UF2 family ID against device chip type.
        RP2040 and RP2350 have different family IDs and are not interchangeable.
    """
    pass
```

**Key sections:**
- Brief summary (first line)
- Extended description (optional paragraph)
- Args/Parameters
- Returns
- Raises
- Examples
- Notes/Warnings

### 7.2 Documentation Structure

**Organize by audience:**

- **User-facing**: Installation, CLI usage, troubleshooting
- **API reference**: Auto-generated from docstrings
- **Developer-facing**: Contributing, architecture, testing

**Write progressively:**
1. Start with getting-started guide (quick win)
2. Add comprehensive user guides
3. Generate API reference automatically
4. Document architecture and design decisions last

### 7.3 CI/CD Optimization

**Caching for faster builds:**

```yaml
build:docs:
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - .cache/pip/
      - .venv/
```

**Parallel MR documentation:**

```yaml
review:docs:
  stage: deploy
  extends: .pages
  environment:
    name: review/$CI_COMMIT_REF_NAME
    url: https://<namespace>.gitlab.io/<project>/-/jobs/$CI_JOB_ID/artifacts/public/index.html
    on_stop: stop_review
  rules:
    - if: $CI_MERGE_REQUEST_IID
```

### 7.4 Quality Gates

**Enforce documentation quality:**

```yaml
test:docs:
  stage: build
  script:
    # Strict build (fail on warnings)
    - mkdocs build --strict
    # Check for broken links
    - pip install linkchecker
    - linkchecker site/
  allow_failure: false
```

---

## 8. Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `pages` job fails with "No public/ directory" | Artifact path incorrect | Ensure `mv site public` in pages job |
| 404 on GitLab Pages | `site_url` incorrect | Match `site_url` to GitLab Pages pattern |
| API docs not generating | mkdocstrings config error | Verify `::: module.path` syntax, check module imports |
| Theme not loading | Missing dependencies | Run `pip install mkdocs-material[imaging]` |
| Build fails on CI but works locally | Dependency mismatch | Pin versions in pyproject.toml, use `uv` for reproducibility |

### Debugging Commands

```bash
# Serve docs locally with live reload
mkdocs serve

# Build with verbose output
mkdocs build --verbose --strict

# Validate config
mkdocs get-config

# Check plugin versions
pip show mkdocs mkdocs-material mkdocstrings
```

---

## 9. Alternative Approaches

### 9.1 Portray (Integrated Approach)

**Tool**: Portray by Timothy Crosley
**Website**: https://timothycrosley.github.io/portray/

Portray combines MkDocs and pdoc3 into single tool:

```toml
# pyproject.toml
[tool.portray]
output_dir = "site"
modules = ["your_package"]

[tool.portray.mkdocs.theme]
name = "material"
```

**Pros:**
- Single configuration file (pyproject.toml)
- Automatic module discovery
- Integrated pdoc3 for code documentation

**Cons:**
- Less flexible than standalone mkdocs + mkdocstrings
- Smaller community (lower maintenance)
- Fewer customization options

**Verdict:** Use Portray for simple projects; use mkdocs + mkdocstrings for production projects requiring customization.

### 9.2 Sphinx (Traditional Approach)

**Tool**: Sphinx
**Website**: https://www.sphinx-doc.org/

Python documentation standard, used by Python itself:

**Pros:**
- Industry standard (Python, NumPy, Django use it)
- Extensive plugin ecosystem
- Multi-format output (HTML, PDF, ePub)

**Cons:**
- Steeper learning curve (reStructuredText)
- More complex configuration
- Less modern UI out-of-box

**Verdict:** Use Sphinx for large, established projects or projects requiring PDF output. Use MkDocs for modern, Markdown-based documentation.

### 9.3 Read the Docs Integration

Material for MkDocs works with Read the Docs hosting:

```yaml
# .readthedocs.yaml
version: 2
mkdocs:
  configuration: mkdocs.yml
python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

**Use case:** Alternative to GitLab Pages (free public hosting)

---

## Implementation Checklist

### Initial Setup
- [ ] Add docs dependencies to pyproject.toml
- [ ] Create docs/ directory structure
- [ ] Create mkdocs.yml with Material theme
- [ ] Write index.md homepage
- [ ] Configure GitLab CI .gitlab-ci.yml

### Content Creation
- [ ] Getting Started guide
- [ ] User guide pages
- [ ] API reference structure (mkdocstrings)
- [ ] Developer/contributing guide

### Quality Assurance
- [ ] Test locally with `mkdocs serve`
- [ ] Verify all nav links work
- [ ] Check API docs generate correctly
- [ ] Test CI pipeline on feature branch
- [ ] Verify GitLab Pages deployment

### Maintenance
- [ ] Set up automated link checking
- [ ] Configure documentation versioning (if needed)
- [ ] Add badges to README linking to docs
- [ ] Document documentation (meta!)

---

## Conclusion

This framework provides a production-ready, scalable approach to Python project documentation. By combining MkDocs Material, mkdocstrings, and GitLab CI/CD, teams can maintain high-quality documentation with minimal manual effort.

**Next Steps:**
1. Copy template files to your project
2. Customize mkdocs.yml for your project
3. Write initial documentation pages
4. Configure GitLab CI pipeline
5. Commit and push to trigger deployment

**Support & Resources:**
- MkDocs documentation: https://www.mkdocs.org/
- Material for MkDocs: https://squidfunk.github.io/mkdocs-material/
- mkdocstrings: https://mkdocstrings.github.io/
- GitLab Pages: https://docs.gitlab.com/user/project/pages/

---

**Document Metadata:**
- Framework Version: 1.0
- Research Sources: Context7 (MkDocs, Material, mkdocstrings), GitLab Docs, Exa web search, GitHub code search
- Validation: Based on production deployments (Typer, multiple organizations)
- Last Review: October 2025
