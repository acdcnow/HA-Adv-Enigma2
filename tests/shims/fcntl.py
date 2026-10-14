"""Minimal Windows shim for the Unix only ``fcntl`` module.

``homeassistant.runner`` imports ``fcntl`` at module level (for the single
instance lock file) and ``pytest_homeassistant_custom_component`` imports
``homeassistant.runner``, so the official Home Assistant test harness cannot be
imported on Windows without this stub.

The functions are no-ops. This file is only a local development helper: it is
never shipped to Home Assistant and is not needed on Linux or macOS, where the
real ``fcntl`` exists. To use it, copy it into the virtual environment::

    Copy-Item tests\\shims\\fcntl.py .venv\\Lib\\site-packages\\fcntl.py
"""

LOCK_SH = 1
LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8


def flock(fd, operation):  # noqa: ARG001, ANN001
    """Pretend to acquire a file lock (no-op on Windows)."""
    return None
