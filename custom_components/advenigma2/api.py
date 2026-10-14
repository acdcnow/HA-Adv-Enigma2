"""Raw OpenWebif calls for the endpoints that openwebifpy does not cover.

`openwebifpy` only implements status, power, volume, zapping, the remote control,
screen messages, the screenshot URL and bouquets. Everything else the integration
uses (timers, recordings, tuner signal, sleep timer, current EPG, HDMI-CEC power
on) is a plain JSON call on the same aiohttp session, so the polling, the offline
back-off and the credentials keep working unchanged.

See https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/wiki/OpenWebif-API-documentation
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Final

import aiohttp
from yarl import URL

from homeassistant.util import dt as dt_util

LOGGER = logging.getLogger(__package__)

PATH_GRAB = "/grab"
PATH_TIMERLIST = "/api/timerlist"
PATH_TIMERADD = "/api/timeradd"
PATH_TIMERCHANGE = "/api/timerchange"
PATH_TIMERTOGGLESTATUS = "/api/timertogglestatus"
PATH_TIMERDELETE = "/api/timerdelete"
PATH_TIMERCLEANUP = "/api/timercleanup"
PATH_RECORDNOW = "/api/recordnow"
PATH_REMOTECONTROL = "/api/remotecontrol"
PATH_MOVIELIST = "/api/movielist"
PATH_GETSERVICES = "/api/getservices"
PATH_MOVIEDELETE = "/api/moviedelete"
PATH_MOVIERENAME = "/api/movierename"
PATH_TUNERSIGNAL = "/api/tunersignal"
PATH_SLEEPTIMER = "/api/sleeptimer"
PATH_GETCURRENT = "/api/getcurrent"
PATH_SUPPORTS_CEC = "/api/supports_powerup_without_waking_tv"
PATH_SET_CEC = "/api/set_powerup_without_waking_tv"

# OpenWebif serves the streams on its own port
STREAM_PORT: Final = 8001


class AdvEnigma2ApiError(Exception):
    """Raised when OpenWebif answers something that is not a JSON result."""


class AdvEnigma2Api:
    """The OpenWebif endpoints openwebifpy does not implement."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: URL,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Store the session and the base url of the box (without credentials)."""
        self._session = session
        self._base_url = base_url
        self._headers = headers

    @property
    def host(self) -> str:
        """Return the host of the box."""
        return str(self._base_url.host or "")

    def screenshot_url(
        self, mode: str, file_format: str, resolution: int
    ) -> URL:
        """Return the URL of a screen grab of the box."""
        return self._base_url.with_path(PATH_GRAB).with_query(
            {"mode": mode, "format": file_format, "r": resolution}
        )

    def stream_url(self, serviceref: str) -> str:
        """Return the URL that streams a service of the box."""
        return str(self._base_url.with_port(STREAM_PORT).with_path(f"/{serviceref}"))

    # -- plumbing ---------------------------------------------------------

    async def _async_call(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call an endpoint and return the JSON body."""
        async with self._session.get(
            self._base_url.with_path(path), params=params, headers=self._headers
        ) as response:
            response.raise_for_status()
            return await self._async_json(response)

    @staticmethod
    async def _async_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
        """Parse the JSON body of a response."""
        text = await response.text()
        try:
            payload = json.loads(text)
        except ValueError as err:
            raise AdvEnigma2ApiError(
                f"{response.url} did not answer with JSON: {text.strip()[:120]}"
            ) from err
        if not isinstance(payload, dict):
            raise AdvEnigma2ApiError(f"{response.url} did not answer with an object")
        return payload

    @staticmethod
    def _ok(payload: dict[str, Any]) -> bool:
        """Return the `result` flag of a JSON answer."""
        return bool(payload.get("result", False))

    async def async_get_image(self, url: URL) -> bytes | None:
        """Download the bytes of a screen grab."""
        async with self._session.get(url, headers=self._headers) as response:
            if response.status != 200:
                LOGGER.debug("Screen grab failed with HTTP %s", response.status)
                return None
            return await response.read()

    # -- general information ---------------------------------------------

    async def async_get_tuner_signal(self) -> dict[str, Any]:
        """Return the tuner signal (snr, snr_db, ber, agc)."""
        return await self._async_call(PATH_TUNERSIGNAL)

    async def async_get_services(self, bouquet: str) -> list[dict[str, Any]]:
        """Return the channels of a bouquet (for the channel browser)."""
        payload = await self._async_call(PATH_GETSERVICES, {"sRef": bouquet})
        return list(payload.get("services", []))

    async def async_get_now_next(self) -> list[dict[str, Any]]:
        """Return the current and the following programme of the running service."""
        payload = await self._async_call(PATH_GETCURRENT)
        return list(payload.get("events", []))

    async def async_supports_cec_power_on(self) -> bool:
        """Return True if the box can power on without waking the TV."""
        async with self._session.get(
            self._base_url.with_path(PATH_SUPPORTS_CEC), headers=self._headers
        ) as response:
            if response.status != 200:
                return False
            return (await response.text()).strip().lower() == "true"

    async def async_power_on_without_waking_tv(self) -> bool:
        """Power the box on without waking the TV over HDMI-CEC."""
        return self._ok(await self._async_call(PATH_SET_CEC))

    # -- timers ----------------------------------------------------------

    async def async_get_timers(self) -> list[dict[str, Any]]:
        """Return the timers of the box."""
        payload = await self._async_call(PATH_TIMERLIST)
        return list(payload.get("timers", []))

    async def async_add_timer(
        self,
        serviceref: str,
        begin: int,
        end: int,
        name: str,
        *,
        description: str | None = None,
        disabled: bool = False,
        justplay: bool = False,
        afterevent: int | None = None,
        dirname: str | None = None,
        tags: str | None = None,
        eit: int | None = None,
    ) -> bool:
        """Add a timer to the box."""
        params: dict[str, Any] = {
            "sRef": serviceref,
            "begin": begin,
            "end": end,
            "name": name,
            "disabled": int(disabled),
            "justplay": int(justplay),
        }
        if description is not None:
            params["description"] = description
        if afterevent is not None:
            params["afterevent"] = afterevent
        if dirname:
            params["dirname"] = dirname
        if tags:
            params["tags"] = tags
        if eit is not None:
            params["eit"] = eit
        return self._ok(await self._async_call(PATH_TIMERADD, params))

    async def async_toggle_timer(self, serviceref: str, begin: int, end: int) -> bool:
        """Enable or disable a timer; returns the new disabled state."""
        payload = await self._async_call(
            PATH_TIMERTOGGLESTATUS,
            {"sRef": serviceref, "begin": begin, "end": end},
        )
        return bool(payload.get("disabled", False))

    async def async_change_timer(
        self,
        serviceref: str,
        begin: int,
        end: int,
        name: str,
        channel_old: str,
        begin_old: int,
        end_old: int,
        *,
        description: str | None = None,
    ) -> bool:
        """Change the time, the name or the description of a timer."""
        params: dict[str, Any] = {
            "sRef": serviceref,
            "begin": begin,
            "end": end,
            "name": name,
            "channelOld": channel_old,
            "beginOld": begin_old,
            "endOld": end_old,
        }
        if description is not None:
            params["description"] = description
        return self._ok(await self._async_call(PATH_TIMERCHANGE, params))

    async def async_delete_timer(
        self, serviceref: str, begin: int, end: int, eit: int | None = None
    ) -> bool:
        """Delete a timer."""
        params: dict[str, Any] = {"sRef": serviceref, "begin": begin, "end": end}
        if eit is not None:
            params["eit"] = eit
        return self._ok(await self._async_call(PATH_TIMERDELETE, params))

    async def async_cleanup_timers(self) -> bool:
        """Delete the expired timers."""
        return self._ok(await self._async_call(PATH_TIMERCLEANUP))

    async def async_record_now(self, infinite: bool = False) -> bool:
        """Start recording the running programme."""
        params = {"infinite": 1} if infinite else None
        return self._ok(await self._async_call(PATH_RECORDNOW, params))

    # -- recordings ------------------------------------------------------

    async def async_get_recordings(self, dirname: str | None = None) -> list[dict[str, Any]]:
        """Return the recordings in the movie folder of the box."""
        params = {"dirname": dirname} if dirname else None
        payload = await self._async_call(PATH_MOVIELIST, params)
        return list(payload.get("movies", []))

    async def async_delete_recording(self, serviceref: str, force: bool = False) -> bool:
        """Delete a recording."""
        params: dict[str, Any] = {"sRef": serviceref}
        if force:
            params["force"] = 1
        return self._ok(await self._async_call(PATH_MOVIEDELETE, params))

    async def async_rename_recording(self, serviceref: str, newname: str) -> bool:
        """Rename a recording."""
        return self._ok(
            await self._async_call(
                PATH_MOVIERENAME, {"sRef": serviceref, "newname": newname}
            )
        )

    # -- remote control --------------------------------------------------

    async def async_send_remote_control(
        self, command: int, rc_type: str | None = None
    ) -> bool:
        """Send a remote control key; `rc_type` is standard, long or ascii."""
        params: dict[str, Any] = {"command": command}
        if rc_type and rc_type != "standard":
            params["type"] = rc_type
        return self._ok(await self._async_call(PATH_REMOTECONTROL, params))

    # -- sleep timer -----------------------------------------------------

    async def async_get_sleep_timer(self) -> dict[str, Any]:
        """Return the sleep timer configuration."""
        return await self._async_call(PATH_SLEEPTIMER, {"cmd": "get"})

    async def async_set_sleep_timer(
        self, enabled: bool, minutes: int, action: str
    ) -> bool:
        """Configure the sleep timer."""
        return self._ok(
            await self._async_call(
                PATH_SLEEPTIMER,
                {
                    "cmd": "set",
                    "enabled": str(bool(enabled)),
                    "time": int(minutes),
                    "action": action,
                    "confirmed": "True",
                },
            )
        )


def timer_uid(timer: Mapping[str, Any]) -> str:
    """Return the unique ID of a timer."""
    return f"{timer.get('serviceref')}|{timer.get('begin')}|{timer.get('end')}"


def timer_due(timer: Mapping[str, Any]) -> Any:
    """Return the begin of a timer as an aware datetime."""
    begin = timer.get("begin")
    return dt_util.utc_from_timestamp(begin) if isinstance(begin, (int, float)) else None


def recording_uid(movie: Mapping[str, Any]) -> str:
    """Return the unique ID of a recording (its service reference)."""
    return str(movie.get("fullname") or movie.get("serviceref") or movie.get("filename"))


def now_next_event(events: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    """Return the event at `index` of a `/api/getcurrent` answer."""
    if len(events) > index:
        return events[index]
    return None
