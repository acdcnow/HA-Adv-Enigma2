"""The sleep timer of the box as a number (minutes)."""

from __future__ import annotations

from typing import override

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
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
    """Set up the sleep timer of the box."""
    async_add_entities([AdvEnigma2SleepTimer(entry.runtime_data)])


class AdvEnigma2SleepTimer(AdvEnigma2Entity, NumberEntity):
    """Minutes until the box goes to standby or shuts down.

    `0` turns the sleep timer off. The action is chosen with the matching select
    entity.
    """

    _attr_translation_key = "sleep_timer"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 999
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: AdvEnigma2UpdateCoordinator) -> None:
        """Initialize the sleep timer."""
        super().__init__(coordinator, "sleep_timer")

    @property
    @override
    def native_value(self) -> float | None:
        """Return the configured minutes, `0` when the timer is off."""
        sleep_timer = self.coordinator.sleep_timer
        if not sleep_timer or not sleep_timer.get("enabled"):
            return 0
        return sleep_timer.get("minutes")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the action that the sleep timer performs."""
        sleep_timer = self.coordinator.sleep_timer or {}
        return {"action": sleep_timer.get("action", SLEEP_TIMER_ACTIONS[0])}

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the minutes or turn the sleep timer off with `0`."""
        minutes = int(value)
        action = (self.coordinator.sleep_timer or {}).get(
            "action", SLEEP_TIMER_ACTIONS[0]
        )
        await self.coordinator.api.async_set_sleep_timer(
            enabled=minutes > 0, minutes=minutes, action=action
        )
        await self.coordinator.async_request_refresh()
