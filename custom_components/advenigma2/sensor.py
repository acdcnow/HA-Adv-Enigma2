"""Sensors for the Adv Enigma2 box."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import now_next_event
from .const import DOMAIN
from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .entity import AdvEnigma2Entity


def _signal_value(key: str) -> Callable[[AdvEnigma2UpdateCoordinator], Any]:
    """Return a function that reads one value of the tuner signal."""

    def _value(coordinator: AdvEnigma2UpdateCoordinator) -> Any:
        if not coordinator.signal:
            return None
        return coordinator.signal.get(key)

    return _value


def _image_version(coordinator: AdvEnigma2UpdateCoordinator) -> str | None:
    """Return the image that runs on the box, e.g. `openatv 8.0`."""
    distro = coordinator.about.get("imagedistro")
    version = coordinator.about.get("imagever")
    if not distro and not version:
        return None
    return " ".join(part for part in (distro, version) if part)


def _event(index: int) -> Callable[[AdvEnigma2UpdateCoordinator], Any]:
    """Return a function that reads the title of the now (0) or next (1) event."""

    def _value(coordinator: AdvEnigma2UpdateCoordinator) -> Any:
        event = now_next_event(coordinator.epg, index)
        return event.get("title") if event else None

    return _value


def _event_attributes(index: int) -> Callable[[AdvEnigma2UpdateCoordinator], dict[str, Any]]:
    """Return a function that describes the now (0) or next (1) event."""

    def _attributes(coordinator: AdvEnigma2UpdateCoordinator) -> dict[str, Any]:
        event = now_next_event(coordinator.epg, index)
        if not event:
            return {}
        begin = dt_util.utc_from_timestamp(event["begin_timestamp"])
        attributes: dict[str, Any] = {
            "channel": event.get("sname"),
            "begin": begin,
            "end": begin + _timedelta(event.get("duration_sec")),
            "duration": _timedelta(event.get("duration_sec")),
            "description": event.get("shortdesc") or "",
            "event_id": event.get("id"),
        }
        return attributes

    return _attributes


def _timedelta(seconds: Any) -> timedelta:
    """Return a timedelta for a number of seconds."""
    return timedelta(seconds=seconds or 0)


@dataclass(frozen=True, kw_only=True)
class AdvEnigma2SensorDescription(SensorEntityDescription):
    """Describes a sensor of the box."""

    value_fn: Callable[[AdvEnigma2UpdateCoordinator], Any]
    attrs_fn: Callable[[AdvEnigma2UpdateCoordinator], dict[str, Any]] | None = None


SENSORS: tuple[AdvEnigma2SensorDescription, ...] = (
    AdvEnigma2SensorDescription(
        key="signal_snr",
        translation_key="signal_snr",
        icon="mdi:signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_signal_value("snr"),
    ),
    AdvEnigma2SensorDescription(
        key="signal_agc",
        translation_key="signal_agc",
        icon="mdi:signal-variant",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_signal_value("agc"),
    ),
    AdvEnigma2SensorDescription(
        key="signal_ber",
        translation_key="signal_ber",
        icon="mdi:signal-cellular-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_signal_value("ber"),
    ),
    AdvEnigma2SensorDescription(
        key="image_version",
        translation_key="image_version",
        icon="mdi:image-multiple-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_image_version,
    ),
    AdvEnigma2SensorDescription(
        key="now_playing",
        translation_key="now_playing",
        icon="mdi:television-play",
        value_fn=_event(0),
        attrs_fn=_event_attributes(0),
    ),
    AdvEnigma2SensorDescription(
        key="next_programme",
        translation_key="next_programme",
        icon="mdi:television-guide",
        value_fn=_event(1),
        attrs_fn=_event_attributes(1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdvEnigma2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of the box."""
    async_add_entities(
        AdvEnigma2Sensor(entry.runtime_data, description) for description in SENSORS
    )


class AdvEnigma2Sensor(AdvEnigma2Entity, SensorEntity):
    """A sensor that reads its value from the coordinator."""

    entity_description: AdvEnigma2SensorDescription

    def __init__(
        self,
        coordinator: AdvEnigma2UpdateCoordinator,
        description: AdvEnigma2SensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        # the name of the entity comes from the translations, like the key
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the details of an EPG entry."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator) or None
