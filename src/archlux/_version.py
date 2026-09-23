"""Single source of truth for the package version.

Read by hatch at build time (``[tool.hatch.version]``) and imported by every module that
stamps an output. It imports nothing, so any layer may depend on it without loading the
rest of the library.
"""

__version__ = "0.10.0.dev0"
