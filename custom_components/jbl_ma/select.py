"""Select entities — input source, surround mode, display dim, Dolby
audio mode, room EQ.

Source and Surround are also exposed via the media_player entity, but a lot
of dashboards want them as plain dropdown rows — that's what these provide.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DIM_LEVELS,
    DOMAIN,
    supported_dolby,
    supported_room_eq,
    supported_sources,
    supported_surround,
)
from .coordinator import JBLCoordinator
from .entity import JBLEntity
from .jbl import JBLClient


@dataclass(frozen=True)
class JBLSelectSpec:
    key: str
    name: str
    state_key: str
    icon: str | None
    options_for_model: Callable[[int | None], dict[int, str]]
    setter: Callable[[JBLClient, int], Awaitable[None]]
    entity_category: EntityCategory | None = EntityCategory.CONFIG


SPECS: tuple[JBLSelectSpec, ...] = (
    JBLSelectSpec(
        key="source", name="Input", state_key="source", icon="mdi:audio-input-stereo-minijack",
        options_for_model=supported_sources,
        setter=lambda c, v: c.set_source(v),
        entity_category=None,  # primary control, not diagnostic
    ),
    JBLSelectSpec(
        key="surround", name="Surround Mode", state_key="surround",
        icon="mdi:surround-sound",
        options_for_model=supported_surround,
        setter=lambda c, v: c.set_surround(v),
        entity_category=None,
    ),
    JBLSelectSpec(
        key="dim", name="Display Dim", state_key="dim", icon="mdi:brightness-6",
        options_for_model=lambda _model: dict(DIM_LEVELS),
        setter=lambda c, v: c.set_dim(v),
    ),
    JBLSelectSpec(
        key="dolby_mode", name="Dolby Audio Mode", state_key="dolby_mode",
        icon="mdi:dolby",
        options_for_model=supported_dolby,
        setter=lambda c, v: c.set_dolby_mode(v),
    ),
    JBLSelectSpec(
        key="room_eq", name="Room EQ", state_key="room_eq",
        icon="mdi:equalizer",
        options_for_model=supported_room_eq,
        setter=lambda c, v: c.set_room_eq(v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JBLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(JBLSelect(coordinator, spec) for spec in SPECS)


class JBLSelect(JBLEntity, SelectEntity):
    def __init__(self, coordinator: JBLCoordinator, spec: JBLSelectSpec) -> None:
        super().__init__(coordinator, f"select_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_entity_category = spec.entity_category
        self._id_to_name = spec.options_for_model(coordinator.model)
        self._name_to_id = {v: k for k, v in self._id_to_name.items()}
        self._attr_options = list(self._id_to_name.values())

    @property
    def current_option(self) -> str | None:
        sid = self.coordinator.client.state.get(self._spec.state_key)
        return self._id_to_name.get(sid)

    async def async_select_option(self, option: str) -> None:
        sid = self._name_to_id.get(option)
        if sid is None:
            return
        await self._dispatch(
            f"set {self._spec.name.lower()} to '{option}'",
            self._spec.setter(self.coordinator.client, sid),
        )
