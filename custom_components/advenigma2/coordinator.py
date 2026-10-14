"""Data update coordinator for the Adv Enigma2 integration."""

import asyncio
import json
import logging
from collections.abc import Awaitable
from typing import Any, Final, override

from aiohttp import encode_basic_auth
from aiohttp.client_exceptions import ClientError
from openwebif.api import OpenWebIfDevice, OpenWebIfStatus
from openwebif.error import InvalidAuthError
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AdvEnigma2Api
from .const import CONF_SOURCE_BOUQUET, DOMAIN

LOGGER = logging.getLogger(__package__)

SETUP_TIMEOUT = 10

# Delay in seconds before the next poll after 1, 2, 3, ... consecutive failures.
# The last entry repeats, so a box that is switched off, in deep standby or
# rebooting is polled ever 10 minutes at most instead of every
# DEFAULT_SCAN_INTERVAL (30 s). Home Assistant logs the failure once when the box
# goes away (and again when it comes back), not once per scan interval.
OFFLINE_RETRY_DELAYS: Final[tuple[int, ...]] = (30, 60, 120, 300, 600)


def offline_retry_delay(failures: int) -> int:
    """Return the delay before the next poll after `failures` failed attempts."""
    index = min(max(failures, 1), len(OFFLINE_RETRY_DELAYS)) - 1
    return OFFLINE_RETRY_DELAYS[index]


type AdvEnigma2ConfigEntry = ConfigEntry[AdvEnigma2UpdateCoordinator]


class AdvEnigma2UpdateCoordinator(DataUpdateCoordinator[OpenWebIfStatus]):
    """The Adv Enigma2 data update coordinator."""

    config_entry: AdvEnigma2ConfigEntry
    device: OpenWebIfDevice
    unique_id: str | None

    def __init__(self, hass: HomeAssistant, config_entry: AdvEnigma2ConfigEntry) -> None:
        """Initialize the Adv Enigma2 data update coordinator."""

        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        base_url = URL.build(
            scheme="http" if not config_entry.data[CONF_SSL] else "https",
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            user=config_entry.data.get(CONF_USERNAME),
            password=config_entry.data.get(CONF_PASSWORD),
        )

        session = async_create_clientsession(
            hass, verify_ssl=config_entry.data[CONF_VERIFY_SSL], base_url=base_url
        )

        # the session belongs to this entry and is closed when it is unloaded
        self.session = session

        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)

        # a base url without credentials, for the raw OpenWebif calls and for the
        # stream url that is handed out to other integrations
        self.base_url = URL.build(
            scheme="http" if not config_entry.data[CONF_SSL] else "https",
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
        )
        self.api = AdvEnigma2Api(
            session,
            self.base_url,
            {"Authorization": encode_basic_auth(username, password)}
            if username or password
            else None,
        )

        # normalised information of the box, filled during setup
        self.about: dict[str, Any] = {}
        self.supports_cec_power_on = False

        # data of the optional OpenWebif features, refreshed by every poll
        self.signal: dict[str, Any] | None = None
        self.timers: list[dict[str, Any]] = []
        self.epg: list[dict[str, Any]] = []
        self.sleep_timer: dict[str, Any] | None = None

        self.device = OpenWebIfDevice(
            session, source_bouquet=config_entry.options.get(CONF_SOURCE_BOUQUET)
        )

        self.device_info = DeviceInfo(
            configuration_url=base_url,
            name=config_entry.data[CONF_HOST],
        )

        # the host is used in log messages, the base url is not: it carries the
        # credentials of the box
        self.host = config_entry.data[CONF_HOST]

        # number of consecutive failed polls, used for the offline back-off
        self.offline_failures = 0

        # set once per outage, so a broken login does not open a reauthentication
        # flow on every poll
        self.reauth_prompted = False

        # set the unique ID for the entities to the config entry unique ID
        # for devices that don't report a MAC address
        self.unique_id = config_entry.unique_id

    @override
    async def _async_setup(self) -> None:
        """Provide needed data to the device info."""

        about = await asyncio.wait_for(self.device.get_about(), timeout=SETUP_TIMEOUT)
        self.about = about.get("info", {})
        try:
            self.supports_cec_power_on = await self.api.async_supports_cec_power_on()
        except Exception:  # noqa: BLE001 - optional feature, must not block setup
            LOGGER.debug(
                "%s does not report the HDMI-CEC power on support",
                self.host,
                exc_info=True,
            )
        self.device.mac_address = about["info"]["ifaces"][0]["mac"]
        self.device_info["model"] = about["info"]["model"]
        self.device_info["manufacturer"] = about["info"]["brand"]
        if self.device.mac_address is not None:
            self.device_info[ATTR_IDENTIFIERS] = {
                (DOMAIN, format_mac(iface["mac"]))
                for iface in about["info"]["ifaces"]
                if "mac" in iface and iface["mac"] is not None
            }
            self.device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, iface["mac"])
                for iface in about["info"]["ifaces"]
                if "mac" in iface and iface["mac"] is not None
            }
            self.unique_id = self.device.mac_address
        elif self.unique_id is not None:
            self.device_info[ATTR_IDENTIFIERS] = {(DOMAIN, self.unique_id)}

    @override
    async def _async_update_data(self) -> OpenWebIfStatus:
        """Fetch the device status.

        An Enigma2 box is expected to be unreachable while it is switched off, in
        deep standby or rebooting. Instead of retrying at the normal scan
        interval forever, the poll backs off via `UpdateFailed(retry_after=...)`:
        Home Assistant then waits 30 s, 1 min, 2 min, 5 min and from then on
        10 minutes between attempts, and it logs the outage once instead of once
        per scan interval.
        """
        try:
            await self.device.update()
        except InvalidAuthError as err:
            self._async_prompt_reauth()
            raise self._async_offline_failure(
                f"{self.host} rejected the credentials, check the username and "
                "password of the integration"
            ) from err
        except (ClientError, OSError, json.JSONDecodeError) as err:
            raise self._async_offline_failure(
                f"{self.host} is not reachable ({type(err).__name__}: {err})"
            ) from err
        except Exception as err:  # noqa: BLE001  # pylint: disable=broad-except
            # An unexpected error must not turn the poll loop into a request (and
            # a traceback) every scan interval either, so back off the same way.
            raise self._async_offline_failure(
                f"Unexpected error while polling {self.host} "
                f"({type(err).__name__}: {err})"
            ) from err

        if self.offline_failures:
            LOGGER.info(
                "%s is reachable again after %s failed attempt(s), resuming the "
                "normal update interval",
                self.host,
                self.offline_failures,
            )
            self.offline_failures = 0
            self.reauth_prompted = False

        # Optional OpenWebif features. Their failures must never fail the poll: a
        # box that answers statusinfo but not, for example, this endpoint simply
        # leaves the matching entities without new data.
        self.signal = await self._async_optional(self.api.async_get_tuner_signal())
        self.timers = await self._async_optional(self.api.async_get_timers(), [])
        self.epg = await self._async_optional(self.api.async_get_now_next(), [])
        self.sleep_timer = await self._async_optional(self.api.async_get_sleep_timer())

        return self.device.status

    async def _async_optional(
        self, call: Awaitable[Any], default: Any = None
    ) -> Any:
        """Await an optional call; a failure only removes that one feature."""
        try:
            return await call
        except Exception:  # noqa: BLE001 - optional data, never fail the poll
            LOGGER.debug(
                "Optional OpenWebif call for %s failed", self.host, exc_info=True
            )
            return default

    def _async_prompt_reauth(self) -> None:
        """Ask the user for new credentials once per outage."""
        if self.reauth_prompted or self.config_entry is None:
            return
        self.reauth_prompted = True
        self.config_entry.async_start_reauth_if_available(self.hass)

    def _async_offline_failure(self, reason: str) -> UpdateFailed:
        """Count a failed poll and build the `UpdateFailed` carrying the back-off."""
        self.offline_failures += 1
        delay = offline_retry_delay(self.offline_failures)
        return UpdateFailed(
            f"{reason}; polling again in {delay} seconds "
            f"(failed attempt {self.offline_failures})",
            retry_after=delay,
        )

    @callback
    def async_reset_offline_backoff(self) -> None:
        """Drop a running offline back-off, e.g. after a power-on command.

        Returning to the normal interval immediately means the entities show up
        again as soon as the box has finished booting, even if the previous
        failures had already pushed the interval to several minutes.
        """
        if self.offline_failures:
            LOGGER.debug(
                "Resetting the offline back-off of %s after a power command",
                self.host,
            )
            self.offline_failures = 0
