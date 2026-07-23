"""The CoalPilot integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COAL_TYPE,
    ATTR_COUNT,
    ATTR_FIXED_TIME,
    ATTR_MODE,
    ATTR_VERDICT,
    DOMAIN,
    MODE_AUTO,
    MODE_FIXED,
    SERVICE_FEEDBACK,
    SERVICE_FINISH,
    SERVICE_SET_FIXED_TIME,
    SERVICE_START,
    SERVICE_STOP,
    VERDICT_LONGER,
    VERDICT_PERFECT,
    VERDICT_SHORTER,
)
from .coordinator import CoalPilotCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up shared services once."""
    hass.data.setdefault(DOMAIN, {})
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CoalPilot from a config entry."""
    coordinator = CoalPilotCoordinator(hass, entry)
    await coordinator.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: CoalPilotCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_unload()
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: CoalPilotCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator is not None:
        await coordinator.async_options_updated()


def _resolve(hass: HomeAssistant, call: ServiceCall) -> list[CoalPilotCoordinator]:
    """Resolve the target coordinator(s) from device/entity/entry targets."""
    coordinators: dict[str, CoalPilotCoordinator] = hass.data.get(DOMAIN, {})
    entry_ids = call.data.get("entry_id")
    if entry_ids:
        if isinstance(entry_ids, str):
            entry_ids = [entry_ids]
        return [coordinators[e] for e in entry_ids if e in coordinators]
    # Fall back: if only one oven exists, target it.
    if len(coordinators) == 1:
        return list(coordinators.values())
    return list(coordinators.values())


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_START):
        return

    async def _start(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_start(
                coal_type=call.data.get(ATTR_COAL_TYPE),
                count=call.data.get(ATTR_COUNT),
                mode=call.data.get(ATTR_MODE),
                fixed_time=call.data.get(ATTR_FIXED_TIME),
            )

    async def _stop(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_stop()

    async def _finish(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_finish()

    async def _feedback(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_feedback(call.data[ATTR_VERDICT])

    async def _set_fixed(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_set_fixed_time(call.data[ATTR_FIXED_TIME])

    entry_target = {vol.Optional("entry_id"): vol.Any(cv.string, [cv.string])}

    hass.services.async_register(
        DOMAIN,
        SERVICE_START,
        _start,
        schema=vol.Schema(
            {
                **entry_target,
                vol.Optional(ATTR_COAL_TYPE): cv.string,
                vol.Optional(ATTR_COUNT): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(ATTR_MODE): vol.In([MODE_AUTO, MODE_FIXED]),
                vol.Optional(ATTR_FIXED_TIME): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP, _stop, schema=vol.Schema(entry_target)
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FINISH, _finish, schema=vol.Schema(entry_target)
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FEEDBACK,
        _feedback,
        schema=vol.Schema(
            {
                **entry_target,
                vol.Required(ATTR_VERDICT): vol.In(
                    [VERDICT_SHORTER, VERDICT_PERFECT, VERDICT_LONGER]
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FIXED_TIME,
        _set_fixed,
        schema=vol.Schema(
            {
                **entry_target,
                vol.Required(ATTR_FIXED_TIME): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        ),
    )
