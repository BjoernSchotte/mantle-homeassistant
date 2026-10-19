"""Base of all Mantle entities: one TV, its `hub.device.<id>` state, unavailable while the hub is away."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_AVAILABLE, SIGNAL_STATE
from .hub import MantleHub


class MantleEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: MantleHub, device_id: str, key: str) -> None:
        self.hub = hub
        self.device_id = device_id
        device = hub.devices[device_id]
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("name"),
            manufacturer="Mantle",
            model=device.get("model"),
            sw_version=device.get("mantleVersion"),
        )

    @property
    def attrs(self) -> dict[str, Any]:
        return (self.hub.states.get(self.device_id) or {}).get("attrs") or {}

    @property
    def available(self) -> bool:
        return self.hub.available and self.device_id in self.hub.states

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_STATE.format(self.device_id), self.async_write_ha_state)
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_AVAILABLE.format(self.hub.entry_id), self.async_write_ha_state)
        )
