"""Home Assistant 2026.10.1 contract check for the Adv Enigma2 integration.

This harness runs against a *real* Home Assistant installation and verifies that
every Home Assistant and openwebifpy symbol the integration touches still exists
with the expected shape in the targeted release.

Run it with the interpreter that has Home Assistant installed, e.g.::

    .venv\\Scripts\\python.exe tests\\verify_ha_2026_contract.py

It exits non-zero when anything it checks is missing, so it is usable in CI.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "advenigma2"
DOMAIN = "advenigma2"

# Home Assistant 2026.10.1 requires Python 3.14.2+
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []
PASSED = 0


def check(label: str, condition: bool, detail: Any = "") -> None:
    """Record the outcome of a single contract check."""
    global PASSED
    if condition:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILURES.append(f"{label}{f' ({detail})' if detail else ''}")
        print(f"  FAIL {label}{f' ({detail})' if detail else ''}")


def has(obj: Any, *names: str) -> bool:
    """Return True when every name exists on obj."""
    return all(hasattr(obj, name) for name in names)


def section(title: str) -> None:
    print(f"\n{title}")


def main() -> int:
    """Run every contract check."""
    import homeassistant.const as ha_const
    import openwebif
    from aiohttp.client_exceptions import ClientError, ServerDisconnectedError

    section("Versions")
    ha_version = ha_const.__version__
    print(f"  Home Assistant: {ha_version}")
    print(f"  openwebifpy:    {openwebif.__version__}")
    check("Home Assistant major/minor is 2026.10", ha_version.startswith("2026.10"), ha_version)
    check("Python is 3.14.2+", sys.version_info[:3] >= (3, 14, 2), sys.version.split()[0])

    import voluptuous as vol

    print(f"  voluptuous:     {vol.__name__} ({vol.__file__})")
    check("schema library importable as `voluptuous`", has(vol, "Schema", "Required", "Optional", "All", "Coerce"))

    section("Home Assistant API used by the integration")
    from homeassistant.components import media_player as mp
    from homeassistant.config_entries import (
        SOURCE_REAUTH,
        SOURCE_RECONFIGURE,
        SOURCE_USER,
        ConfigEntries,
        ConfigEntry,
        ConfigFlow,
        ConfigFlowResult,
        OptionsFlow,
        OptionsFlowWithReload,
    )
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant, callback
    from homeassistant.helpers import entity_platform, selector
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_component
    from homeassistant.helpers import schema_config_entry_flow as scef
    from homeassistant.helpers import update_coordinator as uc
    from homeassistant.helpers.aiohttp_client import async_create_clientsession

    check("config_entries.ConfigFlow", inspect.isclass(ConfigFlow))
    check("config_entries.ConfigFlowResult", ConfigFlowResult is not None)
    check("config_entries.SOURCE_USER", SOURCE_USER == "user")
    check("config_entries.OptionsFlow", inspect.isclass(OptionsFlow))
    check("config_entries.ConfigEntry", inspect.isclass(ConfigEntry))
    check("const.Platform.MEDIA_PLAYER", Platform.MEDIA_PLAYER == "media_player")
    check("const.Platform.CAMERA", hasattr(Platform, "CAMERA"))
    check("const.Platform.BUTTON", hasattr(Platform, "BUTTON"))
    check("const.Platform.TODO", hasattr(Platform, "TODO"))
    check("const.Platform.SENSOR", hasattr(Platform, "SENSOR"))
    check("config_entries.SOURCE_RECONFIGURE", SOURCE_RECONFIGURE == "reconfigure")
    check("config_entries.SOURCE_REAUTH", SOURCE_REAUTH == "reauth")
    check(
        "ConfigEntries.async_entry_for_domain_unique_id",
        callable(getattr(ConfigEntries, "async_entry_for_domain_unique_id", None)),
    )
    check(
        "device_registry.async_get_device_by_identifier",
        callable(getattr(dr.DeviceRegistry, "async_get_device_by_identifier", None)),
    )
    from homeassistant.helpers.update_coordinator import UpdateFailed as _UpdateFailed

    check(
        "UpdateFailed accepts retry_after",
        "retry_after" in inspect.signature(_UpdateFailed.__init__).parameters,
        inspect.signature(_UpdateFailed.__init__),
    )
    check("core.HomeAssistant / callback", has(HomeAssistant, "config_entries") and callable(callback))
    check(
        "async_create_clientsession",
        callable(async_create_clientsession),
    )

    check(
        "helpers.entity_component.DEFAULT_SCAN_INTERVAL",
        hasattr(entity_component, "DEFAULT_SCAN_INTERVAL"),
        getattr(entity_component, "DEFAULT_SCAN_INTERVAL", None),
    )
    check(
        "helpers.update_coordinator.DataUpdateCoordinator",
        inspect.isclass(uc.DataUpdateCoordinator) and hasattr(uc.DataUpdateCoordinator, "async_config_entry_first_refresh"),
    )
    check("helpers.update_coordinator.CoordinatorEntity", inspect.isclass(uc.CoordinatorEntity))
    check(
        "helpers.entity_platform.AddConfigEntryEntitiesCallback",
        hasattr(entity_platform, "AddConfigEntryEntitiesCallback"),
    )
    check(
        "helpers.device_registry symbols",
        has(dr, "CONNECTION_NETWORK_MAC", "DeviceInfo", "format_mac"),
    )
    check(
        "helpers.schema_config_entry_flow symbols",
        has(scef, "SchemaCommonFlowHandler", "SchemaFlowFormStep", "SchemaOptionsFlowHandler"),
    )

    section("Config entry contract (2026.10.1 vs. 2026.11 dev)")
    check(
        "ConfigEntries.async_unload_platforms exists",
        callable(getattr(ConfigEntries, "async_unload_platforms", None)),
    )
    check(
        "async_unload_platforms_or_raise is NOT required by 2026.10.1",
        not hasattr(ConfigEntries, "async_unload_platforms_or_raise"),
        "present (dev/2026.11 API)" if hasattr(ConfigEntries, "async_unload_platforms_or_raise") else "",
    )

    section("media_player entity API")
    check(
        "media_player classes",
        has(mp, "MediaPlayerEntity", "MediaPlayerEntityFeature", "MediaPlayerState", "MediaType"),
    )
    for feature in (
        "VOLUME_SET",
        "VOLUME_MUTE",
        "TURN_OFF",
        "NEXT_TRACK",
        "STOP",
        "PREVIOUS_TRACK",
        "VOLUME_STEP",
        "TURN_ON",
        "PAUSE",
        "SELECT_SOURCE",
        "PLAY",
    ):
        check(f"MediaPlayerEntityFeature.{feature}", hasattr(mp.MediaPlayerEntityFeature, feature))
    check("MediaPlayerState.OFF / ON", has(mp.MediaPlayerState, "OFF", "ON"))
    check("MediaType.TVSHOW", hasattr(mp.MediaType, "TVSHOW"))
    check("MediaPlayerEntity._attr_state", hasattr(mp.MediaPlayerEntity, "_attr_state"))

    section("Selector API")
    check(
        "selector classes",
        has(
            selector,
            "TextSelector",
            "TextSelectorConfig",
            "TextSelectorType",
            "NumberSelector",
            "NumberSelectorConfig",
            "NumberSelectorMode",
            "BooleanSelector",
            "SelectSelector",
            "SelectSelectorConfig",
            "SelectSelectorMode",
        ),
    )
    check("TextSelectorType.PASSWORD", hasattr(selector.TextSelectorType, "PASSWORD"))
    check("NumberSelectorMode.BOX", hasattr(selector.NumberSelectorMode, "BOX"))
    check("SelectSelectorMode.DROPDOWN", hasattr(selector.SelectSelectorMode, "DROPDOWN"))

    section("aiohttp exceptions used")
    check("ClientError / ServerDisconnectedError", ClientError is not None and ServerDisconnectedError is not None)

    section("openwebifpy API surface")
    from openwebif import enums
    from openwebif.api import OpenWebIfDevice, OpenWebIfStatus
    from openwebif.error import InvalidAuthError

    check("openwebif.error.InvalidAuthError", inspect.isclass(InvalidAuthError))
    check("OpenWebIfDevice.__init__ accepts a session", "host" in inspect.signature(OpenWebIfDevice.__init__).parameters)
    check("OpenWebIfDevice.source_bouquet parameter", "source_bouquet" in inspect.signature(OpenWebIfDevice.__init__).parameters)
    check(
        "OpenWebIfDevice methods",
        has(
            OpenWebIfDevice,
            "update",
            "get_about",
            "get_all_bouquets",
            "get_all_services",
            "get_bouquets",
            "get_status_info",
            "set_powerstate",
            "turn_on",
            "turn_off",
            "deep_standby",
            "set_volume",
            "get_volume",
            "toggle_mute",
            "zap",
            "send_remote_control_action",
            "send_message",
            "get_screen_grab_url",
            "close",
        ),
    )
    check(
        "OpenWebIfDevice attributes",
        {
            "status",
            "sources",
            "source_list",
            "picon_url",
            "mac_address",
            "turn_off_to_deep",
        }
        <= set(getattr(OpenWebIfDevice, "__annotations__", {})),
        sorted(getattr(OpenWebIfDevice, "__annotations__", {})),
    )
    status_fields = {item.name for item in dataclasses.fields(OpenWebIfStatus)}
    check(
        "OpenWebIfStatus fields",
        {"currservice", "volume", "muted", "in_standby", "is_recording", "status_info"}
        <= status_fields,
        sorted(status_fields),
    )
    check("PowerState members", has(enums.PowerState, "DEEP_STANDBY", "STANDBY", "REBOOT", "RESTART_ENIGMA", "WAKEUP"))
    check("RemoteControlCodes members", has(enums.RemoteControlCodes, "STOP", "PLAY", "PAUSE", "CHANNEL_UP", "CHANNEL_DOWN"))
    check("SetVolumeOption members", has(enums.SetVolumeOption, "UP", "DOWN", "MUTE"))
    check("ScreenGrabMode members", has(enums.ScreenGrabMode, "ALL", "OSD", "VIDEO", "PIP", "LCD"))
    check("ScreenGrabFormat members", has(enums.ScreenGrabFormat, "JPG", "PNG", "BMP"))

    section("Component imports and naming")
    const = importlib.import_module("custom_components.advenigma2.const")
    coordinator = importlib.import_module("custom_components.advenigma2.coordinator")
    config_flow = importlib.import_module("custom_components.advenigma2.config_flow")
    media_player = importlib.import_module("custom_components.advenigma2.media_player")
    init = importlib.import_module("custom_components.advenigma2")

    check("const.DOMAIN == advenigma2", const.DOMAIN == DOMAIN, const.DOMAIN)
    check("coordinator types", has(coordinator, "AdvEnigma2UpdateCoordinator", "AdvEnigma2ConfigEntry"))
    check("config flow handler", has(config_flow, "AdvEnigma2ConfigFlowHandler"))
    config_entries_module = importlib.import_module("homeassistant.config_entries")
    handlers = getattr(config_entries_module, "HANDLERS", None)
    registered = handlers.get(DOMAIN) if handlers is not None else None
    check(
        "config flow is registered for the advenigma2 domain",
        registered is config_flow.AdvEnigma2ConfigFlowHandler,
        registered,
    )
    check("media player entity class", has(media_player, "AdvEnigma2MediaPlayer"))
    check("PLATFORMS includes media_player", Platform.MEDIA_PLAYER in init.PLATFORMS, init.PLATFORMS)
    check(
        "async_setup_entry returns bool (2026.10.1 contract)",
        inspect.signature(init.async_setup_entry).return_annotation in (bool, "bool", "-> bool"),
        inspect.signature(init.async_setup_entry).return_annotation,
    )
    check(
        "async_unload_entry returns bool (2026.10.1 contract)",
        inspect.signature(init.async_unload_entry).return_annotation in (bool, "bool", "-> bool"),
        inspect.signature(init.async_unload_entry).return_annotation,
    )

    check("no leftover core enigma2 domain", 'DOMAIN = "enigma2"' not in (COMPONENT / "const.py").read_text(encoding="utf-8"))

    section("Reconfiguration, reauthentication and the offline back-off")
    check(
        "config flow implements reconfigure",
        has(config_flow.AdvEnigma2ConfigFlowHandler, "async_step_reconfigure"),
    )
    check(
        "config flow implements reauth",
        has(
            config_flow.AdvEnigma2ConfigFlowHandler,
            "async_step_reauth",
            "async_step_reauth_confirm",
        ),
    )
    check("REAUTH_SCHEMA limits the input to the credentials", set(map(str, config_flow.REAUTH_SCHEMA.schema)) == {"username", "password"})
    check(
        "validate_user_input can exclude the entry being reconfigured",
        "current_entry" in inspect.signature(config_flow.AdvEnigma2ConfigFlowHandler.validate_user_input).parameters,
    )
    options_flow = config_flow.AdvEnigma2ConfigFlowHandler.async_get_options_flow(
        SimpleNamespace(options={}, entry_id="test")
    )
    check(
        "options flow reloads the entry automatically",
        isinstance(options_flow, OptionsFlowWithReload) and options_flow.automatic_reload is True,
        type(options_flow).__name__,
    )
    check("offline_retry_delay helper", callable(coordinator.offline_retry_delay))
    check(
        "offline retry delays grow and end in a cap",
        tuple(coordinator.OFFLINE_RETRY_DELAYS) == (30, 60, 120, 300, 600)
        and coordinator.offline_retry_delay(1) == 30
        and coordinator.offline_retry_delay(5) == 600
        and coordinator.offline_retry_delay(99) == 600,
        coordinator.OFFLINE_RETRY_DELAYS,
    )
    check(
        "coordinator can reset the back-off",
        has(coordinator.AdvEnigma2UpdateCoordinator, "async_reset_offline_backoff", "_async_offline_failure"),
    )
    coordinator_source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
    check("the poll raises UpdateFailed with retry_after", "retry_after=delay" in coordinator_source)
    check("the poll backs off for unexpected errors too", "Unexpected error while polling" in coordinator_source)
    check("reauth is only prompted once per outage", "reauth_prompted" in coordinator_source)
    media_player_source = (COMPONENT / "media_player.py").read_text(encoding="utf-8")
    check(
        "the player is not pinned to unavailable after deep standby",
        "_attr_available = False" not in media_player_source,
    )
    check("the player writes its state when it is added", "async_added_to_hass" in media_player_source)
    check("turning the box on clears the back-off", "async_reset_offline_backoff" in media_player_source)
    check(
        "unloading the entry closes the OpenWebIf client",
        "device.close()" in (COMPONENT / "__init__.py").read_text(encoding="utf-8"),
    )
    for path in sorted(COMPONENT.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "Enigma2Device":
                check(f"{path.name} uses the renamed entity class", False, "Enigma2Device")
        check(
            f"{path.name} has no `_attr_temperature_unit` style legacy attr",
            "_attr_temperature_unit" not in source,
        )

    section("Manifest, HACS metadata and translations")
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    check("manifest domain", manifest["domain"] == DOMAIN, manifest["domain"])
    check("manifest config_flow", manifest.get("config_flow") is True)
    check("manifest version", isinstance(manifest.get("version"), str) and manifest["version"].count(".") == 2, manifest.get("version"))
    check("manifest requirement openwebifpy", manifest.get("requirements") == ["openwebifpy==4.3.1"], manifest.get("requirements"))
    check("manifest iot_class", manifest.get("iot_class") == "local_polling")
    check("manifest integration_type", manifest.get("integration_type") == "device")
    check("manifest codeowners", manifest.get("codeowners") == ["@acdcnow"])
    repo_name = "ha-adv-enigma2"
    check(
        "manifest documentation points at the fork",
        repo_name in manifest.get("documentation", "").lower(),
    )
    check(
        "manifest issue_tracker points at the fork",
        repo_name in manifest.get("issue_tracker", "").lower(),
    )

    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    check("hacs.json name", isinstance(hacs.get("name"), str), hacs)
    check("hacs.json render_readme", hacs.get("render_readme") is True)
    check("hacs.json homeassistant == 2026.10.1", hacs.get("homeassistant") == "2026.10.1", hacs.get("homeassistant"))

    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    translations = COMPONENT / "translations"
    for locale in ("en", "de"):
        path = translations / f"{locale}.json"
        check(f"translations/{locale}.json exists", path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        check(f"translations/{locale}.json matches strings.json structure", _same_shape(strings, data), locale)
    check(
        "translations/en.json is byte-identical to strings.json (core generates it from strings.json)",
        (translations / "en.json").read_text(encoding="utf-8") == (COMPONENT / "strings.json").read_text(encoding="utf-8"),
    )

    section("Config flow error keys are translated")
    for key in ("cannot_connect", "invalid_auth", "unknown"):
        check(f"error.{key} translated", key in strings["config"]["error"], strings["config"]["error"].keys())
        check(f"abort.{key} translated", key in strings["config"]["abort"], strings["config"]["abort"].keys())
    check("abort.already_configured translated", "already_configured" in strings["config"]["abort"])
    check(
        "user step documents all fields",
        set(strings["config"]["step"]["user"]["data"]) == {"host", "password", "port", "ssl", "username", "verify_ssl"},
        set(strings["config"]["step"]["user"]["data"]),
    )
    check(
        "options step documents all options",
        set(strings["options"]["step"]["init"]["data"]) == {"deep_standby", "source_bouquet", "use_channel_icon"},
        set(strings["options"]["step"]["init"]["data"]),
    )
    check(
        "options data keys match DATA_KEYS/OPTIONS_KEYS",
        set(config_flow.AdvEnigma2ConfigFlowHandler.OPTIONS_KEYS)
        == set(strings["options"]["step"]["init"]["data"]),
    )
    check(
        "reconfigure step documents all connection fields",
        set(strings["config"]["step"]["reconfigure"]["data"])
        == set(strings["config"]["step"]["user"]["data"]),
        set(strings["config"]["step"]["reconfigure"].get("data", {})),
    )
    check(
        "reauth_confirm step documents the credentials",
        set(strings["config"]["step"]["reauth_confirm"]["data"]) == {"username", "password"},
        set(strings["config"]["step"].get("reauth_confirm", {}).get("data", {})),
    )
    check(
        "abort.unique_id_mismatch is translated",
        "unique_id_mismatch" in strings["config"]["abort"],
    )
    check(
        "CONFIG_SCHEMA covers DATA_KEYS",
        {str(key) for key in config_flow.CONFIG_SCHEMA.schema} == set(config_flow.AdvEnigma2ConfigFlowHandler.DATA_KEYS),
        {str(key) for key in config_flow.CONFIG_SCHEMA.schema},
    )

    section("Summary")
    print(f"  {PASSED} checks passed, {len(FAILURES)} failed")
    if FAILURES:
        print("\nFailures:")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    return 0


def _same_shape(left: Any, right: Any) -> bool:
    """Compare nested dicts by structure only, ignoring string values."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same_shape(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same_shape(a, b) for a, b in zip(left, right, strict=True))
    return type(left) is type(right)


if __name__ == "__main__":
    sys.exit(main())
