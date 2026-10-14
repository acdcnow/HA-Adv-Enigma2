"""Unit tests for the sensors of the box."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.fake_api import EPG
from tests.helpers import entity_id, setup_entry


async def test_tuner_signal_sensors(hass: HomeAssistant, make_entry) -> None:
    """The tuner signal of the running service is exposed."""
    await setup_entry(hass, make_entry)

    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_snr")).state == "84"
    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_agc")).state == "66"
    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_ber")).state == "0"


async def test_image_sensor(hass: HomeAssistant, make_entry) -> None:
    """The image that runs on the box is exposed."""
    await setup_entry(hass, make_entry)

    assert hass.states.get(entity_id(hass, "sensor", "image")).state == "openatv 8.0"


async def test_epg_sensors(hass: HomeAssistant, make_entry) -> None:
    """The running and the following programme are exposed with their details."""
    await setup_entry(hass, make_entry)

    now = hass.states.get(entity_id(hass, "sensor", "now_playing"))
    nxt = hass.states.get(entity_id(hass, "sensor", "next_programme"))

    assert now.state == "Tagesschau"
    assert nxt.state == "Sportschau"
    assert now.attributes["channel"] == "Das Erste HD"
    assert now.attributes["description"] == "Nachrichten"
    assert now.attributes["event_id"] == 4711
    assert now.attributes["begin"] == dt_util.utc_from_timestamp(
        EPG[0]["begin_timestamp"]
    )
    assert now.attributes["end"] == dt_util.utc_from_timestamp(
        EPG[0]["begin_timestamp"] + EPG[0]["duration_sec"]
    )
    assert now.attributes["duration"].total_seconds() == EPG[0]["duration_sec"]


async def test_sensors_without_data(hass: HomeAssistant, make_entry) -> None:
    """A box that answers no signal leaves the sensors without a value."""
    from tests.fake_api import FakeApi

    FakeApi.signal = None
    FakeApi.epg = []
    await setup_entry(hass, make_entry)

    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_snr")).state == (
        "unknown"
    )
    assert hass.states.get(entity_id(hass, "sensor", "now_playing")).state == "unknown"


async def test_empty_tuner_signal_does_not_break_the_sensors(
    hass: HomeAssistant, make_entry
) -> None:
    """A tuner without a lock answers empty strings instead of numbers.

    `state_class: measurement` and a unit tell Home Assistant that the sensor has a
    numeric value, so writing `''` raised a `ValueError` and not one of the signal
    sensors was added (`Sensor sensor.10_0_0_30_tunersignal_snr ... has the
    non-numeric value: ''`).
    """
    from tests.fake_api import FakeApi

    FakeApi.signal = {"snr": "", "snr_db": "", "agc": "", "ber": ""}
    await setup_entry(hass, make_entry)

    for name in ("tuner_signal_snr", "tuner_signal_agc", "tuner_signal_ber"):
        assert hass.states.get(entity_id(hass, "sensor", name)).state == "unknown"


async def test_tuner_signal_accepts_numbers_as_text(
    hass: HomeAssistant, make_entry
) -> None:
    """OpenWebif sends the signal values as strings."""
    from tests.fake_api import FakeApi

    FakeApi.signal = {"snr": "84", "agc": "66.5", "ber": "0", "snr_db": "12.4"}
    await setup_entry(hass, make_entry)

    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_snr")).state == "84"
    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_agc")).state == (
        "66.5"
    )
    assert hass.states.get(entity_id(hass, "sensor", "tuner_signal_ber")).state == "0"
