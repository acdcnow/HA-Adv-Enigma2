"""Config flow for Adv Enigma2."""

import logging
import re
from collections.abc import Mapping
from typing import Any, cast, override

from aiohttp.client_exceptions import ClientError
from openwebif.api import OpenWebIfDevice
from openwebif.error import InvalidAuthError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
    SchemaOptionsFlowHandlerWithReload,
)

from .const import (
    CONF_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

HTTP_SCHEMES = ("http", "https")

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SSL, default=DEFAULT_SSL): selector.BooleanSelector(),
        vol.Required(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
    }
)

_LOGGER = logging.getLogger(__name__)


def clean_connection_input(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Return the connection data with an address that yarl can build a URL from.

    People type the address of the box the way a browser takes it — with a scheme,
    a port or a trailing slash — while the rest of the integration expects the bare
    host name. Everything else is split off here: a scheme decides `ssl`, a port in
    the address wins over the port field. Passing `https://box` to `URL.build()`
    used to raise a `ValueError` that surfaced as "Unknown error occurred".
    """
    data = dict(user_input)
    address = str(data.get(CONF_HOST) or "").strip()

    scheme, separator, rest = address.partition("://")
    if separator:
        address = rest.strip()
        if scheme.strip().lower() in HTTP_SCHEMES:
            data[CONF_SSL] = scheme.strip().lower() == "https"

    # only the authority of a URL matters, drop a path, a query or a fragment
    address = re.split(r"[/?#]", address, maxsplit=1)[0].strip()

    host, port = _split_port(address)
    if port is not None:
        data[CONF_PORT] = port
    data[CONF_HOST] = host
    return data


def _split_port(address: str) -> tuple[str, int | None]:
    """Split `host:port` (and `[ipv6]:port`) from an address.

    A port is only taken from the address when it really is one, so a bare IPv6
    address keeps its colons.
    """
    if address.startswith("[") and "]" in address:
        host, _, remainder = address[1:].partition("]")
        return host, _port_number(remainder.removeprefix(":"))

    if address.count(":") == 1:
        host, _, port = address.partition(":")
        if (number := _port_number(port)) is not None:
            return host, number

    return address, None


def _port_number(port: str) -> int | None:
    """Return the port of an address, if it is a usable one."""
    port = port.strip()
    if port.isdigit() and 1 <= int(port) <= 65535:
        return int(port)
    return None

# Reauthentication only asks for the credentials, everything else is kept from
# the existing entry; use reconfigure to change the host or the port.
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get the options schema."""
    entry = cast(SchemaOptionsFlowHandler, handler.parent_handler).config_entry
    bouquets = [
        b[1] for b in (await entry.runtime_data.device.get_all_bouquets())["bouquets"]
    ]

    return vol.Schema(
        {
            vol.Optional(CONF_DEEP_STANDBY): selector.BooleanSelector(),
            vol.Optional(CONF_SOURCE_BOUQUET): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=bouquets,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_USE_CHANNEL_ICON): selector.BooleanSelector(),
        }
    )


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(get_options_schema),
}


class AdvEnigma2ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Adv Enigma2."""

    DATA_KEYS = (
        CONF_HOST,
        CONF_PORT,
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_SSL,
        CONF_VERIFY_SSL,
    )
    OPTIONS_KEYS = (CONF_DEEP_STANDBY, CONF_SOURCE_BOUQUET, CONF_USE_CHANNEL_ICON)

    async def validate_user_input(
        self,
        user_input: dict[str, Any],
        current_entry: ConfigEntry | None = None,
    ) -> dict[str, str] | None:
        """Validate user input and remember the unique ID of the box.

        `current_entry` is set while an existing entry is reconfigured or
        reauthenticated. The entry's own host and unique ID must then not make the
        flow abort with `already_configured`, only a *different* entry may.
        """

        errors = None

        existing_entry_id = current_entry.entry_id if current_entry else None
        host = str(user_input.get(CONF_HOST) or "")

        if not host:
            return {"base": "invalid_host"}

        if existing_entry_id is None or host != current_entry.data.get(CONF_HOST):
            self._async_abort_entries_match({CONF_HOST: host})

        try:
            base_url = URL.build(
                scheme="http" if not user_input[CONF_SSL] else "https",
                host=host,
                port=user_input.get(CONF_PORT),
                user=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )
        except (TypeError, ValueError):
            # yarl rejects an address it cannot represent, e.g. a second colon
            _LOGGER.debug("Cannot build an URL for the host %r", host)
            return {"base": "invalid_host"}

        session = async_create_clientsession(
            self.hass, verify_ssl=user_input[CONF_VERIFY_SSL], base_url=base_url
        )

        try:
            about = await OpenWebIfDevice(session).get_about()
        except InvalidAuthError:
            errors = {"base": "invalid_auth"}
        except ClientError:
            errors = {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors = {"base": "unknown"}
        else:
            unique_id = about["info"]["ifaces"][0]["mac"] or self.unique_id
            await self.async_set_unique_id(unique_id)
            if existing_entry_id is None:
                self._abort_if_unique_id_configured()
            elif (
                existing := self.hass.config_entries.async_entry_for_domain_unique_id(
                    self.handler, unique_id
                )
            ) is not None and existing.entry_id != existing_entry_id:
                # another entry is already in charge of this box
                raise AbortFlow("already_configured")

        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is None:
            return self.async_show_form(step_id=SOURCE_USER, data_schema=CONFIG_SCHEMA)

        user_input = clean_connection_input(user_input)
        if errors := await self.validate_user_input(user_input):
            return self.async_show_form(
                step_id=SOURCE_USER,
                data_schema=self.add_suggested_values_to_schema(
                    CONFIG_SCHEMA, user_input
                ),
                errors=errors,
            )
        return self.async_create_entry(data=user_input, title=user_input[CONF_HOST])

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step.

        Adjust the connection settings of the entry (host, port, SSL, username,
        password, certificate verification) without removing and adding it again,
        which would lose the entity IDs and the device registry entries.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = clean_connection_input(user_input)
            errors = await self.validate_user_input(user_input, entry) or {}
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    title=user_input[CONF_HOST],
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id=SOURCE_RECONFIGURE,
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, user_input or entry.data
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    @override
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle a reauthentication request.

        Reached from the integration's "Authentication failed" entry point or from
        the reconfigure menu of the device, so that new login data of the box can
        be entered without deleting the entry.
        """
        return await self.async_step_reauth_confirm()

    @override
    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step of the reauthentication flow."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_data = clean_connection_input(
                {
                    **entry.data,
                    CONF_USERNAME: user_input.get(CONF_USERNAME),
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                }
            )
            errors = await self.validate_user_input(new_data, entry) or {}
            if not errors:
                # the credentials must belong to the box of this entry
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data_updates=new_data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, user_input or entry.data
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandlerWithReload:
        """Get the options flow for this handler.

        `SchemaOptionsFlowHandlerWithReload` reloads the config entry when the
        options change, so a new bouquet, the deep standby switch or the channel
        icon take effect immediately instead of after the next restart.
        """
        return SchemaOptionsFlowHandlerWithReload(config_entry, OPTIONS_FLOW)
