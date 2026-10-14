# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1b2] - 2026-10-14

### Fixed

* The source list fallback of 1.1.1b1 is **capped at three attempts** per reachable
  period. Without the cap, a box that has no channel to report would have been
  asked twice on every scan interval instead of logging the warning, and a box that
  was still booting would have burned the attempts before it could answer. The
  budget is reset as soon as the box answers again after an outage.

This release supersedes 1.1.1b1.

## [1.1.1b1] - 2026-10-14

### Fixed

* **The tuner signal sensors no longer fail to be added.** A tuner without a lock
  (the box in standby, or on a channel it cannot tune) is answered by OpenWebif
  with empty strings, and a sensor with `state_class: measurement` and a unit may
  not be handed one: `ValueError: Sensor sensor.…_tunersignal_snr has device class
  'None', state class 'measurement' unit '%' … however, it has the non-numeric
  value: ''`. The values are now coerced to a number, and to `unknown` when the
  box has none.
* **The channel browser no longer fails with a `KeyError`.** `/api/getservices`
  answers a bouquet in different key spellings depending on the OpenWebif version
  (`serviceref`/`sRef`, `servicename`/`sName`), and a bouquet can hold entries that
  are not a channel at all. Reading `service["serviceref"]` directly turned that
  into "Unknown error" in the media browser; the entries are now read tolerantly
  and unusable ones are skipped (and reported once, with the keys the box
  answered, so a wrong shape stays diagnosable).
* **The media player gets a source list, and openwebifpy stops warning.**
  openwebifpy builds the sources from `/api/epgnow?bRef=…`, which some boxes
  (OpenATV 8.0) answer without events, so the source list stayed empty and
  `No sources could be loaded from specified bouquet.` was logged on **every**
  poll. When that happens the sources are now filled from `/api/getservices` of
  the configured (or first) bouquet, which every OpenWebif version answers.

## [1.1.1b0] - 2026-10-14

### Fixed

* **Setup and reconfigure no longer fail with "Unknown error occurred"** when the
  address is entered the way a browser takes it. A scheme (`https://10.0.0.30`), a
  port (`192.168.1.23:8080`), a path (`enigma2.local/statusinfo`) or a trailing
  slash used to be handed to `URL.build()` verbatim, which raised a `ValueError`
  (`Host 'https://10.0.0.30' cannot contain ':' (at position 5)`) that the flow
  reported as an unknown error. The host is now split into host, port and scheme:
  a scheme decides *Use HTTPS*, a port in the address wins over the port field, and
  what remains is stored in the entry. An address that has no usable host shows a
  translated error (`invalid_host`) instead of an exception.
* **The setup dialog is translated again.** The field labels, error and abort texts
  used the `[%key:common::config_flow::…%]` references of Home Assistant core, which
  the frontend only resolves for the built-in translations — in a HACS install the
  labels showed up as the raw placeholder (`[%key:common::config_flow::data::host%]`).
  They are literal texts now, in English and German.

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
