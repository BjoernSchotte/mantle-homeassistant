"""The button "Neu laden" on each TV: config, apps and plugins (device command `reload`)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MantleConfigEntry
from .api import MantleError
from .const import SIGNAL_NEW_DEVICE
from .entity import MantleEntity
from .hub import MantleHub


class ReloadButton(MantleEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub: MantleHub, device_id: str) -> None:
        super().__init__(hub, device_id, "reload")

    async def async_press(self) -> None:
        try:
            await self.hub.command(self.device_id, "reload")
        except MantleError as err:
            raise HomeAssistantError(str(err)) from err


async def async_setup_entry(hass: HomeAssistant, entry: MantleConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    hub = entry.runtime_data
    add([ReloadButton(hub, device_id) for device_id in hub.devices])

    @callback
    def new_device(device_id: str) -> None:
        add([ReloadButton(hub, device_id)])

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE.format(entry.entry_id), new_device))
