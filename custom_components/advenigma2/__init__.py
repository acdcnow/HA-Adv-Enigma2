"""Support for Adv Enigma2 devices."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .services import async_register_services, async_unregister_services

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.TODO,
    Platform.NUMBER,
    Platform.SELECT,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: AdvEnigma2ConfigEntry
) -> bool:
    """Set up Adv Enigma2 from a config entry."""

    coordinator = AdvEnigma2UpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AdvEnigma2ConfigEntry
) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    # Close the aiohttp session that belongs to this entry. Home Assistant only
    # closes it on shutdown, so without this every reload (and every options
    # change, which reloads the entry) would leave one session behind.
    await entry.runtime_data.device.close()

    # Drop the services when the last entry of the integration is gone.
    if not any(
        other.state is ConfigEntryState.LOADED
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        async_unregister_services(hass)

    return True
