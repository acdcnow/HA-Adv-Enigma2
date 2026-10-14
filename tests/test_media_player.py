"""Unit tests for the Adv Enigma2 media player platform."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from openwebif.enums import PowerState, RemoteControlCodes, SetVolumeOption

from custom_components.advenigma2.const import DOMAIN
from custom_components.advenigma2.media_player import MEDIA_ID_CHANNELS
from tests.fake_api import FakeApi
from tests.fakes import MAC, RECORDING_REF, SERVICE_REF
from tests.helpers import entity_id


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


async def test_media_browser_lists_bouquets_channels_and_recordings(
    hass: HomeAssistant, make_entry
) -> None:
    """The media browser walks from the bouquets down to the channels."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "media_player")

    async def browse(content_id: str, content_type: str):
        response = await hass.services.async_call(
            "media_player",
            "browse_media",
            {
                "entity_id": entity,
                "media_content_id": content_id,
                "media_content_type": content_type,
            },
            blocking=True,
            return_response=True,
        )
        return response[entity]

    root = await browse("root", "root")
    assert [child.title for child in root.children] == [
        "Channels",
        "Recordings",
    ]

    channels = await browse("channels", "channels")
    assert [child.title for child in channels.children] == ["Favourites"]

    bouquet = await browse(channels.children[0].media_content_id, "bouquet")
    assert [child.title for child in bouquet.children] == [
        "Das Erste HD",
        "ZDF HD",
    ]
    assert bouquet.children[0].media_content_id == SERVICE_REF

    recordings = await browse("recordings", "recordings")
    assert [child.title for child in recordings.children] == ["Tagesschau"]
    assert recordings.children[0].media_content_id == RECORDING_REF


async def test_media_browser_skips_entries_it_cannot_play(
    hass: HomeAssistant, make_entry
) -> None:
    """A bouquet can hold entries that are no channel, and boxes differ in spelling.

    Reading `service["serviceref"]` raised a `KeyError` that Home Assistant
    reported as "Unknown error" in the media browser when a box answered a bouquet
    with different keys.
    """
    FakeApi.services = [
        {"sRef": SERVICE_REF, "sName": "Das Erste HD"},
        {"serviceref": "1:0:19:2B66:3F3:1:C00000:0:0:0:", "name": "ZDF HD"},
        {"title": "Sub bouquet"},
        {},
    ]
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "media_player")

    response = await hass.services.async_call(
        "media_player",
        "browse_media",
        {
            "entity_id": entity,
            "media_content_id": MEDIA_ID_CHANNELS,
            "media_content_type": "channels",
        },
        blocking=True,
        return_response=True,
    )
    bouquet = response[entity].children[0]

    browsed = await hass.services.async_call(
        "media_player",
        "browse_media",
        {
            "entity_id": entity,
            "media_content_id": bouquet.media_content_id,
            "media_content_type": "bouquet",
        },
        blocking=True,
        return_response=True,
    )

    assert [child.title for child in browsed[entity].children] == [
        "Das Erste HD",
        "ZDF HD",
    ]
    assert browsed[entity].children[0].media_content_id == SERVICE_REF


async def test_the_source_list_is_filled_when_the_box_has_no_epg(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """openwebifpy builds the sources from `/api/epgnow`, which OpenATV answers empty.

    The sources are then taken from `/api/getservices`, so the media player has a
    working source list and openwebifpy stops logging "No sources could be loaded
    from specified bouquet" on every poll.
    """
    entry = make_entry()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = fake_device.last()
    device.sources = {}
    device.source_list = []

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert device.sources == {
        "Das Erste HD": SERVICE_REF,
        "ZDF HD": "1:0:19:2B66:3F3:1:C00000:0:0:0:",
    }
    assert device.source_list == ["Das Erste HD", "ZDF HD"]
    assert hass.states.get(entity_id(hass, "media_player")).attributes[
        "source_list"
    ] == ["Das Erste HD", "ZDF HD"]


async def test_play_media_tunes_a_channel_and_plays_a_recording(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Playing from the browser zaps the box to the channel or the recording."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "media_player")
    device = fake_device.last()

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": entity,
            "media_content_id": SERVICE_REF,
            "media_content_type": "channel",
        },
        blocking=True,
    )
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": entity,
            "media_content_id": RECORDING_REF,
            "media_content_type": "recording",
        },
        blocking=True,
    )

    assert device.recorded("zap") == [SERVICE_REF, RECORDING_REF]


async def test_stream_url_of_the_running_channel(
    hass: HomeAssistant, make_entry
) -> None:
    """The stream url can be handed to another media player."""
    await setup_entry(hass, make_entry)

    state = hass.states.get(entity_id(hass, "media_player"))

    assert state.attributes["stream_url"] == f"http://192.168.1.23:8001/{SERVICE_REF}"
