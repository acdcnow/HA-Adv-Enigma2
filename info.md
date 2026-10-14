# Adv Enigma2 (OpenWebif) for Home Assistant

Control an Enigma2 receiver (OpenATV, OpenPLi, OpenHDF, VTi, DreamOS, …) from Home
Assistant — as a media player with full playback, volume and channel control.

This is the Home Assistant core `enigma2` integration under its own `advenigma2`
domain, so it can be installed and updated through HACS.

## Highlights

* **Media player** with the current programme, channel, description, begin/end time,
  recording state, volume, mute and channel icon — plus a media browser for the
  bouquets, their channels and the recordings of the box.
* **Everything else OpenWebif offers:** buttons (reboot, restart Enigma2, standby,
  deep standby, record now, delete expired timers, HDMI-CEC power on), a screenshot
  camera, signal/image/EPG sensors, the recording timers as a to-do list, the sleep
  timer, and services for messages, remote-control keys, timers and recordings.
* **Reconfigure** the connection (host, port, HTTP(S), credentials) without losing
  the device and entity IDs, plus a **reauthentication** flow for new credentials.
* **Polite polling:** a box that is switched off or in deep standby is polled with a
  growing delay (30 s → 1 min → 2 min → 5 min → 10 min) instead of every 30 seconds,
  the outage is logged once, and polling returns to normal as soon as the box answers.
* Requires Home Assistant **2026.10.1** or newer. Verified against OpenATV 8.0.

See the [README](https://github.com/acdcnow/HA-Adv-Enigma2) for installation,
configuration and the list of OpenWebif calls behind every entity.
