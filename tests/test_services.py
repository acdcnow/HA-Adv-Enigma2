"""Unit tests for the services of the integration."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from openwebif.enums import MessageType, RemoteControlCodes

from custom_components.advenigma2.const import AFTEREVENT_DEEP_STANDBY, DOMAIN
from tests.fake_api import FakeApi
from tests.fakes import RECORDING_REF, SERVICE_REF, TIMER_BEGIN, TIMER_END
from tests.helpers import entity_id, setup_entry


async def test_send_message(hass: HomeAssistant, make_entry, fake_device) -> None:
    """A message is shown on the TV screen."""
    await setup_entry(hass, make_entry)

    await hass.services.async_call(
        DOMAIN,
        "send_message",
        {
            "entity_id": entity_id(hass, "media_player"),
            "message": "Das Essen ist fertig",
            "type": "warning",
            "timeout": 10,
        },
        blocking=True,
    )

    assert fake_device.last().recorded("send_message") == [
        ("Das Essen ist fertig", MessageType.WARNING, 10)
    ]


async def test_send_remote_control(hass: HomeAssistant, make_entry) -> None:
    """A key of the remote control is sent to the box."""
    await setup_entry(hass, make_entry)

    await hass.services.async_call(
        DOMAIN,
        "send_remote_control",
        {
            "entity_id": entity_id(hass, "media_player"),
            "command": "CHANNEL_UP",
            "type": "long",
        },
        blocking=True,
    )

    assert FakeApi.last().recorded("send_remote_control") == [
        (RemoteControlCodes.CHANNEL_UP.value, "long")
    ]


async def test_add_timer(hass: HomeAssistant, make_entry) -> None:
    """A timer can be created from Home Assistant."""
    await setup_entry(hass, make_entry)

    await hass.services.async_call(
        DOMAIN,
        "add_timer",
        {
            "entity_id": entity_id(hass, "media_player"),
            "channel": "Das Erste HD",
            "begin": dt_util.utc_from_timestamp(TIMER_BEGIN).isoformat(),
            "end": dt_util.utc_from_timestamp(TIMER_END).isoformat(),
            "name": "Tagesschau",
            "afterevent": "deep_standby",
        },
        blocking=True,
    )

    assert FakeApi.last().recorded("add_timer") == [
        {
            "serviceref": SERVICE_REF,
            "begin": TIMER_BEGIN,
            "end": TIMER_END,
            "name": "Tagesschau",
            "description": None,
            "disabled": False,
            "justplay": False,
            "afterevent": AFTEREVENT_DEEP_STANDBY,
            "dirname": None,
            "tags": None,
        }
    ]


async def test_add_timer_rejects_a_reversed_range(
    hass: HomeAssistant, make_entry
) -> None:
    """A timer that would end before it starts is refused."""
    await setup_entry(hass, make_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "add_timer",
            {
                "entity_id": entity_id(hass, "media_player"),
                "channel": "Das Erste HD",
                "begin": dt_util.utc_from_timestamp(TIMER_END).isoformat(),
                "end": dt_util.utc_from_timestamp(TIMER_BEGIN).isoformat(),
                "name": "Falsch",
            },
            blocking=True,
        )

    assert FakeApi.last().recorded("add_timer") == []


async def test_remove_timer(hass: HomeAssistant, make_entry) -> None:
    """A timer can be deleted by channel and time."""
    await setup_entry(hass, make_entry)

    await hass.services.async_call(
        DOMAIN,
        "remove_timer",
        {
            "entity_id": entity_id(hass, "media_player"),
            "channel": SERVICE_REF,
            "begin": dt_util.utc_from_timestamp(TIMER_BEGIN).isoformat(),
            "end": dt_util.utc_from_timestamp(TIMER_END).isoformat(),
        },
        blocking=True,
    )

    assert FakeApi.last().recorded("delete_timer") == [
        (SERVICE_REF, TIMER_BEGIN, TIMER_END, None)
    ]


async def test_delete_and_rename_recording(
    hass: HomeAssistant, make_entry
) -> None:
    """Recordings can be deleted and renamed."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "media_player")

    await hass.services.async_call(
        DOMAIN,
        "delete_recording",
        {"entity_id": entity, "recording": RECORDING_REF, "force": True},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "rename_recording",
        {"entity_id": entity, "recording": RECORDING_REF, "name": "Tagesschau.ts"},
        blocking=True,
    )

    api = FakeApi.last()
    assert api.recorded("delete_recording") == [(RECORDING_REF, True)]
    assert api.recorded("rename_recording") == [(RECORDING_REF, "Tagesschau.ts")]


async def test_services_are_removed_with_the_last_entry(
    hass: HomeAssistant, make_entry
) -> None:
    """The services disappear together with the integration."""
    entry = await setup_entry(hass, make_entry)
    assert hass.services.has_service(DOMAIN, "send_message")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "send_message")
