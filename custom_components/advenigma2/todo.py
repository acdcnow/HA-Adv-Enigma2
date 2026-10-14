"""The timers of the box as a to-do list."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, override

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import timer_due, timer_uid
from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .entity import AdvEnigma2Entity

# Creating a timer needs a channel, which a to-do item cannot carry: use the
# `advenigma2.add_timer` service for that. Disabling (the checkbox), moving the
# due date and deleting are supported from the to-do list.
SUPPORTED_FEATURES = (
    TodoListEntityFeature.DELETE_TODO_ITEM
    | TodoListEntityFeature.UPDATE_TODO_ITEM
    | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdvEnigma2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list of the box."""
    async_add_entities([AdvEnigma2TimerList(entry.runtime_data)])


class AdvEnigma2TimerList(AdvEnigma2Entity, TodoListEntity):
    """The recording timers of the box.

    A checked item means the timer is disabled, an unchecked one that it will be
    recorded. The due date is the begin of the timer.
    """

    _attr_translation_key = "timers"
    _attr_icon = "mdi:calendar-clock"
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, coordinator: AdvEnigma2UpdateCoordinator) -> None:
        """Initialize the to-do list."""
        super().__init__(coordinator, "timers")

    @override
    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return the timers of the box."""
        items: list[TodoItem] = []
        for timer in self.coordinator.timers:
            items.append(
                TodoItem(
                    uid=timer_uid(timer),
                    summary=timer.get("name") or "Timer",
                    status=(
                        TodoItemStatus.COMPLETED
                        if timer.get("disabled")
                        else TodoItemStatus.NEEDS_ACTION
                    ),
                    due=timer_due(timer),
                    description=_timer_description(timer),
                )
            )
        return items

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete the timers in `uids`."""
        for uid in uids:
            timer = self._timer(uid)
            await self.coordinator.api.async_delete_timer(
                timer["serviceref"],
                int(timer["begin"]),
                int(timer["end"]),
                timer.get("eit"),
            )
        await self.coordinator.async_request_refresh()

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Apply a change made in the to-do list to the timer."""
        timer = self._timer(item.uid)
        serviceref = timer["serviceref"]
        begin = int(timer["begin"])
        end = int(timer["end"])
        name = timer.get("name") or "Timer"

        new_name = item.summary or name
        new_begin = _begin_of(item.due, begin)
        new_end = end + (new_begin - begin)

        if new_name != name or new_begin != begin:
            await self.coordinator.api.async_change_timer(
                serviceref,
                new_begin,
                new_end,
                new_name,
                serviceref,
                begin,
                end,
                description=timer.get("description") or None,
            )

        wants_disabled = item.status == TodoItemStatus.COMPLETED
        if wants_disabled != bool(timer.get("disabled")):
            await self.coordinator.api.async_toggle_timer(
                serviceref, new_begin, new_end
            )

        await self.coordinator.async_request_refresh()

    def _timer(self, uid: str | None) -> dict[str, Any]:
        """Return the timer of a to-do item."""
        for timer in self.coordinator.timers:
            if timer_uid(timer) == uid:
                return timer
        raise HomeAssistantError(f"The timer {uid} is no longer on the box")


def _begin_of(due: date | datetime | None, current_begin: int) -> int:
    """Return the begin timestamp for a due date.

    A date without a time keeps the time of the timer, a datetime is used as is.
    """
    if isinstance(due, datetime):
        return int(due.timestamp())
    if isinstance(due, date):
        return int(
            datetime.combine(
                due, datetime.fromtimestamp(current_begin).time()
            ).timestamp()
        )
    return current_begin


def _timer_description(timer: dict[str, Any]) -> str:
    """Return the channel and the time of a timer."""
    channel = timer.get("servicename") or ""
    description = timer.get("description") or ""
    if not description:
        return channel
    return f"{channel} · {description}".strip(" ·")


def _parse_time(timer: dict[str, Any], key: str) -> time | None:
    """Return the begin or end of a timer as a time of day."""
    value = timer.get(key)
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value).time()
