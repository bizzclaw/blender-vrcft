"""pytest configuration for tests directory.

This conftest prevents pytest from treating the parent directory as a Python package,
which is necessary because the parent __init__.py is a Blender add-on init file,
not a standard Python package init.
"""

# This file tells pytest that tests is its own package root
# and prevents pytest from trying to import the parent __init__.py
