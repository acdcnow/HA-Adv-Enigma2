"""Unit tests for the timers of the box (the to-do list)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.fake_api import FakeApi
from tests.fakes import SERVICE_REF, TIMER_BEGIN, TIMER_END
from tests.helpers import entity_id, setup_entry

UID_FIRST = f"{SERVICE_REF}|{TIMER_BEGIN}|{TIMER_END}"
UID_SECOND = f"{SERVICE_REF}|{TIMER_BEGIN + 86400}|{TIMER_END + 86400}"


async def get_items(hass: HomeAssistant, entity: str) -> list[dict]:
    """Return the timers as the to-do list shows them."""
    response = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": entity},
        blocking=True,
        return_response=True,
    )
    return response[entity]["items"]


async def test_timers_are_listed(hass: HomeAssistant, make_entry) -> None:
    """The timers of the box show up with name, channel, time and state."""
    await setup_entry(hass, make_entry)

    items = await get_items(hass, entity_id(hass, "todo", "timers"))

    assert [item["summary"] for item in items] == ["Tagesschau", "Sportschau"]
    # a disabled timer of the box is a checked item of the list
    assert [item["status"] for item in items] == ["needs_action", "completed"]
    assert [item["uid"] for item in items] == [UID_FIRST, UID_SECOND]
    assert items[0]["description"] == "Das Erste HD · Nachrichten"
    assert items[0]["due"] == dt_util.utc_from_timestamp(TIMER_BEGIN).isoformat()


async def test_timer_can_be_disabled_and_enabled(
    hass: HomeAssistant, make_entry
) -> None:
    """Checking a timer disables it, unchecking enables it again."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "todo", "timers")

    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": entity, "item": UID_FIRST, "status": "completed"},
        blocking=True,
    )

    assert FakeApi.last().recorded("toggle_timer") == [
        (SERVICE_REF, TIMER_BEGIN, TIMER_END)
    ]


async def test_timer_can_be_moved(hass: HomeAssistant, make_entry) -> None:
    """Changing the due date of an item moves the timer, keeping its duration."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "todo", "timers")
    new_begin = TIMER_BEGIN + 3600

    await hass.services.async_call(
        "todo",
        "update_item",
        {
            "entity_id": entity,
            "item": UID_FIRST,
            "due_datetime": dt_util.utc_from_timestamp(new_begin).isoformat(),
        },
        blocking=True,
    )

    assert FakeApi.last().recorded("change_timer") == [
        {
            "serviceref": SERVICE_REF,
            "begin": new_begin,
            "end": TIMER_END + 3600,
            "name": "Tagesschau",
            "begin_old": TIMER_BEGIN,
            "end_old": TIMER_END,
            "description": "Nachrichten",
        }
    ]


async def test_timer_can_be_renamed(hass: HomeAssistant, make_entry) -> None:
    """Renaming a to-do item renames the timer on the box."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "todo", "timers")

    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": entity, "item": UID_FIRST, "rename": "Tagesschau um zehn"},
        blocking=True,
    )

    assert FakeApi.last().recorded("change_timer")[0]["name"] == "Tagesschau um zehn"


async def test_timer_can_be_deleted(hass: HomeAssistant, make_entry) -> None:
    """Deleting an item deletes the timer on the box."""
    await setup_entry(hass, make_entry)
    entity = entity_id(hass, "todo", "timers")

    await hass.services.async_call(
        "todo", "remove_item", {"entity_id": entity, "item": [UID_FIRST]}, blocking=True
    )

    assert FakeApi.last().recorded("delete_timer") == [
        (SERVICE_REF, TIMER_BEGIN, TIMER_END, 4711)
    ]
