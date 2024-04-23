"""
Contains the entry point for the application
"""

try:
    from ._version import __version__  # noqa: F401
except ImportError:
    __version__ = "unknown"


def PyONCatQt():
    """This is needed for backward compatibility because mantid workbench does "from shiver import Shiver" """
    from .pyoncatqt import PyONCatQt as pyoncatqt

    return pyoncatqt()
