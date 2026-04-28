"""Switch entities — party mode, dialog enhancement, DRC."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, feature
from .coordinator import JBLCoordinator
from .entity import JBLEntity
from .jbl import JBLClient


@dataclass(frozen=True)
class JBLSwitchSpec:
    key: str
    name: str
    state_key: str
    icon: str | None
    setter: Callable[[JBLClient, bool], Awaitable[None]]
    feature: str | None = None


SPECS: tuple[JBLSwitchSpec, ...] = (
    JBLSwitchSpec(
        key="party", name="Party Mode", state_key="party", icon="mdi:party-popper",
        setter=lambda c, on: c.set_party(on), feature="party",
    ),
    JBLSwitchSpec(
        key="dialog", name="Dialog Enhancement", state_key="dialog",
        icon="mdi:account-voice",
        setter=lambda c, on: c.set_dialog(on),
    ),
    JBLSwitchSpec(
        key="drc", name="Dolby/DTS DRC", state_key="drc", icon="mdi:waveform",
        setter=lambda c, on: c.set_drc(on), feature="drc",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JBLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JBLSwitch(coordinator, spec)
        for spec in SPECS
        if spec.feature is None or feature(coordinator.model, spec.feature)
    )


class JBLSwitch(JBLEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: JBLCoordinator, spec: JBLSwitchSpec) -> None:
        super().__init__(coordinator, f"switch_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.client.state.get(self._spec.state_key)

    async def async_turn_on(self, **kwargs) -> None:
        await self._dispatch(
            f"enable {self._spec.name.lower()}",
            self._spec.setter(self.coordinator.client, True),
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self._dispatch(
            f"disable {self._spec.name.lower()}",
            self._spec.setter(self.coordinator.client, False),
        )
