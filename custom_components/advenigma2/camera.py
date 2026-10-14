"""Screenshot camera for the Adv Enigma2 box."""

from __future__ import annotations

from typing import override

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_SCREENSHOT_FORMAT,
    CONF_SCREENSHOT_MODE,
    CONF_SCREENSHOT_RESOLUTION,
    DEFAULT_SCREENSHOT_FORMAT,
    DEFAULT_SCREENSHOT_MODE,
    DEFAULT_SCREENSHOT_RESOLUTION,
)
from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .entity import AdvEnigma2Entity

# A dashboard that shows the camera asks for a new picture in this interval. The
# request is only made while the box answers, an unreachable box is not polled.
FRAME_INTERVAL = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdvEnigma2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the screenshot camera of the box."""
    async_add_entities([AdvEnigma2Camera(entry.runtime_data)])


class AdvEnigma2Camera(AdvEnigma2Entity, Camera):
    """The live picture of the box as a camera."""

    _attr_translation_key = "screenshot"
    _attr_frame_interval = FRAME_INTERVAL

    def __init__(self, coordinator: AdvEnigma2UpdateCoordinator) -> None:
        """Initialize the camera.

        Both bases need their own `__init__`: `Camera` sets up the access tokens
        and the WebRTC provider that `async_internal_added_to_hass` expects.
        """
        Camera.__init__(self)
        AdvEnigma2Entity.__init__(self, coordinator, "screenshot")

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a screen grab of the box.

        The box is only asked while the coordinator can reach it: a box that is
        switched off or in deep standby must not be poked for every dashboard
        refresh.
        """
        if not self.coordinator.last_update_success:
            return None

        options = self.coordinator.config_entry.options
        url = self.coordinator.api.screenshot_url(
            options.get(CONF_SCREENSHOT_MODE, DEFAULT_SCREENSHOT_MODE),
            options.get(CONF_SCREENSHOT_FORMAT, DEFAULT_SCREENSHOT_FORMAT),
            options.get(CONF_SCREENSHOT_RESOLUTION, DEFAULT_SCREENSHOT_RESOLUTION),
        )
        return await self.coordinator.api.async_get_image(url)
