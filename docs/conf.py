"""
Sphinx configuration for AI Beast documentation.

This file configures Sphinx to generate API documentation from docstrings,
create a searchable HTML documentation site, and integrate with ReadTheDocs.
"""

import os
import sys
from datetime import datetime

# Add project root to path for autodoc
sys.path.insert(0, os.path.abspath(".."))

# =============================================================================
# Project Information
# =============================================================================

project = "AI Beast"
copyright = f"{datetime.now().year}, AI Beast Contributors"
author = "AI Beast Contributors"

# Version info - read from VERSION file
version_file = os.path.join(os.path.dirname(__file__), "..", "VERSION")
if os.path.exists(version_file):
    with open(version_file) as f:
        version = f.read().strip()
else:
    version = "0.1.0"

release = version

# =============================================================================
# General Configuration
# =============================================================================

# Sphinx extensions
extensions = [
    # Core extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.githubpages",
    # Additional extensions
    "sphinx_copybutton",
    "sphinx_design",
    "myst_parser",
]

# Source file parsers
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Master document
master_doc = "index"

# Exclude patterns
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**/__pycache__",
]

# Template paths
templates_path = ["_templates"]

# Static files
html_static_path = ["_static"]

# =============================================================================
# Autodoc Configuration
# =============================================================================

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}

# Generate autosummary pages
autosummary_generate = True
autosummary_imported_members = True

# Napoleon settings for Google/NumPy docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_type_aliases = None

# =============================================================================
# Intersphinx Configuration
# =============================================================================

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "httpx": ("https://www.python-httpx.org/", None),
    "redis": ("https://redis-py.readthedocs.io/en/stable/", None),
}

# =============================================================================
# HTML Output Configuration
# =============================================================================

# Theme
html_theme = "furo"

# Theme options
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#2563eb",
        "color-brand-content": "#2563eb",
    },
    "dark_css_variables": {
        "color-brand-primary": "#60a5fa",
        "color-brand-content": "#60a5fa",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
    "source_repository": "https://github.com/dylan90401/ai_beast",
    "source_branch": "main",
    "source_directory": "docs/",
}

# HTML options
html_title = f"AI Beast {version}"
html_short_title = "AI Beast"
html_favicon = "_static/favicon.ico"
html_logo = "_static/logo.png"

# Show "Edit on GitHub" link
html_context = {
    "display_github": True,
    "github_user": "dylan90401",
    "github_repo": "ai_beast",
    "github_version": "main",
    "conf_py_path": "/docs/",
}

# =============================================================================
# MyST Parser Configuration (Markdown)
# =============================================================================

myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

myst_heading_anchors = 3

# =============================================================================
# TODO Extension
# =============================================================================

todo_include_todos = True

# =============================================================================
# Copy Button Configuration
# =============================================================================

copybutton_prompt_text = r">>> |\.\.\. |\$ |> "
copybutton_prompt_is_regexp = True

# =============================================================================
# LaTeX Output Configuration
# =============================================================================

latex_elements = {
    "papersize": "letterpaper",
    "pointsize": "10pt",
    "preamble": "",
    "fncychap": "\\usepackage[Bjornstrup]{fncychap}",
}

latex_documents = [
    (master_doc, "ai_beast.tex", "AI Beast Documentation", author, "manual"),
]

# =============================================================================
# Man Page Output Configuration
# =============================================================================

man_pages = [
    (master_doc, "ai_beast", "AI Beast Documentation", [author], 1),
]

# =============================================================================
# Texinfo Output Configuration
# =============================================================================

texinfo_documents = [
    (
        master_doc,
        "ai_beast",
        "AI Beast Documentation",
        author,
        "ai_beast",
        "Local AI Infrastructure Manager",
        "Miscellaneous",
    ),
]
