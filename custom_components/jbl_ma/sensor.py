"""Diagnostic sensors — streaming server name & state."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STREAM_SERVERS, STREAM_STATES
from .coordinator import JBLCoordinator
from .entity import JBLEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JBLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            JBLStreamServerSensor(coordinator),
            JBLStreamStateSensor(coordinator),
        ]
    )


class JBLStreamServerSensor(JBLEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:music"

    def __init__(self, coordinator: JBLCoordinator) -> None:
        super().__init__(coordinator, "sensor_stream_server")
        self._attr_name = "Streaming Source"

    @property
    def native_value(self) -> str | None:
        sid = self.coordinator.client.state.get("stream_server")
        if sid is None:
            return None
        return STREAM_SERVERS.get(sid, f"id={sid}")


class JBLStreamStateSensor(JBLEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:play-pause"

    def __init__(self, coordinator: JBLCoordinator) -> None:
        super().__init__(coordinator, "sensor_stream_state")
        self._attr_name = "Streaming State"

    @property
    def native_value(self) -> str | None:
        sid = self.coordinator.client.state.get("stream_state")
        if sid is None:
            return None
        return STREAM_STATES.get(sid, f"id={sid}")
