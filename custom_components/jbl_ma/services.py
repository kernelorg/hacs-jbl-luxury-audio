"""Custom services exposed by the JBL MA integration.

- jbl_ma.send_ir   — send a remote-control IR code (by name or 24-bit int)
- jbl_ma.send_raw  — send arbitrary command id + data bytes (advanced)
"""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, IR_CODES
from .coordinator import JBLCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_IR = "send_ir"
SERVICE_SEND_RAW = "send_raw"


def _coerce_int(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise vol.Invalid("must be int or hex string")


SEND_IR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("code"): vol.Any(
            vol.In(IR_CODES.keys()),
            _coerce_int,
        ),
    }
)

SEND_RAW_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("command_id"): _coerce_int,
        vol.Optional("data", default=[]): [_coerce_int],
    }
)


def _coordinator_for_device(hass: HomeAssistant, device_id: str) -> JBLCoordinator:
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Unknown device {device_id}")
    for entry_id in device.config_entries:
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is not None:
            return coordinator
    raise HomeAssistantError(f"Device {device_id} is not a JBL MA AVR")


@callback
def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SEND_IR):
        return

    async def _send_ir(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[CONF_DEVICE_ID])
        raw = call.data["code"]
        code = IR_CODES[raw] if isinstance(raw, str) else int(raw)
        await coordinator.client.send_ir(code)

    async def _send_raw(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[CONF_DEVICE_ID])
        cmd_id = int(call.data["command_id"])
        data = [int(b) & 0xFF for b in call.data.get("data", [])]
        # use the public _request path for response handling
        await coordinator.client._request(cmd_id, data)  # noqa: SLF001

    hass.services.async_register(DOMAIN, SERVICE_SEND_IR, _send_ir, schema=SEND_IR_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SEND_RAW, _send_raw, schema=SEND_RAW_SCHEMA)


@callback
def async_unregister_services(hass: HomeAssistant) -> None:
    for svc in (SERVICE_SEND_IR, SERVICE_SEND_RAW):
        if hass.services.has_service(DOMAIN, svc):
            hass.services.async_remove(DOMAIN, svc)
