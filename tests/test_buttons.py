"""Unit tests for the buttons of the box."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from openwebif.enums import PowerState

from tests.fake_api import FakeApi
from tests.helpers import entity_id, setup_entry


async def press(hass: HomeAssistant, name: str) -> None:
    """Press one button of the box."""
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", name)}, blocking=True
    )


async def test_power_buttons(hass: HomeAssistant, make_entry, fake_device) -> None:
    """Reboot, restart Enigma2, standby and deep standby reach the box."""
    await setup_entry(hass, make_entry)

    for name in ("reboot", "restart_enigma2", "standby", "deep_standby"):
        await press(hass, name)

    assert fake_device.last().recorded("set_powerstate") == [
        PowerState.REBOOT,
        PowerState.RESTART_ENIGMA,
        PowerState.STANDBY,
        PowerState.DEEP_STANDBY,
    ]


async def test_record_and_cleanup_buttons(
    hass: HomeAssistant, make_entry
) -> None:
    """Recording the running programme and cleaning up timers works."""
    await setup_entry(hass, make_entry)

    await press(hass, "record_now")
    await press(hass, "cleanup_timers")

    api = FakeApi.last()
    assert api.recorded("record_now") == [False]
    assert api.recorded("cleanup_timers") == [None]


async def test_cec_button_is_unavailable_without_support(
    hass: HomeAssistant, make_entry
) -> None:
    """The HDMI-CEC power on button is hidden when the box cannot do it."""
    FakeApi.supports_cec = False
    await setup_entry(hass, make_entry)

    state = hass.states.get(entity_id(hass, "button", "power_on_without_waking_tv"))

    assert state is not None
    assert state.state == "unavailable"


async def test_cec_button_powers_the_box_on(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """The HDMI-CEC power on button works when the box supports it."""
    FakeApi.supports_cec = True
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "button", "power_on_without_waking_tv")
    assert hass.states.get(entity).state != "unavailable"

    fake_device.last().turn_off_to_deep = True
    await hass.services.async_call("button", "press", {"entity_id": entity}, blocking=True)

    assert FakeApi.last().recorded("power_on_without_waking_tv") == [None]
