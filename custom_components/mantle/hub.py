"""One connection per config entry: the TVs of the hub, their live states (`/api/live`) and the hub's events."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import MantleClient, MantleError
from .const import EVENT, SIGNAL_AVAILABLE, SIGNAL_NEW_DEVICE, SIGNAL_STATE, STATE_PREFIX

_LOGGER = logging.getLogger(__name__)

#: Waits before reconnect attempt n (the last one repeats).
RETRY_SECONDS: tuple[float, ...] = (1, 2, 5, 10, 30, 60)


class MantleHub:
    """Keeps `/api/live` open: states of `hub.device.<id>` go to the entities, events to the HA bus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: MantleClient) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.client = client
        #: Mantle device id → device as `/api/ext/devices/list` lists it.
        self.devices: dict[str, dict[str, Any]] = {}
        #: Mantle device id → last `hub.device.<id>` state record.
        self.states: dict[str, dict[str, Any]] = {}
        self.available = False
        self._task: asyncio.Task[None] | None = None
        self._warned_events = False
        self._refreshing = False
        #: Device ids the hub's list did not return; asked again only after a reconnect.
        self._unknown: set[str] = set()
        #: Logged once per outage and once when it ends, as HA asks (log-when-unavailable).
        self._was_connected = False
        self._outage_logged = False

    async def async_start(self) -> None:
        """Loads the device list (raises MantleError) and opens the live connection in the background."""
        self.devices = {d["id"]: d for d in await self.client.devices()}
        self._task = self.entry.async_create_background_task(self.hass, self._run(), f"mantle live {self.entry_id}")

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._set_available(False)

    async def _run(self) -> None:
        attempt = 0
        while True:
            try:
                async with self.client.live() as ws:
                    self._unknown.clear()
                    await ws.send_json({"subscribe": ["states", "events:*"]})
                    async for msg in ws:
                        if msg.type is not aiohttp.WSMsgType.TEXT:
                            continue
                        attempt = 0
                        self._handle(msg.json())
            except asyncio.CancelledError:
                raise
            except aiohttp.WSServerHandshakeError as err:
                if err.status in (401, 403):
                    # Retrying a revoked token cannot help: ask for a new one and stop here.
                    _LOGGER.warning("Mantle Hub: Der Hub lehnt das Token ab; bitte ein neues eintragen")
                    self._set_available(False)
                    self.entry.async_start_reauth(self.hass)
                    return
                _LOGGER.debug("Mantle Hub: Verbindung abgelehnt (%s)", err)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.debug("Mantle Hub: Verbindung getrennt (%s)", err)
            if self._was_connected:
                self._was_connected = False
                self._outage_logged = True
                _LOGGER.warning("Mantle Hub %s ist nicht erreichbar", self.client.url)
            self._set_available(False)
            wait = RETRY_SECONDS[min(attempt, len(RETRY_SECONDS) - 1)]
            attempt += 1
            await asyncio.sleep(wait)

    @callback
    def _handle(self, frame: dict[str, Any]) -> None:
        if frame.get("error") == "forbidden" and str(frame.get("topic", "")).startswith("events:"):
            if not self._warned_events:
                self._warned_events = True
                _LOGGER.warning(
                    "Mantle Hub: Hub-Events gibt es nur mit dem Token eines Admin-Kontos; Zustände und Aktionen gehen"
                )
            return
        topic = frame.get("topic")
        data = frame.get("data")
        if not isinstance(data, dict):
            return
        if topic == "states":
            if not self._was_connected:
                self._was_connected = True
                if self._outage_logged:
                    self._outage_logged = False
                    _LOGGER.info("Mantle Hub %s ist wieder erreichbar", self.client.url)
            self._set_available(True)
            state_id = str(data.get("id", ""))
            if state_id.startswith(STATE_PREFIX):
                self._on_device_state(state_id[len(STATE_PREFIX) :], data)
        elif isinstance(topic, str) and topic.startswith("events:"):
            # State changes arrive through `states` already; as events they would only fill the recorder.
            if data.get("type") == "hub.state_changed":
                return
            self.hass.bus.async_fire(
                EVENT, {"type": data.get("type"), "data": data.get("data"), "origin": data.get("origin")}
            )

    @callback
    def _on_device_state(self, device_id: str, state: dict[str, Any]) -> None:
        self.states[device_id] = state
        if device_id in self.devices:
            async_dispatcher_send(self.hass, SIGNAL_STATE.format(device_id))
        elif not self._refreshing and device_id not in self._unknown:
            self._refreshing = True
            self.entry.async_create_background_task(self.hass, self._refresh_devices(device_id), "mantle devices")

    async def _refresh_devices(self, wanted: str) -> None:
        """A TV the integration does not know yet: reload the list and add its entities."""
        try:
            fresh = {d["id"]: d for d in await self.client.devices()}
        except MantleError as err:
            _LOGGER.warning("Mantle Hub: Geräteliste nicht geladen: %s", err)
            return
        finally:
            self._refreshing = False
        if wanted not in fresh:
            self._unknown.add(wanted)
        for device_id, device in fresh.items():
            if device_id not in self.devices:
                self.devices[device_id] = device
                async_dispatcher_send(self.hass, SIGNAL_NEW_DEVICE.format(self.entry_id), device_id)

    @callback
    def _set_available(self, available: bool) -> None:
        if available == self.available:
            return
        self.available = available
        async_dispatcher_send(self.hass, SIGNAL_AVAILABLE.format(self.entry_id))

    async def command(self, device_id: str, name: str, args: dict[str, Any] | None = None) -> Any:
        """A device command through the hub action `devices.command` (openSpace, reload, snapshot)."""
        data: dict[str, Any] = {"deviceId": device_id, "name": name}
        if args is not None:
            data["args"] = args
        return await self.client.call_action("devices.command", data)
