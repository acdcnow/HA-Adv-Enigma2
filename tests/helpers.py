"""Shared helpers for the Adv Enigma2 tests."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def setup_entry(hass: HomeAssistant, make_entry, **kwargs):
    """Set up a config entry of the fake box and return it."""
    entry = make_entry(**kwargs)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass: HomeAssistant, domain: str, name: str | None = None) -> str:
    """Return the entity id of a platform, or of one entity of it.

    With `has_entity_name` the entity id is the (translated) device name followed
    by the (translated) entity name, so the entity is selected by the key the code
    uses, which is the last part of its unique id.
    """
    ids = hass.states.async_entity_ids(domain)
    if name is None:
        assert len(ids) == 1, ids
        return ids[0]

    registry = er.async_get(hass)
    matches = [
        entry.entity_id
        for entry in registry.entities.values()
        if entry.domain == domain and (entry.unique_id or "").endswith(f"-{name}")
    ]
    if not matches:
        # the entity id is the slug of the translated name, which can differ from
        # the key the code uses (`signal_snr` -> `tuner_signal_snr`)
        matches = [entity for entity in ids if entity.endswith(name)]
    assert len(matches) == 1, f"{name}: {ids}"
    return matches[0]
