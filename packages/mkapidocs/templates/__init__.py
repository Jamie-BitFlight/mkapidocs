"""Template module exports."""

from importlib.resources import files

from .c_api_md_template import C_API_MD_TEMPLATE
from .cli_md_template import CLI_MD_TEMPLATE
from .index_md_template import INDEX_MD_TEMPLATE
from .install_md_template import INSTALL_MD_TEMPLATE
from .python_api_md_template import PYTHON_API_MD_TEMPLATE

# Load static templates using modern importlib.resources.files() API
GITHUB_ACTIONS_PAGES_TEMPLATE = files("mkapidocs.templates").joinpath("pages.yml").read_text()
GITLAB_CI_PAGES_TEMPLATE = files("mkapidocs.templates").joinpath("gitlab-ci.yml").read_text()
MKDOCS_YML_TEMPLATE = files("mkapidocs.templates").joinpath("mkdocs.yml.j2").read_text()

__all__ = [
    "CLI_MD_TEMPLATE",
    "C_API_MD_TEMPLATE",
    "GITHUB_ACTIONS_PAGES_TEMPLATE",
    "GITLAB_CI_PAGES_TEMPLATE",
    "INDEX_MD_TEMPLATE",
    "INSTALL_MD_TEMPLATE",
    "MKDOCS_YML_TEMPLATE",
    "PYTHON_API_MD_TEMPLATE",
]
