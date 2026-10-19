"""Mantle: the TVs of a Mantle hub as Home Assistant devices, hub actions as services, hub events on the bus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .api import ACTION_NAME, MantleAuthError, MantleClient, MantleError
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .hub import MantleHub

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MantleConfigEntry = ConfigEntry[MantleHub]

OPEN_SPACE_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string, vol.Required("space"): cv.string})
CALL_ACTION_SCHEMA = vol.Schema(
    {vol.Required("action"): vol.All(cv.string, vol.Match(ACTION_NAME)), vol.Optional("data", default={}): dict}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Services are registered once and find the hub through the device or the only entry."""

    def hub_and_device(device_id: str) -> tuple[MantleHub, str]:
        device = dr.async_get(hass).async_get(device_id)
        mantle_id = next((ident for domain, ident in device.identifiers if domain == DOMAIN), None) if device else None
        if device is None or mantle_id is None:
            raise ServiceValidationError("Das ist kein Mantle-Gerät")
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
                return entry.runtime_data, mantle_id
        raise ServiceValidationError("Der Mantle Hub dieses Geräts ist nicht geladen")

    async def open_space(call: ServiceCall) -> None:
        hub, mantle_id = hub_and_device(call.data["device_id"])
        try:
            result = await hub.command(mantle_id, "openSpace", {"id": call.data["space"]})
        except MantleError as err:
            raise HomeAssistantError(str(err)) from err
        if isinstance(result, dict) and result.get("sent") is False:
            raise HomeAssistantError("Der Fernseher ist nicht mit dem Hub verbunden")

    async def call_action(call: ServiceCall) -> ServiceResponse:
        entries = [e for e in hass.config_entries.async_loaded_entries(DOMAIN)]
        if not entries:
            raise ServiceValidationError("Kein Mantle Hub eingerichtet")
        hub: MantleHub = entries[0].runtime_data
        try:
            result: Any = await hub.client.call_action(call.data["action"], call.data["data"])
        except MantleError as err:
            raise HomeAssistantError(str(err)) from err
        return {"result": result}

    hass.services.async_register(DOMAIN, "open_space", open_space, schema=OPEN_SPACE_SCHEMA)
    # Any hub action the token allows, admin ones included: only HA admins may call it.
    async_register_admin_service(
        hass, DOMAIN, "call_action", call_action, CALL_ACTION_SCHEMA, SupportsResponse.OPTIONAL
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MantleConfigEntry) -> bool:
    client = MantleClient(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    hub = MantleHub(hass, entry, client)
    try:
        await client.me()
        await hub.async_start()
    except MantleAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except MantleError as err:
        raise ConfigEntryNotReady(str(err)) from err
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MantleConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
