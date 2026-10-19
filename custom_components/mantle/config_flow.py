"""Set up a Mantle hub: URL and a long-lived token (profile → Zugangstoken); zeroconf fills the URL in."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import MantleAuthError, MantleClient, MantleError, normalize_url
from .const import CONF_TOKEN, CONF_URL, DOMAIN

TOKEN_FIELD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class MantleConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._url = ""

    async def _check(self, url: str, token: str) -> tuple[str | None, str]:
        """Returns (error key or None, normalized URL)."""
        try:
            normalized = normalize_url(url)
        except ValueError:
            return "invalid_url", url
        try:
            await MantleClient(async_get_clientsession(self.hass), normalized, token).me()
        except MantleAuthError:
            return "invalid_auth", normalized
        except MantleError:
            return "cannot_connect", normalized
        return None, normalized

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error, url = await self._check(user_input[CONF_URL], user_input[CONF_TOKEN])
            if error is None:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Mantle", data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN]})
            errors["base"] = error
            self._url = user_input[CONF_URL]
        schema = vol.Schema({vol.Required(CONF_URL, default=self._url): str, vol.Required(CONF_TOKEN): TOKEN_FIELD})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """The hub announces itself as `_mantle._tcp` with its public URL in TXT `url`."""
        url = str(discovery_info.properties.get("url") or f"http://{discovery_info.host}:{discovery_info.port}")
        try:
            url = normalize_url(url)
        except ValueError:
            return self.async_abort(reason="invalid_url")
        await self.async_set_unique_id(url)
        self._abort_if_unique_id_configured()
        self._url = url
        self.context["title_placeholders"] = {"url": url}
        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The hub rejected the token: ask for a new one."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error, _ = await self._check(entry.data[CONF_URL], user_input[CONF_TOKEN])
            if error is None:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]})
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_FIELD}), errors=errors
        )
