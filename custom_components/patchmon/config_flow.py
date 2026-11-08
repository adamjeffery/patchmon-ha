"""Config flow for PatchMon."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    PatchMonAuthError,
    PatchMonClient,
    PatchMonConnectionError,
    PatchMonError,
)
from .const import (
    CONF_TOKEN_KEY,
    CONF_TOKEN_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL_SECONDS,
)
from .coordinator import PatchMonConfigEntry

_LOGGER = logging.getLogger(__name__)

_SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_TOKEN_KEY): str,
        vol.Required(CONF_TOKEN_SECRET): _SECRET,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)
_REAUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_TOKEN_KEY): str, vol.Required(CONF_TOKEN_SECRET): _SECRET}
)


async def _async_test_credential(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> str | None:
    """Return an error key if the scoped API can't be read with these settings."""
    client = PatchMonClient(
        async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL]),
        data[CONF_URL],
        data[CONF_TOKEN_KEY],
        data[CONF_TOKEN_SECRET],
    )
    try:
        await client.async_get_hosts()
    except PatchMonAuthError:
        return "invalid_auth"
    except PatchMonConnectionError:
        return "cannot_connect"
    except PatchMonError:
        _LOGGER.exception("Unexpected PatchMon error")
        return "unknown"
    return None


class PatchMonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PatchMon."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the server and API credential."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].strip().rstrip("/")
            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()
            if error := await _async_test_credential(self.hass, user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title="PatchMon", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after the credential was rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API credential."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            if error := await _async_test_credential(self.hass, data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_REAUTH_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: PatchMonConfigEntry) -> PatchMonOptionsFlow:
        """Return the options flow."""
        return PatchMonOptionsFlow()


class PatchMonOptionsFlow(OptionsFlowWithReload):
    """Polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=interval): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_SECONDS)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
