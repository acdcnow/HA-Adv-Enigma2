"""Unit tests for the Adv Enigma2 media player platform."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from openwebif.enums import PowerState, RemoteControlCodes, SetVolumeOption

from custom_components.advenigma2.const import DOMAIN
from tests.fakes import MAC, SERVICE_REF


async def setup_entry(hass: HomeAssistant, make_entry) -> tuple[object, str]:
    """Set up a config entry and return it together with the entity_id."""
    entry = make_entry()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, hass.states.async_entity_ids("media_player")[0]


async def test_setup_creates_a_media_player(hass: HomeAssistant, make_entry) -> None:
    """The box shows up as a media player with the current programme."""
    _, entity_id = await setup_entry(hass, make_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["media_title"] == "Das Erste HD"
    assert state.attributes["media_series_title"] == "Tagesschau"
    assert state.attributes["media_channel"] == "Das Erste HD"
    assert state.attributes["media_content_id"] == SERVICE_REF
    assert state.attributes["media_content_type"] == "tvshow"
    assert state.attributes["media_description"] == (
        "Tagesschau\n10:00 - 10:30\nNachrichten"
    )
    assert state.attributes["media_start_time"] == "10:00"
    assert state.attributes["media_end_time"] == "10:30"
    assert state.attributes["media_currently_recording"] is False
    assert state.attributes["source"] == "Das Erste HD"
    assert state.attributes["source_list"] == ["Das Erste HD"]
    assert state.attributes["volume_level"] == 0.42
    # Home Assistant serves the picon through the media player image proxy
    assert state.attributes["entity_picture"].startswith("/api/media_player_proxy/")


async def test_device_registry_entry_carries_the_box_information(
    hass: HomeAssistant, make_entry
) -> None:
    """The MAC of the box makes the device unique."""
    entry, _ = await setup_entry(hass, make_entry)

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, format_mac(MAC)), entry.entry_id
    )

    assert device is not None
    assert device.model == "UHD Quad 4K Pro"
    assert device.manufacturer == "GigaBlue"
    assert device.name == "192.168.1.23"


async def test_standby_makes_the_player_off(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """The power state of the box is reflected in the entity state."""
    entry, entity_id = await setup_entry(hass, make_entry)
    assert hass.states.get(entity_id).state == "on"

    fake_device.last().status.in_standby = True
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"


async def test_volume_channel_and_source_commands(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """The media player services reach the OpenWebIF client."""
    _, entity_id = await setup_entry(hass, make_entry)
    device = fake_device.last()

    await hass.services.async_call(
        "media_player", "volume_up", {"entity_id": entity_id}, blocking=True
    )
    await hass.services.async_call(
        "media_player", "volume_down", {"entity_id": entity_id}, blocking=True
    )
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": entity_id, "volume_level": 0.5},
        blocking=True,
    )
    assert device.recorded("set_volume") == [
        SetVolumeOption.UP,
        SetVolumeOption.DOWN,
        50,
    ]

    await hass.services.async_call(
        "media_player", "media_next_track", {"entity_id": entity_id}, blocking=True
    )
    await hass.services.async_call(
        "media_player", "media_previous_track", {"entity_id": entity_id}, blocking=True
    )
    assert device.recorded("send_remote_control_action") == [
        RemoteControlCodes.CHANNEL_UP,
        RemoteControlCodes.CHANNEL_DOWN,
    ]

    await hass.services.async_call(
        "media_player", "media_pause", {"entity_id": entity_id}, blocking=True
    )
    assert RemoteControlCodes.PAUSE in device.recorded("send_remote_control_action")

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": entity_id, "source": "Das Erste HD"},
        blocking=True,
    )
    assert device.recorded("zap") == [SERVICE_REF]

    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {"entity_id": entity_id, "is_volume_muted": True},
        blocking=True,
    )
    assert device.recorded("toggle_mute") == [None]


async def test_turn_off_uses_standby_or_deep_standby(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """The deep standby option decides how the box is switched off."""
    _, entity_id = await setup_entry(hass, make_entry)
    device = fake_device.last()

    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert device.recorded("set_powerstate") == [PowerState.STANDBY]

    device.turn_off_to_deep = True
    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert device.recorded("set_powerstate") == [
        PowerState.STANDBY,
        PowerState.DEEP_STANDBY,
    ]


async def test_turn_on_clears_the_offline_backoff(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Turning the box on polls it at the normal interval again."""
    entry, entity_id = await setup_entry(hass, make_entry)
    entry.runtime_data.offline_failures = 5

    await hass.services.async_call(
        "media_player", "turn_on", {"entity_id": entity_id}, blocking=True
    )

    assert fake_device.last().recorded("turn_on") == [None]
    assert entry.runtime_data.offline_failures == 0


async def test_setup_is_retried_when_the_box_is_off(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """A box that is off while Home Assistant starts leads to a setup retry.

    This is what keeps Home Assistant from failing the entry (and from never
    trying again) when the box happens to be switched off during a restart.
    """
    fake_device.about_error = ClientError("Cannot connect to host")
    entry = make_entry()

    assert await hass.config_entries.async_setup(entry.entry_id) is False

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_closes_the_client(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Unloading the entry closes the aiohttp session of the box."""
    entry, _ = await setup_entry(hass, make_entry)
    device = fake_device.last()

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()

    assert device.closed is True
