"""Button entities — IR-remote navigation, reboot, factory reset.

Navigation buttons are regular dashboard controls (no entity_category) so
they're easy to put on a card as a virtual remote. Reboot / factory reset
stay in the CONFIG bucket since they're administrative.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, IR_CODES
from .coordinator import JBLCoordinator
from .entity import JBLEntity
from .jbl import JBLClient


@dataclass(frozen=True)
class JBLButtonSpec:
    key: str
    name: str
    icon: str | None
    action: Callable[[JBLClient], Awaitable[None]]
    device_class: ButtonDeviceClass | None = None
    enabled_by_default: bool = True
    entity_category: EntityCategory | None = None


def _ir(name: str) -> Callable[[JBLClient], Awaitable[None]]:
    code = IR_CODES[name]
    return lambda c: c.send_ir(code)


# Remote-control navigation. Same set as on the physical IR remote.
NAV_SPECS: tuple[JBLButtonSpec, ...] = (
    JBLButtonSpec("nav_up",    "Up",    "mdi:arrow-up-bold",    _ir("up")),
    JBLButtonSpec("nav_down",  "Down",  "mdi:arrow-down-bold",  _ir("down")),
    JBLButtonSpec("nav_left",  "Left",  "mdi:arrow-left-bold",  _ir("left")),
    JBLButtonSpec("nav_right", "Right", "mdi:arrow-right-bold", _ir("right")),
    JBLButtonSpec("nav_ok",    "OK",    "mdi:circle-slice-8",   _ir("ok")),
    JBLButtonSpec("nav_back",  "Back",  "mdi:keyboard-backspace", _ir("back")),
    JBLButtonSpec("nav_menu",  "Menu",  "mdi:menu",             _ir("menu")),
)

ADMIN_SPECS: tuple[JBLButtonSpec, ...] = (
    JBLButtonSpec(
        key="reboot", name="Reboot", icon="mdi:restart",
        device_class=ButtonDeviceClass.RESTART,
        action=lambda c: c.reboot(),
        entity_category=EntityCategory.CONFIG,
    ),
    JBLButtonSpec(
        key="factory_reset", name="Factory Reset", icon="mdi:restore-alert",
        action=lambda c: c.factory_reset(),
        enabled_by_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JBLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JBLButton(coordinator, spec) for spec in (*NAV_SPECS, *ADMIN_SPECS)
    )


class JBLButton(JBLEntity, ButtonEntity):
    def __init__(self, coordinator: JBLCoordinator, spec: JBLButtonSpec) -> None:
        super().__init__(coordinator, f"button_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_device_class = spec.device_class
        self._attr_entity_registry_enabled_default = spec.enabled_by_default
        self._attr_entity_category = spec.entity_category

    async def async_press(self) -> None:
        await self._dispatch(self._spec.name.lower(), self._spec.action(self.coordinator.client))
