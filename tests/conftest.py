"""Shared pytest fixtures for the Adv Enigma2 tests.

Run the suite with the interpreter that has Home Assistant 2026.10.1 installed::

    .venv\\Scripts\\python.exe -m pytest
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.advenigma2 import config_flow, coordinator
from custom_components.advenigma2.const import DOMAIN
from tests.fake_api import FakeApi
from tests.fakes import MAC, FakeOpenWebIfDevice

if sys.platform == "win32":  # pragma: no cover - platform specific
    # The Home Assistant test harness blocks sockets, allowing only AF_UNIX ones
    # because asyncio needs them for its self-pipe. On Windows socket.socketpair()
    # uses AF_INET, so creating the event loop of a test would fail before the
    # test even starts. Nothing in this suite opens a connection - the box is
    # faked (tests/fakes.py) - so the guard is lifted on Windows only.
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None
    pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None

DEFAULT_DATA: dict[str, Any] = {
    CONF_HOST: "192.168.1.23",
    CONF_PORT: 80,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/advenigma2 in every test."""
    yield


@pytest.fixture(autouse=True)
def fake_device(monkeypatch: pytest.MonkeyPatch):
    """Replace the OpenWebIf client and the raw API with the fakes."""
    FakeOpenWebIfDevice.reset()
    FakeApi.reset()
    monkeypatch.setattr(coordinator, "OpenWebIfDevice", FakeOpenWebIfDevice)
    monkeypatch.setattr(coordinator, "AdvEnigma2Api", FakeApi)
    monkeypatch.setattr(config_flow, "OpenWebIfDevice", FakeOpenWebIfDevice)
    yield FakeOpenWebIfDevice
    FakeOpenWebIfDevice.reset()
    FakeApi.reset()


@pytest.fixture
def make_entry(hass: HomeAssistant):
    """Return a factory that adds a config entry for the fake box to hass."""

    def _make(
        *,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        unique_id: str | None = MAC,
        title: str | None = None,
    ) -> MockConfigEntry:
        full_data = {**DEFAULT_DATA, **(data or {})}
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=title or full_data[CONF_HOST],
            unique_id=unique_id,
            data=full_data,
            options=options or {},
        )
        entry.add_to_hass(hass)
        return entry

    return _make
