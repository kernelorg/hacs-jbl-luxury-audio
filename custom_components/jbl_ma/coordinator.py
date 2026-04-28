"""Lightweight push-style coordinator for the JBL MA AVR client.

The AVR streams unsolicited state changes over its TCP socket, so we don't
poll. The client calls back into us whenever any state field changes; we
forward that to listening entities through DataUpdateCoordinator.
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .jbl import JBLClient

_LOGGER = logging.getLogger(__name__)


class JBLCoordinator(DataUpdateCoordinator[dict]):
    """Bridge between the JBL client and Home Assistant entities."""

    def __init__(self, hass: HomeAssistant, client: JBLClient, model: int | None) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.client = client
        self.model = model
        self._unsub = client.add_listener(self._on_state)

    @callback
    def _on_state(self) -> None:
        # Push the freshest snapshot of client state to all listeners.
        self.async_set_updated_data(dict(self.client.state))

    async def async_close(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        await self.client.stop()
