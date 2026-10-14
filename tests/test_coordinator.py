"""Unit tests for the update coordinator of Adv Enigma2.

The offline behaviour is the important part: a box that is switched off or in
deep standby must be polled with a growing delay instead of every scan interval,
and it must not fill the Home Assistant log either.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from aiohttp.client_exceptions import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from openwebif.error import InvalidAuthError

from custom_components.advenigma2.coordinator import (
    OFFLINE_RETRY_DELAYS,
    AdvEnigma2UpdateCoordinator,
    offline_retry_delay,
)


@pytest.mark.parametrize(
    ("failures", "expected"),
    [(0, 30), (1, 30), (2, 60), (3, 120), (4, 300), (5, 600), (42, 600)],
)
def test_offline_retry_delay_grows_then_caps(failures: int, expected: int) -> None:
    """The delay grows with the number of failed attempts and then caps."""
    assert offline_retry_delay(failures) == expected
    assert offline_retry_delay(failures) == OFFLINE_RETRY_DELAYS[
        min(max(failures, 1), len(OFFLINE_RETRY_DELAYS)) - 1
    ]


async def test_successful_poll_returns_the_status(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """A healthy box is polled without any back-off."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())

    status = await coordinator._async_update_data()

    assert status.in_standby is False
    assert coordinator.offline_failures == 0


async def test_poll_backs_off_while_the_box_is_off(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """A powered off box is polled with a growing delay, not every 30 seconds."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())
    fake_device.update_error = ClientError("Cannot connect to host")

    delays: list[float | None] = []
    for _ in range(len(OFFLINE_RETRY_DELAYS) + 3):
        with pytest.raises(UpdateFailed) as err:
            await coordinator._async_update_data()
        delays.append(err.value.retry_after)

    assert delays == [30, 60, 120, 300, 600, 600, 600, 600]
    assert coordinator.offline_failures == len(delays)
    # after the first failure nothing is polled more often than once a minute,
    # and the cap is ten minutes
    assert min(delays[1:]) >= 60
    assert delays[-1] == OFFLINE_RETRY_DELAYS[-1]


async def test_poll_recovers_and_resets_the_backoff(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Once the box answers again, polling returns to the normal interval."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())
    fake_device.update_error = ClientError("Cannot connect to host")
    for _ in range(3):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    assert coordinator.offline_failures == 3

    fake_device.update_error = None
    status = await coordinator._async_update_data()

    assert status.in_standby is False
    assert coordinator.offline_failures == 0


async def test_authentication_failure_asks_for_reauth_once(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Wrong credentials back off too, and the reauth flow opens only once."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())
    fake_device.update_error = InvalidAuthError()

    with patch.object(
        ConfigEntry, "async_start_reauth_if_available", return_value=True
    ) as start_reauth:
        for _ in range(3):
            with pytest.raises(UpdateFailed) as err:
                await coordinator._async_update_data()

    assert start_reauth.call_count == 1
    assert err.value.retry_after == OFFLINE_RETRY_DELAYS[2]
    assert coordinator.offline_failures == 3


async def test_authentication_failure_asks_again_after_a_recovery(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """A new outage after a successful poll asks for reauth again."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())

    with patch.object(
        ConfigEntry, "async_start_reauth_if_available", return_value=True
    ) as start_reauth:
        fake_device.update_error = InvalidAuthError()
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        fake_device.update_error = None
        await coordinator._async_update_data()
        fake_device.update_error = InvalidAuthError()
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    assert start_reauth.call_count == 2


async def test_unexpected_error_also_backs_off(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """An unexpected poll error must not turn into a request per scan interval."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())
    fake_device.update_error = ValueError("something new in the API")

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.retry_after == OFFLINE_RETRY_DELAYS[0]
    assert "Unexpected error" in str(err.value)
    assert coordinator.offline_failures == 1


async def test_power_command_resets_the_backoff(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """Waking the box up polls it at the normal interval again."""
    coordinator = AdvEnigma2UpdateCoordinator(hass, make_entry())
    fake_device.update_error = ClientError("Cannot connect to host")
    for _ in range(4):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    assert coordinator.offline_failures == 4

    coordinator.async_reset_offline_backoff()

    assert coordinator.offline_failures == 0


async def test_setup_retries_when_the_box_is_off(
    hass: HomeAssistant, make_entry, fake_device
) -> None:
    """A box that is off while Home Assistant starts is a retry, not a failure."""
    from homeassistant.config_entries import ConfigEntryState

    fake_device.about_error = ClientError("Cannot connect to host")
    entry = make_entry()

    assert await hass.config_entries.async_setup(entry.entry_id) is False
    assert entry.state is ConfigEntryState.SETUP_RETRY
