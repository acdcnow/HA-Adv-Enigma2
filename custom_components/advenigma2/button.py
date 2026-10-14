"""Buttons for the Adv Enigma2 box."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiohttp.client_exceptions import ServerDisconnectedError
from openwebif.enums import PowerState

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .entity import AdvEnigma2Entity


def _always_available(coordinator: AdvEnigma2UpdateCoordinator) -> bool:
    """Return True for the buttons that always work."""
    return True


def _cec_available(coordinator: AdvEnigma2UpdateCoordinator) -> bool:
    """Return True when the box can power on without waking the TV."""
    return coordinator.supports_cec_power_on


async def _async_power_state(
    coordinator: AdvEnigma2UpdateCoordinator, state: PowerState
) -> None:
    """Change the power state of the box.

    The box can stop answering in the middle of the call while it reboots or shuts
    down; the coordinator then sees it as unavailable and polls it with the offline
    back-off instead of every scan interval.
    """
    with contextlib.suppress(ServerDisconnectedError):
        await coordinator.device.set_powerstate(state)
    await coordinator.async_refresh()


async def _async_reboot(coordinator: AdvEnigma2UpdateCoordinator) -> None:
    """Reboot the box."""
    await _async_power_state(coordinator, PowerState.REBOOT)


async def _async_restart_enigma(coordinator: AdvEnigma2UpdateCoordinator) -> None:
    """Restart Enigma2 on the box."""
    await _async_power_state(coordinator, PowerState.RESTART_ENIGMA)


async def _async_deep_standby(coordinator: AdvEnigma2UpdateCoordinator) -> None:
    """Shut the box down into deep standby."""
    await _async_power_state(coordinator, PowerState.DEEP_STANDBY)


async def _async_standby(coordinator: AdvEnigma2UpdateCoordinator) -> None:
    """Send the box into standby."""
    await _async_power_state(coordinator, PowerState.STANDBY)


async def _async_record_now(coordinator: AdvEnigma2UpdateCoordinator) -> None:
    """Start recording the running programme."""
    await coordinator.api.async_record_now()
    await coordinator.async_request_refresh()


async def _async_cleanup_timers(coordinator: AdvEnigma2UpdateCoordinator) -> None:
    """Delete the expired timers."""
    await coordinator.api.async_cleanup_timers()
    await coordinator.async_request_refresh()


async def _async_power_on_without_waking_tv(
    coordinator: AdvEnigma2UpdateCoordinator,
) -> None:
    """Power the box on without waking the TV over HDMI-CEC."""
    await coordinator.api.async_power_on_without_waking_tv()
    # the box is booting, so polling may return to the normal interval
    coordinator.async_reset_offline_backoff()
    await coordinator.async_refresh()


@dataclass(frozen=True, kw_only=True)
class AdvEnigma2ButtonDescription(ButtonEntityDescription):
    """Describes a button of the box."""

    press_fn: Callable[[AdvEnigma2UpdateCoordinator], Awaitable[None]]
    available_fn: Callable[
        [AdvEnigma2UpdateCoordinator], bool
    ] = _always_available


BUTTONS: tuple[AdvEnigma2ButtonDescription, ...] = (
    AdvEnigma2ButtonDescription(
        key="reboot",
        icon="mdi:restart",
        press_fn=_async_reboot,
    ),
    AdvEnigma2ButtonDescription(
        key="restart_enigma2",
        icon="mdi:restart-alert",
        press_fn=_async_restart_enigma,
    ),
    AdvEnigma2ButtonDescription(
        key="standby",
        icon="mdi:power-sleep",
        press_fn=_async_standby,
    ),
    AdvEnigma2ButtonDescription(
        key="deep_standby",
        icon="mdi:power-standby",
        press_fn=_async_deep_standby,
    ),
    AdvEnigma2ButtonDescription(
        key="record_now",
        icon="mdi:record-rec",
        press_fn=_async_record_now,
    ),
    AdvEnigma2ButtonDescription(
        key="cleanup_timers",
        icon="mdi:calendar-remove",
        press_fn=_async_cleanup_timers,
    ),
    AdvEnigma2ButtonDescription(
        key="power_on_without_waking_tv",
        icon="mdi:hdmi-port",
        press_fn=_async_power_on_without_waking_tv,
        available_fn=_cec_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdvEnigma2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of the box."""
    async_add_entities(
        AdvEnigma2Button(entry.runtime_data, description) for description in BUTTONS
    )


class AdvEnigma2Button(AdvEnigma2Entity, ButtonEntity):
    """A button that triggers an action on the box."""

    entity_description: AdvEnigma2ButtonDescription

    def __init__(
        self,
        coordinator: AdvEnigma2UpdateCoordinator,
        description: AdvEnigma2ButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        # the name of the entity comes from the translations, like the key
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        """Return True when the button can be pressed."""
        return super().available and self.entity_description.available_fn(
            self.coordinator
        )

    async def async_press(self) -> None:
        """Run the action of the button."""
        await self.entity_description.press_fn(self.coordinator)
