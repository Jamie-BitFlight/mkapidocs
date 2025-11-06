"""Generate documentation pages from nested markdown files."""

from pathlib import Path

import mkdocs_gen_files

# Root of the repository
root = Path.cwd()

# Find all markdown files outside docs/ directory
markdown_files = []
for md_path in root.rglob("*.md"):
    # Skip files in these directories
    skip_dirs = {".venv", "site", "docs", ".git", "__pycache__", ".pytest_cache", "node_modules"}
    if any(part.startswith(".") or part in skip_dirs for part in md_path.parts):
        continue

    # Skip if file is in docs directory
    try:
        md_path.relative_to(root / "docs")
        continue
    except ValueError:
        pass

    markdown_files.append(md_path)

# Build navigation structure
nav_structure = {}
doc_paths = []

# Create virtual docs for each discovered markdown file
for md_path in sorted(markdown_files):
    # Get relative path from root
    rel_path = md_path.relative_to(root)

    # Create a virtual doc path in the "Repository Files" section
    if rel_path.name == "README.md":
        # For README.md files, use the directory name
        # Root README.md becomes about.md, others become index.md in their directory
        doc_path = f"repository/{'/'.join(rel_path.parts[:-1])}/index.md" if len(rel_path.parts) > 1 else "about.md"
    else:
        # For other .md files, keep their name
        doc_path = f"repository/{rel_path}"

    # Read the original file and write to virtual doc
    with mkdocs_gen_files.open(doc_path, "w") as f:
        content = md_path.read_text()
        # Add a breadcrumb header
        f.write(f"# {rel_path}\n\n")
        f.write(content)

    # Set edit path to point to the original file
    mkdocs_gen_files.set_edit_path(doc_path, rel_path)

    doc_paths.append((rel_path, doc_path))

# Generate SUMMARY.md for literate-nav
with mkdocs_gen_files.open("repository/SUMMARY.md", "w") as nav_file:
    nav_file.write("# Repository Files\n\n")

    # Group by directory
    current_dir = None
    for rel_path, doc_path in sorted(doc_paths):
        parent_dir = str(rel_path.parent) if rel_path.parent != Path(".") else "Root"

        # Write directory header
        if current_dir != parent_dir:
            current_dir = parent_dir
            nav_file.write(f"\n## {parent_dir}\n\n")

        # Write file link
        # Remove 'repository/' prefix from doc_path for the link
        link_path = doc_path.replace("repository/", "")
        nav_file.write(f"- [{rel_path.name}]({link_path})\n")
