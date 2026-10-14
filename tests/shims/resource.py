"""Minimal Windows shim for the Unix only ``resource`` module.

``homeassistant.util.resource`` imports ``resource`` at module level and is
imported by ``homeassistant.runner``, which the official Home Assistant test
harness needs. The limit is reported as already high enough, so Home Assistant
skips changing it.

This file is only a local development helper: it is never shipped to Home
Assistant and is not needed on Linux or macOS, where the real ``resource``
exists. To use it, copy it into the virtual environment::

    Copy-Item tests\\shims\\*.py .venv\\Lib\\site-packages\\
"""

RLIMIT_NOFILE = 7
RLIM_INFINITY = -1

_REPORTED_SOFT_LIMIT = 65536


def getrlimit(resource_id):  # noqa: ARG001, ANN001
    """Return a fake soft and hard limit that does not need to be changed."""
    return (_REPORTED_SOFT_LIMIT, _REPORTED_SOFT_LIMIT)


def setrlimit(resource_id, limits):  # noqa: ARG001, ANN001
    """Pretend to set a resource limit (no-op on Windows)."""
    return None
