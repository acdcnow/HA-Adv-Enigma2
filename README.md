# Adv Enigma2 (OpenWebif) for Home Assistant

A HACS custom integration that turns an **Enigma2 receiver** (OpenATV, OpenPLi,
OpenHDF, VTi, DreamOS, …) into a Home Assistant media player — based on the
Home Assistant core `enigma2` integration, with the domain changed to
`advenigma2` so it can be installed and maintained independently.

Requires **Home Assistant 2026.10.1** or newer (`hacs.json`) and a box running
**OpenWebif**. Developed and verified against **OpenATV 8.0**.

## ✨ Features

* **Media player** — the current programme, channel name, description, begin/end
  time, "is recording", volume and channel icons of the running service, plus
  playback controls: volume up/down/set/mute, play, pause, stop, next/previous
  channel, source (bouquet) selection, standby and deep standby.
* **Media browser** — browse the bouquets of the box, open a bouquet to see its
  channels and its recordings, and play the selected item (`play_media`), for
  example from a dashboard, an automation or a voice assistant. The `stream_url`
  attribute exposes the http stream of the running service for use in
  `camera`/`generic` cards.
* **Buttons** — reboot, restart Enigma2, standby, deep standby, record the running
  service now and clean up the finished timers. *Power on without waking the TV*
  uses the OpenATV 8.0 HDMI-CEC endpoint and is only available if the box
  reports support for it.
* **Screenshot camera** — a `camera` entity that serves the current screen of the
  box via OpenWebif `/grab`, with configurable mode (`all`, `video`, `osd`),
  format and resolution. It does **not** poke a box that is switched off.
* **Sensors** — tuner signal (SNR in % and dB, AGC, BER, tuner type), the image
  version of the box and the running/receiving programme (*now playing* with the
  current programme as attribute, *next programme* with the following one).
* **Timers as a to-do list** — the recording timers of the box appear as a
  `todo` list: complete (disabled), edit the due date/time, rename or delete a
  timer, and tick/un-tick it, all backed by `/api/timerlist` and friends.
* **Sleep timer** — a `number` for the minutes and a `select` for what the box
  should do when the sleep timer expires (standby, deep standby, auto, …).
* **Services** — `send_message` (message on the TV screen), `send_remote_control`
  (any key of the remote), `add_timer`, `remove_timer`, `delete_recording` and
  `rename_recording`, all targetable by device or entity.
* **Config flow** — set up from the UI with host, port, HTTP(S), username,
  password and certificate verification.
* **Reconfigure** — change the connection settings of an existing entry from
  *Settings → Devices & services → Adv Enigma2 → Reconfigure*. The device and all
  entity IDs are kept (unlike deleting and re-adding the integration).
* **Reauthentication** — when the box rejects the stored credentials, new login
  data can be entered without touching the rest of the entry.
* **Options** — deep standby on *Turn off*, source bouquet and channel icon as
  the media image. Changing them reloads the entry immediately.
* **Polite polling** — a box that is switched off, in deep standby or rebooting
  is *not* polled every 30 seconds:

  | Failed polls | Wait before the next try |
  |---|---|
  | 1 | 30 s |
  | 2 | 1 min |
  | 3 | 2 min |
  | 4 | 5 min |
  | 5 and later | 10 min (cap) |

  Home Assistant logs the outage **once** (and once when the box is back), and the
  entities go `unavailable` instead of showing stale data. Turning the box on from
  Home Assistant resets the back-off immediately, so it comes back as soon as it
  has finished booting. A box that is off while Home Assistant starts leads to a
  normal *setup retry*, not to a failed entry.

## 📋 Requirements

* Home Assistant **2026.10.1** or newer (the version the integration is tested against).
* An Enigma2 box with **OpenWebif** enabled (default port 80, usually no login).
* The [`openwebifpy`](https://github.com/autinerd/openwebifpy) client library
  (`openwebifpy==4.3.1`) — installed automatically from `manifest.json`.

## 🚀 Installation

### HACS

1. HACS → *Integrations* → ⋯ → **Custom repositories**.
2. Add `https://github.com/acdcnow/HA-Adv-Enigma2`, category **Integration**.
3. Install **Adv Enigma2 (OpenWebif)** and restart Home Assistant.
4. *Settings → Devices & services → Add integration → Adv Enigma2 (OpenWebif)*.

### Manually

Copy `custom_components/advenigma2` into your `config/custom_components/`
directory and restart Home Assistant.

The integration can be installed next to the core `enigma2` integration; the two
do not share a domain, a device or an entity namespace.

## ⚙️ Configuration

| Setting | Where | Notes |
|---|---|---|
| Host, port, SSL, verify SSL, username, password | Setup, then **Reconfigure** | The host is used as the entry title. |
| Turn off to Deep Standby | **Options** | Shuts the box down instead of standby. |
| Bouquet to use as media source | **Options** | Limits the source list to one bouquet. |
| Show channel icon as media image | **Options** | Channel picon instead of the standard image. |
| Screenshot mode, format, resolution | **Options** | What the camera entity grabs (`/grab`). |

The unique ID is taken from the MAC address reported by the box, so replacing the
entry is only required if the box itself is replaced.

## 🔍 Differences from the core `enigma2` integration

Everything else is the core implementation, adjusted where it matters for a
custom integration and for Home Assistant 2026.10.1:

1. Domain `advenigma2`; classes, device and entity names renamed accordingly.
2. `translations/en.json` and `translations/de.json` are shipped, because a custom
   integration has no build step that generates them from `strings.json`
   (`strings.json` kept, identical to `en.json`).
3. `manifest.json` gained `version`, `issue_tracker` and this fork's
   `documentation` URL — required/expected by HACS.
4. The offline back-off described above; core retries every scan interval forever.
5. Reconfigure and reauthentication flows; core only has *add* and *options*.
6. Options are applied immediately.
7. Turning the box off to deep standby no longer pins the entity to `unavailable`
   until the next restart — the coordinator decides availability and recovers by
   itself.
8. The media player writes its state as soon as it is added; core leaves the entity
   `unknown` for up to one scan interval (30 s) after setup.
9. The aiohttp client session is closed when the entry is unloaded, so a reload or a
   settings change does not leak one session per reload.
10. `UpdateFailed(retry_after=…)` is used instead of the 2026.11 API
    `async_unload_platforms_or_raise`, which does not exist in 2026.10.1.
11. Everything OpenATV 8.0 offers beyond the media player is exposed as well:
    buttons, the screenshot camera, signal/image/EPG sensors, timers as a to-do
    list, the sleep timer and six services (see *Features*). Core `enigma2` only
    ships the media player.

## 🧪 Development

The integration is verified against a **real** Home Assistant installation:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install "homeassistant==2026.10.1" "openwebifpy==4.3.1" "pytest-homeassistant-custom-component==0.13.372" "PyTurboJPEG==1.8.3"

# Windows only: the Home Assistant test harness needs two POSIX modules
Copy-Item tests\shims\*.py .venv\Lib\site-packages\ -Force

.\\.venv\\Scripts\\python.exe tests\\verify_ha_2026_contract.py   # 157 API contract checks
.\\.venv\\Scripts\\python.exe -m pytest tests -q                 # 65 unit tests
```

* `tests/verify_ha_2026_contract.py` — asserts that every Home Assistant and
  openwebifpy symbol the integration uses exists in 2026.10.1, that the manifest,
  HACS metadata and translations are consistent, that every platform and service is
  wired up, and that the code does not use APIs that only exist after 2026.10.1.
* `tests/test_*.py` — unit tests against a real `hass` fixture
  (`pytest-homeassistant-custom-component`), with the Enigma2 box replaced by
  `tests/fakes.py` and the raw OpenWebif client by `tests/fake_api.py`:
  config/reconfigure/reauth/options flows, the offline back-off, the media player
  and its browser, the buttons, the camera, the sensors, the timer to-do list, the
  sleep timer and the services.

[`tests/shims/`](tests/shims) contains two no-op stand-ins for the Unix-only
`fcntl` and `resource` modules; the official Home Assistant test harness imports
them, so the suite cannot run on Windows without them. They are local development
helpers only and are never shipped to Home Assistant.

## 🗺️ OpenATV 8.0 coverage

The OpenATV 8.0 endpoints are implemented (see *Features*); this table says which
OpenWebif call backs which entity:

| OpenWebif call | Home Assistant |
|---|---|
| `getcurrent`, `epgservicenext` | `sensor.now_playing`, `sensor.next_programme` |
| `tunersignal` | `sensor.tuner_signal_*` |
| `getabout` | `sensor.image_version` |
| `/grab` | `camera.screenshot` |
| `timerlist`, `timeradd`, `timerchange`, `timertogglestatus`, `timerdelete`, `timercleanup` | `todo.timers` |
| `recordnow` | `button.record_now` |
| `movielist`, `moviedelete`, `movierename` | media browser (`browse_media`) |
| `sleeptimer` | `number.sleep_timer`, `select.sleep_timer_action` |
| `remotecontrol` | service `advenigma2.send_remote_control` |
| `message` | service `advenigma2.send_message` |
| power states | `media_player` (standby/deep standby) and the power buttons |
| `supports_powerup_without_waking_tv`, `set_powerup_without_waking_tv` | `button.power_on_without_waking_the_tv` |

**Streaming the TV picture into Home Assistant** (`streamcurrentm3u`, `streamm3u`)
is the one item still open. The media player exposes the stream of the running
service as the `stream_url` attribute, so a `generic`/`camera` card or an
automation can use it — but the integration does not play the stream itself, and
the box has to serve its stream port (8001) to the caller.

## 📄 License and credits

GPL-3.0-or-later — see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

`custom_components/advenigma2` is derived from the Home Assistant core
[`enigma2`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/enigma2)
integration (Apache-2.0), which in turn is maintained by [@autinerd](https://github.com/autinerd)
and depends on [openwebifpy](https://github.com/autinerd/openwebifpy) (MIT) by
Finbarr Brady.
