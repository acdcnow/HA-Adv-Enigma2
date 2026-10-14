"""Stand-ins for the OpenWebIf client used by the Adv Enigma2 unit tests.

The fakes implement exactly the surface of ``openwebif.api.OpenWebIfDevice`` and
``openwebif.api.OpenWebIfStatus`` that the integration touches, so the tests run
without a real Enigma2 box and without network access. The payloads are copied
from the OpenWebIF API documentation so that the parsing paths are exercised with
realistic data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from homeassistant.util import dt as dt_util
from yarl import URL

# Service reference of "Das Erste HD", as it appears on an OpenATV box
SERVICE_REF = "1:0:19:283D:3FB:1:C00000:0:0:0:"
RECORDING_REF = (
    "1:0:0:0:0:0:0:0:0:0:/media/hdd/movie/20261014 2015 - Das Erste HD - "
    "Tagesschau.ts"
)
MAC = "AA:BB:CC:DD:EE:FF"

# begin/end of the fixture timer, 2026-10-14 20:15 and 21:15 UTC
TIMER_BEGIN = 1792076100
TIMER_END = 1792079700

# Shape of the /api/about response (openwebifpy 4.3.1)
ABOUT: dict[str, Any] = {
    "info": {
        "brand": "GigaBlue",
        "model": "UHD Quad 4K Pro",
        "boxtype": "gbquad4kpro",
        "imagever": "8.0",
        "imagedistro": "openatv",
        "webifver": "OWIF 2.0",
        "uptime": "1:20",
        "transcoding": True,
        "hdd": [{"model": "ATA(WD20EZRZ)", "capacity": "1.82 TB", "free": "1405.121 GB"}],
        "tuners": [{"name": "Tuner A", "type": "DVB-S2"}],
        "ifaces": [
            {
                "name": "eth0",
                "mac": MAC,
                "ip": "192.168.1.23",
                "dhcp": True,
                "mask": "255.255.255.0",
                "gw": "192.168.1.1",
                "firstpublic": None,
                "v4prefix": 24,
                "ipv6": "none",
            }
        ],
    },
    "service": {
        "name": "Das Erste HD",
        "provider": "ARD",
        "ref": SERVICE_REF,
        "width": 1280,
        "height": 720,
        "aspect": 3,
    },
}

SOURCES = {"Das Erste HD": SERVICE_REF}


@dataclass
class FakeServiceEvent:
    """The service that is currently playing."""

    filename: str | None = None
    id: int | None = 1234
    name: str | None = "Tagesschau"
    serviceref: str | None = SERVICE_REF
    begin: str | None = "10:00"
    begin_timestamp: int | None = 1476644933
    end: str | None = "10:30"
    end_timestamp: int | None = 1476646733
    description: str | None = "Nachrichten"
    fulldescription: str | None = "Tagesschau\n10:00 - 10:30\nNachrichten"
    station: str | None = "Das Erste HD"


@dataclass
class FakeStatus:
    """The parsed /api/statusinfo response."""

    currservice: FakeServiceEvent = field(default_factory=FakeServiceEvent)
    volume: int | None = 42
    muted: bool = False
    in_standby: bool = False
    is_recording: bool = False
    streaming_list: str | None = None
    is_streaming: bool | None = False
    status_info: dict[str, Any] | None = None
    is_recording_playback: bool | None = False


class FakeOpenWebIfDevice:
    """Minimal stand-in for ``openwebif.api.OpenWebIfDevice``.

    Class level attributes configure what the fake box answers, so a test can
    simulate a box that is switched off (``update_error``) or that rejects the
    credentials (``about_error``).
    """

    about: ClassVar[dict[str, Any]] = ABOUT
    about_error: ClassVar[Exception | None] = None
    update_error: ClassVar[Exception | None] = None
    instances: ClassVar[list[FakeOpenWebIfDevice]] = []

    def __init__(
        self,
        host: Any,
        port: int = 80,
        username: str | None = None,
        password: str | None = None,
        is_https: bool = False,
        turn_off_to_deep: bool = False,
        source_bouquet: str | None = None,
        **_kwargs: Any,
    ) -> None:
        """Record how the integration instantiated the client."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.is_https = is_https
        self.turn_off_to_deep = turn_off_to_deep
        self.source_bouquet = source_bouquet
        self.mac_address: str | None = None
        self.picon_url: str | None = "http://192.168.1.23/picon/daserstehd.png"
        self.is_offline = False
        self.sources: dict[str, Any] = dict(SOURCES)
        self.source_list: list[str] = list(SOURCES)
        self.status = FakeStatus()
        self.calls: list[tuple[str, Any]] = []
        self.closed = False
        FakeOpenWebIfDevice.instances.append(self)

    # -- test helpers ------------------------------------------------------

    @classmethod
    def reset(cls) -> None:
        """Reset the class level configuration and the instance list."""
        cls.about = ABOUT
        cls.about_error = None
        cls.update_error = None
        cls.instances = []

    @classmethod
    def last(cls) -> FakeOpenWebIfDevice:
        """Return the client the integration created last."""
        return cls.instances[-1]

    def recorded(self, name: str) -> list[Any]:
        """Return the arguments of every recorded call `name`."""
        return [value for call, value in self.calls if call == name]

    # -- the openwebifpy surface the integration uses -----------------------

    async def get_about(self) -> dict[str, Any]:
        """Return the about payload or raise the configured error."""
        if self.about_error is not None:
            raise self.about_error
        return self.about

    async def update(self) -> None:
        """Refresh the status or raise the configured error."""
        self.calls.append(("update", None))
        if self.update_error is not None:
            raise self.update_error

    async def set_powerstate(self, newstate: Any) -> bool:
        """Change the power state of the box."""
        self.calls.append(("set_powerstate", newstate))
        return True

    async def turn_on(self) -> bool:
        """Wake the box up."""
        self.calls.append(("turn_on", None))
        return True

    async def turn_off(self) -> bool:
        """Put the box into standby."""
        self.calls.append(("turn_off", None))
        return True

    async def set_volume(self, new_volume: Any) -> bool:
        """Change the volume."""
        self.calls.append(("set_volume", new_volume))
        return True

    async def toggle_mute(self) -> bool:
        """Toggle mute."""
        self.calls.append(("toggle_mute", None))
        return True

    async def zap(self, source: str) -> bool:
        """Change the channel."""
        self.calls.append(("zap", source))
        return True

    async def send_remote_control_action(self, action: Any) -> bool:
        """Send a remote control key."""
        self.calls.append(("send_remote_control_action", action))
        return True

    async def get_all_bouquets(self) -> dict[str, Any]:
        """Return the bouquet list."""
        return {"bouquets": [[SERVICE_REF, "Favourites"]]}

    async def send_message(self, text: str, message_type: Any = None, timeout: int = -1) -> bool:
        """Show a message on the TV screen."""
        self.calls.append(("send_message", (text, message_type, timeout)))
        return True

    async def close(self) -> None:
        """Close the client."""
        self.closed = True
