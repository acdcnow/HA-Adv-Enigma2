"""Unit tests for the sleep timer of the box."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from tests.fake_api import FakeApi
from tests.helpers import entity_id, setup_entry


async def test_sleep_timer_starts_disabled(hass: HomeAssistant, make_entry) -> None:
    """A sleep timer that is off shows zero minutes."""
    await setup_entry(hass, make_entry)

    state = hass.states.get(entity_id(hass, "number", "sleep_timer"))

    assert state.state == "0"
    assert state.attributes["action"] == "standby"


async def test_sleep_timer_can_be_set(hass: HomeAssistant, make_entry) -> None:
    """Setting minutes configures the sleep timer on the box."""
    await setup_entry(hass, make_entry)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", "sleep_timer"), "value": 45},
        blocking=True,
    )

    assert FakeApi.last().recorded("set_sleep_timer") == [(True, 45, "standby")]


async def test_sleep_timer_can_be_turned_off(hass: HomeAssistant, make_entry) -> None:
    """Setting zero turns the sleep timer off."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "number", "sleep_timer")

    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity, "value": 15}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity, "value": 0}, blocking=True
    )

    assert FakeApi.last().recorded("set_sleep_timer") == [
        (True, 15, "standby"),
        (False, 0, "standby"),
    ]


async def test_sleep_timer_action_can_be_chosen(
    hass: HomeAssistant, make_entry
) -> None:
    """The action select changes what the sleep timer does."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "select", "sleep_timer_action")

    assert hass.states.get(entity).state == "standby"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity, "option": "shutdown"}, blocking=True
    )

    assert FakeApi.last().recorded("set_sleep_timer") == [(False, 30, "shutdown")]
    assert hass.states.get(entity).state == "shutdown"
