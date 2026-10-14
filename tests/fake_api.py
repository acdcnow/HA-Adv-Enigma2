"""A fake for the raw OpenWebif client (api.AdvEnigma2Api).

The class level attributes configure what the fake box answers, so a test can
decide whether it has timers, recordings, a sleep timer or HDMI-CEC power on.
"""

from __future__ import annotations

from typing import Any, ClassVar

from yarl import URL

from tests.fakes import RECORDING_REF, SERVICE_REF, TIMER_BEGIN, TIMER_END

SIGNAL = {"snr": 84, "snr_db": 84, "ber": 0, "agc": 66, "tunernumber": 0, "tunertype": "DVB-S"}

EPG = [
    {
        "id": 4711,
        "title": "Tagesschau",
        "shortdesc": "Nachrichten",
        "longdesc": "Das Wichtigste aus Politik und Wirtschaft.",
        "sname": "Das Erste HD",
        "sref": SERVICE_REF,
        "begin_timestamp": TIMER_BEGIN,
        "duration_sec": 1800,
        "now_timestamp": TIMER_BEGIN,
    },
    {
        "id": 4712,
        "title": "Sportschau",
        "shortdesc": "Bundesliga",
        "longdesc": "Zusammenfassungen der Bundesliga.",
        "sname": "Das Erste HD",
        "sref": SERVICE_REF,
        "begin_timestamp": TIMER_BEGIN + 1800,
        "duration_sec": 2700,
        "now_timestamp": TIMER_BEGIN,
    },
]

TIMERS = [
    {
        "serviceref": SERVICE_REF,
        "servicename": "Das Erste HD",
        "name": "Tagesschau",
        "description": "Nachrichten",
        "eit": 4711,
        "begin": TIMER_BEGIN,
        "end": TIMER_END,
        "duration": TIMER_END - TIMER_BEGIN,
        "disabled": 0,
        "justplay": 0,
        "afterevent": 3,
        "repeated": 0,
        "dirname": "/media/hdd/movie/",
    },
    {
        "serviceref": SERVICE_REF,
        "servicename": "Das Erste HD",
        "name": "Sportschau",
        "description": "",
        "eit": 4712,
        "begin": TIMER_BEGIN + 86400,
        "end": TIMER_END + 86400,
        "duration": TIMER_END - TIMER_BEGIN,
        "disabled": 1,
        "justplay": 0,
        "afterevent": 3,
        "repeated": 0,
        "dirname": "/media/hdd/movie/",
    },
]

MOVIES = [
    {
        "serviceref": RECORDING_REF,
        "fullname": RECORDING_REF,
        "filename": "/media/hdd/movie/20261014 2015 - Das Erste HD - Tagesschau.ts",
        "filename_stripped": "20261014 2015 - Das Erste HD - Tagesschau.ts",
        "eventname": "Tagesschau",
        "title": "Tagesschau",
        "description": "Nachrichten",
        "length": "00:15",
        "servicename": "Das Erste HD",
    }
]

SERVICES = [
    {"servicename": "Das Erste HD", "serviceref": SERVICE_REF},
    {"servicename": "ZDF HD", "serviceref": "1:0:19:2B66:3F3:1:C00000:0:0:0:"},
]

BOUQUETS = [
    [SERVICE_REF.replace("1:0:19:283D:3FB", "1:7:1:0"), "Favourites"],
    ["1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"userbouquet.favourites.tv\"", "Favourites"],
]

SCREENSHOT = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


class FakeApi:
    """Stand-in for `AdvEnigma2Api`."""

    instances: ClassVar[list[FakeApi]] = []

    signal: ClassVar[dict[str, Any] | None] = SIGNAL
    epg: ClassVar[list[dict[str, Any]]] = EPG
    timers: ClassVar[list[dict[str, Any]]] = TIMERS
    movies: ClassVar[list[dict[str, Any]]] = MOVIES
    services: ClassVar[list[dict[str, Any]]] = SERVICES
    sleep_timer: ClassVar[dict[str, Any] | None] = {
        "enabled": False,
        "minutes": 30,
        "action": "standby",
    }
    supports_cec: ClassVar[bool] = False
    screenshot: ClassVar[bytes] = SCREENSHOT
    error: ClassVar[Exception | None] = None

    def __init__(self, session: Any, base_url: URL, headers: Any = None) -> None:
        """Remember the connection details and the calls."""
        self.session = session
        self.base_url = base_url
        self.headers = headers
        self.calls: list[tuple[str, Any]] = []
        FakeApi.instances.append(self)

    @classmethod
    def reset(cls) -> None:
        """Reset the class level configuration."""
        cls.signal = SIGNAL
        cls.epg = EPG
        cls.timers = TIMERS
        cls.movies = MOVIES
        cls.services = SERVICES
        cls.sleep_timer = {"enabled": False, "minutes": 30, "action": "standby"}
        cls.supports_cec = False
        cls.screenshot = SCREENSHOT
        cls.error = None
        cls.instances = []

    @classmethod
    def last(cls) -> FakeApi:
        """Return the client the coordinator created last."""
        return cls.instances[-1]

    def recorded(self, name: str) -> list[Any]:
        """Return the arguments of every recorded call `name`."""
        return [value for call, value in self.calls if call == name]

    def _check(self) -> None:
        """Raise the configured error, if any."""
        if self.error is not None:
            raise self.error

    # -- urls -------------------------------------------------------------

    def screenshot_url(self, mode: str, file_format: str, resolution: int) -> URL:
        """Return the URL of a screen grab."""
        self.calls.append(("screenshot_url", (mode, file_format, resolution)))
        return self.base_url.with_path("/grab").with_query(
            {"mode": mode, "format": file_format, "r": resolution}
        )

    def stream_url(self, serviceref: str) -> str:
        """Return the stream URL of a service."""
        return f"http://{self.base_url.host}:8001/{serviceref}"

    # -- data -------------------------------------------------------------

    async def async_get_tuner_signal(self) -> dict[str, Any]:
        """Return the tuner signal."""
        self._check()
        if self.signal is None:
            raise RuntimeError("no signal")
        return dict(self.signal)

    async def async_get_now_next(self) -> list[dict[str, Any]]:
        """Return the current and the next programme."""
        self._check()
        return list(self.epg)

    async def async_get_timers(self) -> list[dict[str, Any]]:
        """Return the timers."""
        self._check()
        return [dict(timer) for timer in self.timers]

    async def async_get_sleep_timer(self) -> dict[str, Any]:
        """Return the sleep timer."""
        self._check()
        if self.sleep_timer is None:
            raise RuntimeError("no sleep timer")
        return dict(self.sleep_timer)

    async def async_get_recordings(self, dirname: str | None = None) -> list[dict[str, Any]]:
        """Return the recordings."""
        self._check()
        return [dict(movie) for movie in self.movies]

    async def async_get_services(self, bouquet: str) -> list[dict[str, Any]]:
        """Return the channels of a bouquet."""
        self._check()
        self.calls.append(("get_services", bouquet))
        return [dict(service) for service in self.services]

    async def async_get_image(self, url: URL) -> bytes | None:
        """Return the bytes of a screen grab."""
        self._check()
        return self.screenshot

    async def async_supports_cec_power_on(self) -> bool:
        """Return True when the box supports HDMI-CEC power on."""
        self._check()
        return self.supports_cec

    # -- actions ----------------------------------------------------------

    async def async_set_sleep_timer(
        self, enabled: bool, minutes: int, action: str
    ) -> bool:
        """Configure the sleep timer."""
        self._check()
        self.calls.append(("set_sleep_timer", (enabled, minutes, action)))
        self.sleep_timer = {
            "enabled": enabled,
            "minutes": minutes,
            "action": action,
        }
        return True

    async def async_add_timer(self, serviceref: str, begin: int, end: int, name: str, **kwargs: Any) -> bool:
        """Add a timer."""
        self._check()
        self.calls.append(
            ("add_timer", {"serviceref": serviceref, "begin": begin, "end": end, "name": name, **kwargs})
        )
        return True

    async def async_change_timer(
        self,
        serviceref: str,
        begin: int,
        end: int,
        name: str,
        channel_old: str,
        begin_old: int,
        end_old: int,
        **kwargs: Any,
    ) -> bool:
        """Change a timer."""
        self._check()
        self.calls.append(
            (
                "change_timer",
                {
                    "serviceref": serviceref,
                    "begin": begin,
                    "end": end,
                    "name": name,
                    "begin_old": begin_old,
                    "end_old": end_old,
                    **kwargs,
                },
            )
        )
        return True

    async def async_toggle_timer(self, serviceref: str, begin: int, end: int) -> bool:
        """Toggle a timer."""
        self._check()
        self.calls.append(("toggle_timer", (serviceref, begin, end)))
        return True

    async def async_delete_timer(
        self, serviceref: str, begin: int, end: int, eit: int | None = None
    ) -> bool:
        """Delete a timer."""
        self._check()
        self.calls.append(("delete_timer", (serviceref, begin, end, eit)))
        return True

    async def async_cleanup_timers(self) -> bool:
        """Delete the expired timers."""
        self._check()
        self.calls.append(("cleanup_timers", None))
        return True

    async def async_record_now(self, infinite: bool = False) -> bool:
        """Record the running programme."""
        self._check()
        self.calls.append(("record_now", infinite))
        return True

    async def async_delete_recording(self, serviceref: str, force: bool = False) -> bool:
        """Delete a recording."""
        self._check()
        self.calls.append(("delete_recording", (serviceref, force)))
        return True

    async def async_rename_recording(self, serviceref: str, newname: str) -> bool:
        """Rename a recording."""
        self._check()
        self.calls.append(("rename_recording", (serviceref, newname)))
        return True

    async def async_send_remote_control(
        self, command: int, rc_type: str | None = None
    ) -> bool:
        """Send a remote control key."""
        self._check()
        self.calls.append(("send_remote_control", (command, rc_type)))
        return True

    async def async_power_on_without_waking_tv(self) -> bool:
        """Power on without waking the TV."""
        self._check()
        self.calls.append(("power_on_without_waking_tv", None))
        return True


def timer_time(value: int) -> str:
    """Return a timestamp as an ISO string, for the assertions."""
    return dt_util.utc_from_timestamp(value).isoformat()
