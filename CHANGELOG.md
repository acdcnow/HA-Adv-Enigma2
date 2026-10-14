# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-14

Everything OpenWebif on **OpenATV 8.0** offers beyond the media player is now part
of the integration. The new platforms are only created when the box answers, and
they never poke a box that is switched off.

### Added

* **Media browser** (`browse_media` / `play_media`): bouquets → channels and
  recordings; a selected channel is zapped, a recording is played. `stream_url`
  exposes the http stream of the running service.
* **Buttons**: reboot, restart Enigma2, standby, deep standby, record now, delete
  expired timers and *power on without waking the TV* (HDMI-CEC; only available if
  the box reports support for it).
* **Screenshot camera**: the current screen of the box via `/grab`, with mode,
  format and resolution configurable in the options.
* **Sensors**: tuner signal (SNR, AGC, BER, tuner type), image version, now playing
  (with the current programme as attribute) and next programme.
* **Timers as a to-do list**: list, complete/disable, move, rename and delete the
  recording timers of the box.
* **Sleep timer**: a `number` for the minutes and a `select` for what the box does
  when it expires.
* **Services**: `send_message`, `send_remote_control`, `add_timer`, `remove_timer`,
  `delete_recording`, `rename_recording` — targetable by device or entity.
* Options for the screenshot (mode, format, resolution).

### Changed

* The raw OpenWebif endpoints that `openwebifpy` does not implement are called
  through a new `api.AdvEnigma2Api` on the same aiohttp session.
* Basic authentication uses a plain `Authorization` header built with
  `aiohttp.encode_basic_auth()` instead of the deprecated `aiohttp.BasicAuth`
  object.
* Entities share one base class (`entity.AdvEnigma2Entity`) that attaches them to
  the device of the box and writes their state as soon as they are added.

## [1.0.0] - 2026-10-14

First release: the Home Assistant core `enigma2` integration under the new
`advenigma2` domain, verified against Home Assistant 2026.10.1 and OpenATV 8.0.

### Added

* Config flow with host, port, HTTP(S), username, password and certificate
  verification.
* **Reconfigure** flow to change the connection settings of an existing entry —
  the device and all entity IDs are kept.
* **Reauthentication** flow for new credentials.
* Options flow (deep standby, source bouquet, channel icon) that reloads the entry
  automatically, so changes take effect immediately.
* `translations/en.json` and `translations/de.json` (a custom integration has no
  build step that generates them from `strings.json`).
* HACS metadata (`hacs.json`) and `manifest.json` version/issue tracker.
* Unit tests against a real Home Assistant 2026.10.1 (`pytest-homeassistant-custom-component`):
  config, reconfigure, reauth and options flows, the offline back-off and the media
  player entity (35 tests).
* `tests/verify_ha_2026_contract.py`: 119 checks that the Home Assistant 2026.10.1
  API, the openwebifpy API, the manifest, the HACS metadata and the translations all
  match what the code expects.
* CI workflow that runs the contract harness and the unit tests on every push.

### Changed

* Domain `enigma2` → `advenigma2`, with the classes, device and entity names
  renamed; the integration can be installed next to the core `enigma2` integration.
* A box that is switched off or in deep standby is no longer polled every scan
  interval: the poll backs off to 30 s, 1 min, 2 min, 5 min and then every 10
  minutes, logs the outage once, and resumes the normal interval as soon as the box
  answers again. Turning the box on from Home Assistant resets the back-off
  immediately.
* Wrong credentials back off the same way and open the reauthentication flow once
  per outage instead of on every poll.
* The media player writes its state as soon as it is added; it no longer stays
  `unknown` for up to one scan interval after setup.
* Turning the box off to deep standby no longer pins the media player to
  `unavailable` until Home Assistant is restarted — availability follows the
  coordinator, which recovers by itself.
* The aiohttp session of the entry is closed on unload, so reloads and settings
  changes do not leak a session each time.

### Fixed

* Options changes are applied without a manual reload (the core integration ignores
  them until the next restart).
* The poll loop no longer logs a traceback per scan interval for unexpected errors;
  it backs off instead.
