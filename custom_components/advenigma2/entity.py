"""Base entity for the Adv Enigma2 integration."""

from __future__ import annotations

from typing import override

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AdvEnigma2UpdateCoordinator


class AdvEnigma2Entity(CoordinatorEntity[AdvEnigma2UpdateCoordinator]):
    """Common behaviour of every entity of the box."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AdvEnigma2UpdateCoordinator, key: str | None = None
    ) -> None:
        """Initialize the entity and attach it to the device of the box."""
        super().__init__(coordinator)

        # every entity of an entry shares the device of the box, so the device
        # information is taken from the coordinator as it is: adding a
        # `via_device` key (even `None`) makes the device registry report a
        # deprecated `via_device` call
        self._attr_device_info = dict(coordinator.device_info)  # type: ignore[assignment]

        # the MAC of the box is unique per box, the entry id is the fallback for
        # devices that do not report one
        identifier = coordinator.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{identifier}-{key}" if key else identifier

    @override
    async def async_added_to_hass(self) -> None:
        """Write the state from the already fetched data.

        `CoordinatorEntity` only writes the state when the coordinator publishes
        the next update, which would leave every entity `unknown` for a whole scan
        interval (30 s) after the entry was set up.
        """
        await super().async_added_to_hass()
        self._handle_coordinator_update()
