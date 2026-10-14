"""Services of the Adv Enigma2 integration.

Everything that cannot be an entity is a service here: the OpenWebif endpoints for
messages, remote control keys, timers (creating one needs a channel) and
recordings (deleting and renaming one needs a path).
"""

from __future__ import annotations

from openwebif.enums import MessageType, RemoteControlCodes
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    AFTEREVENT_AUTO,
    AFTEREVENT_DEEP_STANDBY,
    AFTEREVENT_STANDBY,
    DOMAIN,
)
from .coordinator import AdvEnigma2UpdateCoordinator

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_SEND_REMOTE_CONTROL = "send_remote_control"
SERVICE_ADD_TIMER = "add_timer"
SERVICE_REMOVE_TIMER = "remove_timer"
SERVICE_DELETE_RECORDING = "delete_recording"
SERVICE_RENAME_RECORDING = "rename_recording"

SERVICES = (
    SERVICE_SEND_MESSAGE,
    SERVICE_SEND_REMOTE_CONTROL,
    SERVICE_ADD_TIMER,
    SERVICE_REMOVE_TIMER,
    SERVICE_DELETE_RECORDING,
    SERVICE_RENAME_RECORDING,
)

MESSAGE_TYPES = {
    "info": MessageType.INFO,
    "warning": MessageType.WARNING,
    "error": MessageType.ERROR,
    "yesno": MessageType.YESNO,
}

REMOTE_CONTROL_TYPES = ["standard", "long", "ascii"]

AFTEREVENT_OPTIONS = {
    "standby": AFTEREVENT_STANDBY,
    "deep_standby": AFTEREVENT_DEEP_STANDBY,
    "auto": AFTEREVENT_AUTO,
}

REMOTE_CONTROL_COMMANDS = sorted(member.name for member in RemoteControlCodes)


TARGET_SCHEMA = {
    vol.Optional(ATTR_DEVICE_ID): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
}


def _coordinator(call: ServiceCall) -> AdvEnigma2UpdateCoordinator:
    """Return the coordinator of the box the service call targets.

    The services take the device of the box, or any of its entities.
    """
    hass = call.hass
    devices = dr.async_get(hass)

    device = None
    if device_id := call.data.get(ATTR_DEVICE_ID):
        device = devices.async_get(device_id)
    elif entity_ids := call.data.get(ATTR_ENTITY_ID):
        entry = er.async_get(hass).async_get(entity_ids[0])
        if entry is not None and entry.device_id:
            device = devices.async_get(entry.device_id)

    if device is None or device.config_entry_id is None:
        raise HomeAssistantError("This service targets a device of Adv Enigma2")

    config_entry = hass.config_entries.async_get_entry(device.config_entry_id)
    if config_entry is None or config_entry.domain != DOMAIN:
        raise HomeAssistantError("This service targets a device of Adv Enigma2")

    return config_entry.runtime_data


def _resolve_channel(coordinator: AdvEnigma2UpdateCoordinator, channel: str) -> str:
    """Return the service reference of a channel name or reference."""
    return coordinator.device.sources.get(channel, channel)


async def _async_send_message(call: ServiceCall) -> None:
    """Show a message on the TV screen."""
    await _coordinator(call).device.send_message(
        call.data["message"],
        MESSAGE_TYPES[call.data["type"]],
        call.data["timeout"],
    )


async def _async_send_remote_control(call: ServiceCall) -> None:
    """Press a key on the remote control of the box."""
    command = getattr(RemoteControlCodes, call.data["command"])
    await _coordinator(call).api.async_send_remote_control(
        command.value, call.data["type"]
    )


async def _async_add_timer(call: ServiceCall) -> None:
    """Add a recording timer."""
    coordinator = _coordinator(call)
    begin = cv.datetime(call.data["begin"])
    end = cv.datetime(call.data["end"])
    if end <= begin:
        raise HomeAssistantError("`end` must be after `begin`")

    await coordinator.api.async_add_timer(
        _resolve_channel(coordinator, call.data["channel"]),
        int(begin.timestamp()),
        int(end.timestamp()),
        call.data["name"],
        description=call.data.get("description"),
        disabled=call.data["disabled"],
        justplay=call.data["justplay"],
        afterevent=AFTEREVENT_OPTIONS[call.data["afterevent"]],
        dirname=call.data.get("dirname"),
        tags=call.data.get("tags"),
    )
    await coordinator.async_request_refresh()


async def _async_remove_timer(call: ServiceCall) -> None:
    """Delete a recording timer."""
    coordinator = _coordinator(call)
    begin = cv.datetime(call.data["begin"])
    end = cv.datetime(call.data["end"])
    await coordinator.api.async_delete_timer(
        _resolve_channel(coordinator, call.data["channel"]),
        int(begin.timestamp()),
        int(end.timestamp()),
    )
    await coordinator.async_request_refresh()


async def _async_delete_recording(call: ServiceCall) -> None:
    """Delete a recording from the hard disk of the box."""
    await _coordinator(call).api.async_delete_recording(
        call.data["recording"], call.data["force"]
    )


async def _async_rename_recording(call: ServiceCall) -> None:
    """Rename a recording on the hard disk of the box."""
    await _coordinator(call).api.async_rename_recording(
        call.data["recording"], call.data["name"]
    )


SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required("message"): cv.string,
        vol.Optional("type", default="info"): vol.In(MESSAGE_TYPES),
        vol.Optional("timeout", default=-1): vol.All(
            vol.Coerce(int), vol.Range(min=-1, max=3600)
        ),
    }
)

SEND_REMOTE_CONTROL_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required("command"): vol.In(REMOTE_CONTROL_COMMANDS),
        vol.Optional("type", default="standard"): vol.In(REMOTE_CONTROL_TYPES),
    }
)

ADD_TIMER_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required("channel"): cv.string,
        vol.Required("begin"): cv.datetime,
        vol.Required("end"): cv.datetime,
        vol.Required("name"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("disabled", default=False): cv.boolean,
        vol.Optional("justplay", default=False): cv.boolean,
        vol.Optional("afterevent", default="auto"): vol.In(AFTEREVENT_OPTIONS),
        vol.Optional("dirname"): cv.string,
        vol.Optional("tags"): cv.string,
    }
)

REMOVE_TIMER_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required("channel"): cv.string,
        vol.Required("begin"): cv.datetime,
        vol.Required("end"): cv.datetime,
    }
)

DELETE_RECORDING_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required("recording"): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    }
)

RENAME_RECORDING_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required("recording"): cv.string,
        vol.Required("name"): cv.string,
    }
)


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the services of the integration (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        return

    for name, schema, handler in (
        (SERVICE_SEND_MESSAGE, SEND_MESSAGE_SCHEMA, _async_send_message),
        (
            SERVICE_SEND_REMOTE_CONTROL,
            SEND_REMOTE_CONTROL_SCHEMA,
            _async_send_remote_control,
        ),
        (SERVICE_ADD_TIMER, ADD_TIMER_SCHEMA, _async_add_timer),
        (SERVICE_REMOVE_TIMER, REMOVE_TIMER_SCHEMA, _async_remove_timer),
        (SERVICE_DELETE_RECORDING, DELETE_RECORDING_SCHEMA, _async_delete_recording),
        (SERVICE_RENAME_RECORDING, RENAME_RECORDING_SCHEMA, _async_rename_recording),
    ):
        hass.services.async_register(DOMAIN, name, handler, schema)


@callback
def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove the services of the integration."""
    for name in SERVICES:
        hass.services.async_remove(DOMAIN, name)


__all__ = [
    "SERVICES",
    "async_register_services",
    "async_unregister_services",
]
