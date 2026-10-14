"""The sleep timer action (standby or shutdown) of the box."""

from __future__ import annotations

from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SLEEP_TIMER_ACTIONS
from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .entity import AdvEnigma2Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdvEnigma2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sleep timer action of the box."""
    async_add_entities([AdvEnigma2SleepTimerAction(entry.runtime_data)])


class AdvEnigma2SleepTimerAction(AdvEnigma2Entity, SelectEntity):
    """What the sleep timer does when it fires."""

    _attr_translation_key = "sleep_timer_action"
    _attr_icon = "mdi:timer-cog-outline"
    _attr_options = SLEEP_TIMER_ACTIONS

    def __init__(self, coordinator: AdvEnigma2UpdateCoordinator) -> None:
        """Initialize the sleep timer action."""
        super().__init__(coordinator, "sleep_timer_action")

    @property
    @override
    def current_option(self) -> str | None:
        """Return the configured action."""
        sleep_timer = self.coordinator.sleep_timer
        if not sleep_timer:
            return None
        action = sleep_timer.get("action")
        return action if action in SLEEP_TIMER_ACTIONS else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the action, keeping the state of the sleep timer."""
        sleep_timer = self.coordinator.sleep_timer or {}
        await self.coordinator.api.async_set_sleep_timer(
            enabled=bool(sleep_timer.get("enabled")),
            minutes=int(sleep_timer.get("minutes") or 0),
            action=option,
        )
        await self.coordinator.async_request_refresh()
