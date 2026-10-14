"""Unit tests for the config, reconfigure, reauthentication and options flows."""

from __future__ import annotations

import pytest
from aiohttp.client_exceptions import ClientError
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from openwebif.error import InvalidAuthError

from custom_components.advenigma2.config_flow import clean_connection_input
from custom_components.advenigma2.const import (
    CONF_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET,
    DOMAIN,
)
from tests.conftest import DEFAULT_DATA
from tests.fakes import MAC

USER_INPUT = dict(DEFAULT_DATA)


@pytest.mark.parametrize(
    ("host", "expected_host", "expected_port", "expected_ssl"),
    [
        ("192.168.1.23", "192.168.1.23", 80, False),
        ("  192.168.1.23  ", "192.168.1.23", 80, False),
        ("https://192.168.1.23", "192.168.1.23", 80, True),
        ("http://192.168.1.23/", "192.168.1.23", 80, False),
        ("192.168.1.23:8080", "192.168.1.23", 8080, False),
        ("https://enigma2.local:8443/statusinfo", "enigma2.local", 8443, True),
        ("enigma2.local/?query=1", "enigma2.local", 80, False),
        ("[fe80::1]", "fe80::1", 80, False),
        ("[fe80::1]:8080", "fe80::1", 8080, False),
        ("fe80::1", "fe80::1", 80, False),
    ],
)
def test_clean_connection_input(
    host: str, expected_host: str, expected_port: int, expected_ssl: bool
) -> None:
    """An address typed the way a browser takes it is normalised.

    A scheme, a port, a path or a trailing slash in the host field used to be
    passed to `URL.build()` verbatim, which raised a `ValueError` and surfaced as
    "Unknown error occurred" in the setup dialog.
    """
    cleaned = clean_connection_input(
        {
            CONF_HOST: host,
            CONF_PORT: 80,
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        }
    )

    assert cleaned[CONF_HOST] == expected_host
    assert cleaned[CONF_PORT] == expected_port
    assert cleaned[CONF_SSL] is expected_ssl


async def test_user_flow_accepts_an_address_with_a_scheme(
    hass: HomeAssistant, fake_device
) -> None:
    """The reported setup failure: `https://10.0.0.30` in the host field."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "https://192.168.1.23"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.23"
    assert result["data"][CONF_HOST] == "192.168.1.23"
    assert result["data"][CONF_SSL] is True


@pytest.mark.parametrize("host", ["", "   ", "https://", "http:///path"])
async def test_user_flow_reports_an_unusable_address(
    hass: HomeAssistant, host: str
) -> None:
    """An address without a host shows a translated error, not a traceback."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: host}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_user_flow_creates_an_entry(hass: HomeAssistant) -> None:
    """The user step creates an entry titled after the host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.23"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == MAC


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (InvalidAuthError(), "invalid_auth"),
        (ClientError("Cannot connect to host"), "cannot_connect"),
        (ValueError("boom"), "unknown"),
    ],
)
async def test_user_flow_reports_connection_problems(
    hass: HomeAssistant, fake_device, error: Exception, expected: str
) -> None:
    """A box that rejects the login or cannot be reached shows an error."""
    fake_device.about_error = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_user_flow_aborts_for_an_known_host(
    hass: HomeAssistant, make_entry
) -> None:
    """The same host may not be added twice."""
    make_entry()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_changes_host_port_and_credentials(
    hass: HomeAssistant, make_entry
) -> None:
    """The connection settings of an existing entry can be adjusted."""
    entry = make_entry()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_RECONFIGURE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_HOST: "192.168.1.24",
            CONF_PORT: 8001,
            CONF_USERNAME: "root",
            CONF_PASSWORD: "dreambox",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.24"
    assert entry.data[CONF_PORT] == 8001
    assert entry.data[CONF_USERNAME] == "root"
    assert entry.title == "192.168.1.24"
    assert entry.unique_id == MAC
    # the entry is reloaded with the new settings
    await hass.async_block_till_done()


async def test_reconfigure_keeps_the_host_and_unique_id(
    hass: HomeAssistant, make_entry
) -> None:
    """The entry's own host and unique ID must not abort the flow.

    Regression test: reusing the core check for "another entry already uses this
    host/unique ID" makes the flow abort with `already_configured` because the
    entry being reconfigured matches itself.
    """
    entry = make_entry()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_PORT: 8002}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.23"
    assert entry.data[CONF_PORT] == 8002
    assert entry.unique_id == MAC
    await hass.async_block_till_done()


async def test_reconfigure_aborts_for_the_host_of_another_entry(
    hass: HomeAssistant, make_entry
) -> None:
    """Two entries may not point at the same box."""
    entry = make_entry()
    make_entry(
        data={CONF_HOST: "192.168.1.24"},
        title="192.168.1.24",
        unique_id="bb:bb:bb:bb:bb:bb",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.24"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.23"


async def test_reconfigure_reports_a_box_that_is_off(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Reconfiguring to an unreachable box keeps the flow open with an error."""
    entry = make_entry()
    fake_device.about_error = ClientError("Cannot connect to host")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.99"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == "192.168.1.23"


async def test_reauth_updates_the_credentials(
    hass: HomeAssistant, make_entry
) -> None:
    """The reauthentication flow replaces the login data only."""
    entry = make_entry(
        data={CONF_USERNAME: "root", CONF_PASSWORD: "dreambox"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "root"
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_HOST] == "192.168.1.23"
    assert entry.unique_id == MAC
    await hass.async_block_till_done()


async def test_reauth_reports_wrong_credentials(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Reauthentication keeps the form open when the new login fails."""
    entry = make_entry(data={CONF_USERNAME: "root", CONF_PASSWORD: "dreambox"})
    fake_device.about_error = InvalidAuthError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == "dreambox"


async def test_options_flow_reloads_the_entry(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Changing the options reloads the entry and closes the old client."""
    entry = make_entry()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    first_client = fake_device.last()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DEEP_STANDBY: True, CONF_SOURCE_BOUQUET: "Favourites"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEEP_STANDBY] is True
    assert entry.options[CONF_SOURCE_BOUQUET] == "Favourites"
    # the reload built a new client and the old one was closed
    assert first_client.closed is True
    assert len(fake_device.instances) == 2
