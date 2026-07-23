"""The CoalPilot integration."""

from __future__ import annotations

import logging
import os

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
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
    SERVICE_RESET_LEARNING,
    SERVICE_SET_FIXED_TIME,
    SERVICE_START,
    SERVICE_STOP,
    SERVICE_TEST_NOTIFY,
    VERDICT_LONGER,
    VERDICT_PERFECT,
    VERDICT_SHORTER,
)
from .coordinator import CoalPilotCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_FILENAME = "coalpilot-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_VERSION = "0.1.11"  # bump to bust the browser cache when the card changes


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the Lovelace card and make sure it loads before dashboards render."""
    flag = f"{DOMAIN}_card_registered"
    if hass.data.get(flag):
        return
    hass.data[flag] = True
    card_path = os.path.join(os.path.dirname(__file__), CARD_FILENAME)
    versioned_url = f"{CARD_URL}?v={CARD_VERSION}"

    # 1) Serve the file.
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, card_path, False)]
        )
    except RuntimeError:
        pass  # already registered (after a reload) – fine

    # 2) Load the card through EXACTLY ONE path at the current version:
    #    - storage-mode dashboards: a Lovelace resource. HA awaits resources
    #      before rendering cards, so the element is always defined in time
    #      (no "Custom element not found" race) — and it is kept in sync to the
    #      current version so no stale copy can linger.
    #    - YAML-mode dashboards (no resource store): fall back to a frontend
    #      module include.
    managed = await _async_ensure_lovelace_resource(hass, versioned_url)
    if not managed:
        try:
            add_extra_js_url(hass, versioned_url)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("CoalPilot: add_extra_js_url failed", exc_info=True)


async def _async_ensure_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """Create/update the card's Lovelace resource. Returns True if managed."""
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None:
            return False
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        base = url.split("?")[0]
        existing = None
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == base:
                existing = item
                break
        if existing is None:
            await resources.async_create_item({"res_type": "module", "url": url})
        elif existing.get("url") != url:
            # keep the version query current so no stale copy loads
            await resources.async_update_item(existing["id"], {"url": url})
        return True
    except Exception:  # noqa: BLE001 - YAML mode has no resource store
        _LOGGER.debug("CoalPilot: Lovelace resource handling skipped", exc_info=True)
        return False


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

    await _async_register_card(hass)
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

    async def _reset_learning(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_reset_learning(call.data.get(ATTR_COAL_TYPE))

    async def _test_notify(call: ServiceCall) -> None:
        for coord in _resolve(hass, call):
            await coord.async_test_notify()

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_LEARNING,
        _reset_learning,
        schema=vol.Schema(
            {**entry_target, vol.Optional(ATTR_COAL_TYPE): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_NOTIFY,
        _test_notify,
        schema=vol.Schema(entry_target),
    )
