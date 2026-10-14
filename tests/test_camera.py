"""Unit tests for the screenshot camera of the box."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError
from homeassistant.core import HomeAssistant

from custom_components.advenigma2.const import (
    CONF_SCREENSHOT_FORMAT,
    CONF_SCREENSHOT_MODE,
    CONF_SCREENSHOT_RESOLUTION,
)
from tests.fake_api import SCREENSHOT, FakeApi
from tests.helpers import entity_id, setup_entry


async def snapshot(hass: HomeAssistant, client) -> tuple[int, bytes]:
    """Ask Home Assistant for the picture of the camera."""
    entity = entity_id(hass, "camera", "screenshot")
    response = await client.get(f"/api/camera_proxy/{entity}")
    return response.status, await response.read()


async def test_camera_serves_the_screen_grab(
    hass: HomeAssistant, make_entry, hass_client
) -> None:
    """The camera asks the box for a screen grab with the default options."""
    await setup_entry(hass, make_entry)
    client = await hass_client()

    status, body = await snapshot(hass, client)

    assert status == 200
    assert body == SCREENSHOT
    assert FakeApi.last().recorded("screenshot_url") == [("all", "jpg", 720)]


async def test_camera_uses_the_options(
    hass: HomeAssistant, make_entry, hass_client
) -> None:
    """The mode, the format and the resolution come from the options."""
    await setup_entry(
        hass,
        make_entry,
        options={
            CONF_SCREENSHOT_MODE: "osd",
            CONF_SCREENSHOT_FORMAT: "png",
            CONF_SCREENSHOT_RESOLUTION: 0,
        },
    )
    client = await hass_client()

    await snapshot(hass, client)

    assert FakeApi.last().recorded("screenshot_url") == [("osd", "png", 0)]


async def test_camera_does_not_poke_a_box_that_is_off(
    hass: HomeAssistant, make_entry, fake_device, hass_client
) -> None:
    """An unreachable box is not asked for pictures on every dashboard refresh."""
    entry = await setup_entry(hass, make_entry)
    client = await hass_client()

    fake_device.update_error = ClientError("Cannot connect to host")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    status, _ = await snapshot(hass, client)

    assert status != 200
    assert FakeApi.last().recorded("screenshot_url") == []
