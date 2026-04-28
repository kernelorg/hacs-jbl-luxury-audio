"""Shared base entity for the JBL MA integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS
from .coordinator import JBLCoordinator
from .jbl import JBLError


class JBLEntity(CoordinatorEntity[JBLCoordinator]):
    """Common base — wires the coordinator to a single device entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: JBLCoordinator, key: str) -> None:
        super().__init__(coordinator)
        host = coordinator.client.host
        port = coordinator.client.port
        device_id = f"{host}:{port}"
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="JBL / Harman",
            model=MODELS.get(coordinator.model, "MA Series"),
            name=f"JBL {MODELS.get(coordinator.model, 'MA AVR')} ({host})",
            configuration_url=f"https://{host}/webclient/",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.client.connected

    async def _dispatch(self, action_label: str, coro: Awaitable) -> None:
        """Run a client coroutine and translate transport errors to user-facing
        HomeAssistantError so the HA UI shows a meaningful message instead of
        a generic 'unknown error'.
        """
        try:
            await coro
        except JBLError as err:
            raise HomeAssistantError(f"AVR rejected '{action_label}': {err}") from err
        except asyncio.TimeoutError as err:
            raise HomeAssistantError(
                f"AVR did not respond to '{action_label}' in time"
            ) from err
        except (ConnectionError, OSError) as err:
            raise HomeAssistantError(
                f"Lost connection to AVR while sending '{action_label}': {err}"
            ) from err
