"""App in front, Mantle version and configuration state of each TV."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MantleConfigEntry
from .const import SIGNAL_NEW_DEVICE
from .entity import MantleEntity
from .hub import MantleHub


class AttrSensor(MantleEntity, SensorEntity):
    """One attribute of `hub.device.<id>`."""

    def __init__(self, hub: MantleHub, device_id: str, key: str, attr: str, *, diagnostic: bool = False) -> None:
        super().__init__(hub, device_id, key)
        self._attr = attr
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        value = self.attrs.get(self._attr)
        return str(value) if value is not None else None


def _entities(hub: MantleHub, device_id: str) -> list[SensorEntity]:
    return [
        AttrSensor(hub, device_id, "foreground_app", "foreground"),
        AttrSensor(hub, device_id, "mantle_version", "mantleVersion", diagnostic=True),
        AttrSensor(hub, device_id, "configuration", "config", diagnostic=True),
    ]


async def async_setup_entry(hass: HomeAssistant, entry: MantleConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    hub = entry.runtime_data
    add([e for device_id in hub.devices for e in _entities(hub, device_id)])

    @callback
    def new_device(device_id: str) -> None:
        add(_entities(hub, device_id))

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE.format(entry.entry_id), new_device))
