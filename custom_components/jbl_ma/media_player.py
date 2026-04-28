"""Media player entity for the JBL MA AVR (power / volume / source / sound mode)."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SOURCES,
    STREAM_SERVERS,
    STREAM_STATES,
    SURROUND_MODES,
    supported_sources,
    supported_surround,
)
from .coordinator import JBLCoordinator
from .entity import JBLEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JBLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JBLMediaPlayer(coordinator)])


class JBLMediaPlayer(JBLEntity, MediaPlayerEntity):
    _attr_name = None  # use device name
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )

    def __init__(self, coordinator: JBLCoordinator) -> None:
        super().__init__(coordinator, "media_player")
        self._sources = supported_sources(coordinator.model)
        self._surround = supported_surround(coordinator.model)
        # name -> id reverse lookups
        self._source_to_id = {v: k for k, v in self._sources.items()}
        self._surround_to_id = {v: k for k, v in self._surround.items()}

    # --- state -----------------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState | None:
        if not self.coordinator.client.connected:
            return None
        if self.coordinator.client.state.get("power"):
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        v = self.coordinator.client.state.get("volume")
        if v is None:
            return None
        return v / 99.0

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.client.state.get("mute")

    @property
    def source(self) -> str | None:
        sid = self.coordinator.client.state.get("source")
        # Fall back to global SOURCES so we always show the name even if the
        # selection is one we filtered out for this model.
        return self._sources.get(sid) or SOURCES.get(sid)

    @property
    def source_list(self) -> list[str]:
        return list(self._sources.values())

    @property
    def sound_mode(self) -> str | None:
        sid = self.coordinator.client.state.get("surround")
        return self._surround.get(sid) or SURROUND_MODES.get(sid)

    @property
    def sound_mode_list(self) -> list[str]:
        return list(self._surround.values())

    @property
    def extra_state_attributes(self) -> dict:
        s = self.coordinator.client.state
        attrs: dict = {}
        if "stream_server" in s:
            attrs["stream_server"] = STREAM_SERVERS.get(s["stream_server"], f"id={s['stream_server']}")
        if "stream_state" in s:
            attrs["stream_state"] = STREAM_STATES.get(s["stream_state"], f"id={s['stream_state']}")
        return attrs

    # --- commands --------------------------------------------------------------

    async def async_turn_on(self) -> None:
        await self._dispatch("turn on", self.coordinator.client.set_power(True))

    async def async_turn_off(self) -> None:
        await self._dispatch("turn off", self.coordinator.client.set_power(False))

    async def async_set_volume_level(self, volume: float) -> None:
        await self._dispatch(
            "set volume", self.coordinator.client.set_volume(round(volume * 99))
        )

    async def async_volume_up(self) -> None:
        cur = self.coordinator.client.state.get("volume", 0)
        await self._dispatch("volume up", self.coordinator.client.set_volume(cur + 1))

    async def async_volume_down(self) -> None:
        cur = self.coordinator.client.state.get("volume", 0)
        await self._dispatch("volume down", self.coordinator.client.set_volume(cur - 1))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._dispatch("mute" if mute else "unmute", self.coordinator.client.set_mute(mute))

    async def async_select_source(self, source: str) -> None:
        sid = self._source_to_id.get(source)
        if sid is None:
            return
        await self._dispatch(f"select source '{source}'", self.coordinator.client.set_source(sid))

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        sid = self._surround_to_id.get(sound_mode)
        if sid is None:
            return
        await self._dispatch(
            f"select sound mode '{sound_mode}'",
            self.coordinator.client.set_surround(sid),
        )
