"""Online and screen of each TV."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MantleConfigEntry
from .const import SIGNAL_NEW_DEVICE
from .entity import MantleEntity
from .hub import MantleHub


class OnlineSensor(MantleEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hub: MantleHub, device_id: str) -> None:
        super().__init__(hub, device_id, "online")

    @property
    def is_on(self) -> bool:
        return (self.hub.states.get(self.device_id) or {}).get("state") == "online"


class ScreenSensor(MantleEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, hub: MantleHub, device_id: str) -> None:
        super().__init__(hub, device_id, "screen")

    @property
    def is_on(self) -> bool | None:
        value = self.attrs.get("screenOn")
        return value if isinstance(value, bool) else None


def _entities(hub: MantleHub, device_id: str) -> list[BinarySensorEntity]:
    return [OnlineSensor(hub, device_id), ScreenSensor(hub, device_id)]


async def async_setup_entry(hass: HomeAssistant, entry: MantleConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    hub = entry.runtime_data
    add([e for device_id in hub.devices for e in _entities(hub, device_id)])

    @callback
    def new_device(device_id: str) -> None:
        add(_entities(hub, device_id))

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE.format(entry.entry_id), new_device))
