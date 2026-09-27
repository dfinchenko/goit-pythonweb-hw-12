"""Sphinx configuration."""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "Contacts API"
author = "Denys Finchenko"
copyright = "2026, Denys Finchenko"
release = "1.0.0"

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode"]
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "show-inheritance": True}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
