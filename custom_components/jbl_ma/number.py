"""Number entities — treble, bass, party-out volume."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, feature
from .coordinator import JBLCoordinator
from .entity import JBLEntity
from .jbl import JBLClient


@dataclass(frozen=True)
class JBLNumberSpec:
    key: str
    name: str
    state_key: str
    min_value: float
    max_value: float
    step: float
    unit: str | None
    icon: str | None
    setter: Callable[[JBLClient, int], Awaitable[None]]
    feature: str | None = None  # gate by model-feature flag


SPECS: tuple[JBLNumberSpec, ...] = (
    JBLNumberSpec(
        key="treble", name="Treble", state_key="treble",
        min_value=-12, max_value=12, step=1, unit="dB", icon="mdi:tune-vertical",
        setter=lambda c, v: c.set_treble(int(v)),
    ),
    JBLNumberSpec(
        key="bass", name="Bass", state_key="bass",
        min_value=-12, max_value=12, step=1, unit="dB", icon="mdi:tune-vertical",
        setter=lambda c, v: c.set_bass(int(v)),
    ),
    JBLNumberSpec(
        key="party_volume", name="Party Volume", state_key="party_volume",
        min_value=0, max_value=99, step=1, unit=None, icon="mdi:party-popper",
        setter=lambda c, v: c.set_party_volume(int(v)),
        feature="party",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JBLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JBLNumber(coordinator, spec)
        for spec in SPECS
        if spec.feature is None or feature(coordinator.model, spec.feature)
    )


class JBLNumber(JBLEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: JBLCoordinator, spec: JBLNumberSpec) -> None:
        super().__init__(coordinator, f"number_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_native_min_value = spec.min_value
        self._attr_native_max_value = spec.max_value
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_icon = spec.icon

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.client.state.get(self._spec.state_key)
        return None if v is None else float(v)

    async def async_set_native_value(self, value: float) -> None:
        await self._dispatch(
            f"set {self._spec.name.lower()} to {int(value)}",
            self._spec.setter(self.coordinator.client, int(value)),
        )
