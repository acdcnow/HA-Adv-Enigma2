"""Support for Adv Enigma2 media players."""

import contextlib
from logging import getLogger
from typing import Any, override

from aiohttp.client_exceptions import ServerDisconnectedError
from openwebif.enums import PowerState, RemoteControlCodes, SetVolumeOption

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import (
    recording_uid,
    service_name,
    service_reference,
)
from .coordinator import AdvEnigma2ConfigEntry, AdvEnigma2UpdateCoordinator
from .entity import AdvEnigma2Entity

ATTR_MEDIA_CURRENTLY_RECORDING = "media_currently_recording"
ATTR_MEDIA_DESCRIPTION = "media_description"
ATTR_MEDIA_END_TIME = "media_end_time"
ATTR_MEDIA_START_TIME = "media_start_time"
ATTR_STREAM_URL = "stream_url"

# the media content types of the channel and recording browser
MEDIA_TYPE_BOUQUET = "bouquet"
MEDIA_TYPE_RECORDING = "recording"
MEDIA_ID_ROOT = "root"
MEDIA_ID_CHANNELS = "channels"
MEDIA_ID_RECORDINGS = "recordings"

_LOGGER = getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdvEnigma2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Adv Enigma2 media player platform."""
    async_add_entities([AdvEnigma2MediaPlayer(entry.runtime_data)])


class AdvEnigma2MediaPlayer(AdvEnigma2Entity, MediaPlayerEntity):
    """Representation of an Adv Enigma2 box."""

    _attr_name = None

    _attr_media_content_type = MediaType.TVSHOW
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, coordinator: AdvEnigma2UpdateCoordinator) -> None:
        """Initialize the Adv Enigma2 device."""
        super().__init__(coordinator)

        # bouquets whose entries could not be used, warned about only once
        self._warned_bouquets: set[str] = set()

    @override
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        if self.coordinator.device.turn_off_to_deep:
            # Deep standby shuts the box down, so it can stop answering in the
            # middle of the request. Whether it is really gone is decided by the
            # coordinator, which reports the entities as unavailable and keeps
            # polling with the offline back-off until the box answers again.
            # Not setting _attr_available here is on purpose: that would pin the
            # entity to unavailable until Home Assistant is restarted.
            # pylint: disable-next=home-assistant-action-swallowed-exception
            with contextlib.suppress(ServerDisconnectedError):
                await self.coordinator.device.set_powerstate(PowerState.DEEP_STANDBY)
        else:
            await self.coordinator.device.set_powerstate(PowerState.STANDBY)
        await self.coordinator.async_refresh()

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        # The box boots for a while, so drop a running offline back-off first:
        # polling must be back at the normal interval to see it come up.
        self.coordinator.async_reset_offline_backoff()
        await self.coordinator.device.turn_on()
        await self.coordinator.async_refresh()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.device.set_volume(int(volume * 100))
        await self.coordinator.async_refresh()

    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self.coordinator.device.set_volume(SetVolumeOption.UP)
        await self.coordinator.async_refresh()

    @override
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.device.set_volume(SetVolumeOption.DOWN)
        await self.coordinator.async_refresh()

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.STOP
        )
        await self.coordinator.async_refresh()

    @override
    async def async_media_play(self) -> None:
        """Play media."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.PLAY
        )
        await self.coordinator.async_refresh()

    @override
    async def async_media_pause(self) -> None:
        """Pause the media player."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.PAUSE
        )
        await self.coordinator.async_refresh()

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.CHANNEL_UP
        )
        await self.coordinator.async_refresh()

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.CHANNEL_DOWN
        )
        await self.coordinator.async_refresh()

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        if mute != self.coordinator.data.muted:
            await self.coordinator.device.toggle_mute()
            await self.coordinator.async_refresh()

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.coordinator.device.zap(self.coordinator.device.sources[source])
        await self.coordinator.async_refresh()

    @override
    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse the bouquets, the channels and the recordings of the box."""
        if media_content_id in (None, MEDIA_ID_ROOT):
            title, media_class, content_type, children = (
                self.name or "Adv Enigma2",
                MediaClass.DIRECTORY,
                MEDIA_ID_ROOT,
                [
                    self._directory("Channels", MEDIA_ID_CHANNELS),
                    self._directory("Recordings", MEDIA_ID_RECORDINGS),
                ],
            )
        elif media_content_id == MEDIA_ID_CHANNELS:
            bouquets = await self.coordinator.device.get_all_bouquets()
            title, media_class, content_type = "Channels", MediaClass.DIRECTORY, "bouquets"
            children = [
                BrowseMedia(
                    title=name,
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=reference,
                    media_content_type=MEDIA_TYPE_BOUQUET,
                    can_play=False,
                    can_expand=True,
                )
                for reference, name in bouquets.get("bouquets", [])
            ]
        elif media_content_type == MEDIA_TYPE_BOUQUET:
            services = await self.coordinator.api.async_get_services(media_content_id)
            title, media_class, content_type = "Channels", MediaClass.DIRECTORY, MEDIA_TYPE_BOUQUET
            children = [
                BrowseMedia(
                    title=name,
                    media_class=MediaClass.CHANNEL,
                    media_content_id=reference,
                    media_content_type=MediaType.CHANNEL,
                    can_play=True,
                    can_expand=False,
                )
                for reference, name in (
                    (service_reference(service), service_name(service) or "?")
                    for service in services
                )
                if reference
            ]
            self._async_warn_about_unusable_services(media_content_id, services, children)
        elif media_content_id == MEDIA_ID_RECORDINGS:
            movies = await self.coordinator.api.async_get_recordings()
            title, media_class, content_type = "Recordings", MediaClass.DIRECTORY, MEDIA_TYPE_RECORDING
            children = [
                BrowseMedia(
                    title=movie.get("eventname")
                    or movie.get("title")
                    or movie.get("filename_stripped", "?"),
                    media_class=MediaClass.MOVIE,
                    media_content_id=recording_uid(movie),
                    media_content_type=MEDIA_TYPE_RECORDING,
                    can_play=True,
                    can_expand=False,
                )
                for movie in movies
            ]
        else:
            raise BrowseError(f"Cannot browse {media_content_id}")

        return BrowseMedia(
            title=title,
            media_class=media_class,
            media_content_id=media_content_id or MEDIA_ID_ROOT,
            media_content_type=content_type,
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _async_warn_about_unusable_services(
        self,
        bouquet: str,
        services: list[dict[str, Any]],
        children: list[BrowseMedia],
    ) -> None:
        """Report the entries of a bouquet that cannot be played.

        A bouquet may legitimately hold entries that are not a channel (markers of
        a sub bouquet), so only a bouquet without any usable entry is worth a
        warning. The keys of the answer are logged as well, because they are what
        identifies a box that answers a different shape than expected.
        """
        if len(children) == len(services) or bouquet in self._warned_bouquets:
            return
        self._warned_bouquets.add(bouquet)

        keys = sorted({key for service in services for key in service})
        if not children:
            _LOGGER.warning(
                "%s returned %s entr(y/ies) for the bouquet %s, but none of them "
                "could be used (keys: %s)",
                self.coordinator.host,
                len(services),
                bouquet,
                keys,
            )
        else:
            _LOGGER.debug(
                "%s returned %s entr(y/ies) for the bouquet %s, %s of them are not "
                "channels (keys: %s)",
                self.coordinator.host,
                len(services),
                bouquet,
                len(services) - len(children),
                keys,
            )

    def _directory(self, title: str, media_id: str) -> BrowseMedia:
        """Return a folder of the media browser."""
        return BrowseMedia(
            title=title,
            media_class=MediaClass.DIRECTORY,
            media_content_id=media_id,
            media_content_type=media_id,
            can_play=False,
            can_expand=True,
        )

    @override
    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: object
    ) -> None:
        """Tune to a channel, play a recording or tune to a stream of the box."""
        if media_type == MediaType.CHANNEL or media_id.startswith("1:"):
            # a channel, or a recording: OpenWebif plays a recording by zapping to
            # the service reference of the movie
            await self.coordinator.device.zap(media_id)
        elif media_type == MediaType.URL:
            # a stream url of this box, e.g. http://box:8001/1:0:19:...
            await self.coordinator.device.zap(media_id.rsplit("/", 1)[-1])
        else:
            raise HomeAssistantError(
                f"The box cannot play media of type {media_type}; use the channel "
                "browser of this entity instead"
            )
        await self.coordinator.async_request_refresh()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update state of the media_player."""

        if not self.coordinator.data.in_standby:
            self._attr_extra_state_attributes = {
                ATTR_MEDIA_CURRENTLY_RECORDING: self.coordinator.data.is_recording,
                ATTR_MEDIA_DESCRIPTION: (
                    self.coordinator.data.currservice.fulldescription
                ),
                ATTR_MEDIA_START_TIME: self.coordinator.data.currservice.begin,
                ATTR_MEDIA_END_TIME: self.coordinator.data.currservice.end,
            }
        else:
            self._attr_extra_state_attributes = {}

        # the stream url of the running channel, so that it can be handed to
        # another media player (a recording has no stream on the box)
        if (serviceref := self.coordinator.data.currservice.serviceref) and not str(
            serviceref
        ).startswith("1:0:0"):
            self._attr_extra_state_attributes[ATTR_STREAM_URL] = (
                self.coordinator.api.stream_url(str(serviceref))
            )

        self._attr_media_title = self.coordinator.data.currservice.station
        self._attr_media_series_title = self.coordinator.data.currservice.name
        self._attr_media_channel = self.coordinator.data.currservice.station
        self._attr_is_volume_muted = self.coordinator.data.muted
        self._attr_media_content_id = self.coordinator.data.currservice.serviceref
        self._attr_media_image_url = self.coordinator.device.picon_url
        self._attr_source = self.coordinator.data.currservice.station
        self._attr_source_list = self.coordinator.device.source_list

        if self.coordinator.data.in_standby:
            self._attr_state = MediaPlayerState.OFF
        else:
            self._attr_state = MediaPlayerState.ON

        if (volume_level := self.coordinator.data.volume) is not None:
            self._attr_volume_level = volume_level / 100
        else:
            self._attr_volume_level = None

        self.async_write_ha_state()
