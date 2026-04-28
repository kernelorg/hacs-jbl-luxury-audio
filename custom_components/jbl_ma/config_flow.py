"""Config flow for JBL MA Series AVR.

Two entry paths:
  * zeroconf discovery — the AVR is found on the LAN via mDNS, the user just
    confirms it.
  * user — manual host entry as a fallback.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_MODEL, DEFAULT_PORT, DOMAIN, MODELS
from .jbl import JBLClient

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
            NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
        ),
    }
)


def _looks_like_jbl_ma(name: str | None, properties: dict) -> bool:
    """Best-effort filter for JBL MA series mDNS records.

    The manifest already narrows by service+name, but mDNS forwarders sometimes
    deliver entries we don't actually want — double-check here.
    """
    blob = " ".join(
        str(v).lower()
        for v in (
            name,
            properties.get("model"),
            properties.get("manufacturer"),
            properties.get("md"),   # googlecast model
            properties.get("am"),   # raop model
            properties.get("mn"),   # tidalconnect model
            properties.get("fn"),   # friendly name
        )
        if v
    )
    if not blob:
        return True  # don't reject when the record is empty
    if "harman luxury audio" in blob:
        return True
    if "jbl" in blob and ("ma510" in blob or "ma710" in blob
                          or "ma7100" in blob or "ma9100" in blob
                          or " ma " in f" {blob} "):
        return True
    return any(m in blob for m in ("ma510", "ma710", "ma7100hp", "ma9100hp"))


class JBLMAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the user-driven and zeroconf-driven config flows."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._discovered_model: int | None = None

    # ------------------------------------------------- manual / fallback path

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                model = await JBLClient(host, port).async_test_connection()
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error testing JBL %s", host)
                errors["base"] = "unknown"
            else:
                title = MODELS.get(model, f"JBL MA AVR ({host})")
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port, CONF_MODEL: model},
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    # ------------------------------------------------------ zeroconf path

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        host = discovery_info.host
        # The IP-control protocol is on a fixed TCP port (50000); the discovered
        # AirPlay/Cast port is irrelevant — we only use the IP.
        port = DEFAULT_PORT
        name = discovery_info.name or ""
        properties = {
            (k.decode(errors="replace") if isinstance(k, bytes) else k):
            (v.decode(errors="replace") if isinstance(v, bytes) else v)
            for k, v in (discovery_info.properties or {}).items()
        }
        _LOGGER.debug(
            "JBL MA zeroconf candidate: type=%s name=%s host=%s props=%s",
            discovery_info.type, name, host, properties,
        )

        if not _looks_like_jbl_ma(name, properties):
            _LOGGER.debug("JBL MA zeroconf rejected by filter: name=%s props=%s",
                          name, properties)
            return self.async_abort(reason="not_jbl_ma")

        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Probe the AVR before showing the confirmation form so we can refuse
        # discoveries that don't actually speak this protocol.
        try:
            model = await JBLClient(host, port).async_test_connection()
        except (asyncio.TimeoutError, OSError) as exc:
            _LOGGER.debug("JBL MA discovered at %s but IP-control probe failed: %s",
                          host, exc)
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error testing discovered JBL %s", host)
            return self.async_abort(reason="unknown")

        self._discovered_host = host
        self._discovered_name = (
            properties.get("fn") or properties.get("friendlyName")
            or name.split(".")[0] or host
        )
        self._discovered_model = model
        # Seed the title shown in the discovered-device card.
        self.context["title_placeholders"] = {
            "name": MODELS.get(model, "JBL MA AVR"),
            "host": host,
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovered_host is not None
        host = self._discovered_host
        model = self._discovered_model
        if user_input is not None:
            title = MODELS.get(model, f"JBL MA AVR ({host})")
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: host,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_MODEL: model,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": MODELS.get(model, "JBL MA AVR"),
                "host": host,
            },
        )
