"""
Public package entry for allure_emailer.

This package exposes helper functions and classes under the
``allure_emailer`` namespace and declares the version of the installed
package.  The primary user interface is provided by the ``cli`` module
which defines a Typer application with ``init`` and ``send``
commands.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("allure-emailer")
except PackageNotFoundError:  # pragma: no cover - package not installed
    __version__ = "0.0.0"

__all__ = ["__version__"]