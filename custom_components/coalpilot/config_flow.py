"""Config and options flow for CoalPilot."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    COAL_DEFAULT_COUNT,
    COAL_ID,
    COAL_IS_DEFAULT,
    COAL_NAME,
    COAL_SHAPE,
    COAL_SHAPES,
    COAL_SIZE,
    COAL_START_TIME,
    CONF_CANCEL_ASKS_FEEDBACK,
    CONF_COAL_TYPES,
    CONF_DEFAULT_TIME,
    CONF_NAME,
    CONF_NOTIFY_MESSAGE,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_TITLE,
    CONF_OVEN_ENTITY,
    DEFAULT_START_TIME,
    DOMAIN,
)


def _base_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, "Shisha Ofen")
            ): str,
            vol.Required(
                CONF_OVEN_ENTITY, default=defaults.get(CONF_OVEN_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["switch", "input_boolean", "light"]
                )
            ),
            vol.Required(
                CONF_DEFAULT_TIME,
                default=defaults.get(CONF_DEFAULT_TIME, DEFAULT_START_TIME) // 60,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=30, step=1, unit_of_measurement="min", mode="box"
                )
            ),
        }
    )


class CoalPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            data = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_OVEN_ENTITY: user_input[CONF_OVEN_ENTITY],
                CONF_DEFAULT_TIME: int(user_input[CONF_DEFAULT_TIME]) * 60,
                CONF_COAL_TYPES: [],
                CONF_CANCEL_ASKS_FEEDBACK: True,
            }
            return self.async_create_entry(title=user_input[CONF_NAME], data=data)

        return self.async_show_form(step_id="user", data_schema=_base_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return CoalPilotOptionsFlow(entry)


class CoalPilotOptionsFlow(OptionsFlow):
    """Manage coal types and notify settings."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        # working copy of options
        self._options: dict[str, Any] = {**entry.data, **entry.options}
        self._options.setdefault(CONF_COAL_TYPES, [])
        self._edit_id: str | None = None

    def _coals(self) -> list[dict[str, Any]]:
        return list(self._options.get(CONF_COAL_TYPES, []))

    async def _save(self) -> ConfigFlowResult:
        # Only persist option keys (name/oven stay in entry.data)
        opts = {
            CONF_COAL_TYPES: self._options[CONF_COAL_TYPES],
            CONF_DEFAULT_TIME: self._options.get(
                CONF_DEFAULT_TIME, DEFAULT_START_TIME
            ),
            CONF_NOTIFY_SERVICE: self._options.get(CONF_NOTIFY_SERVICE),
            CONF_NOTIFY_TITLE: self._options.get(CONF_NOTIFY_TITLE),
            CONF_NOTIFY_MESSAGE: self._options.get(CONF_NOTIFY_MESSAGE),
            CONF_CANCEL_ASKS_FEEDBACK: self._options.get(
                CONF_CANCEL_ASKS_FEEDBACK, True
            ),
        }
        return self.async_create_entry(title="", data=opts)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_coal", "manage_coal", "notify", "settings"],
        )

    # ---- add coal --------------------------------------------------------

    async def async_step_add_coal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            coal = {
                COAL_ID: uuid.uuid4().hex[:8],
                COAL_NAME: user_input[COAL_NAME],
                COAL_SIZE: int(user_input[COAL_SIZE]),
                COAL_SHAPE: user_input[COAL_SHAPE],
                COAL_DEFAULT_COUNT: int(user_input[COAL_DEFAULT_COUNT]),
                COAL_START_TIME: int(user_input[COAL_START_TIME]) * 60,
                COAL_IS_DEFAULT: user_input[COAL_IS_DEFAULT],
            }
            coals = self._coals()
            if coal[COAL_IS_DEFAULT]:
                for c in coals:
                    c[COAL_IS_DEFAULT] = False
            elif not coals:
                coal[COAL_IS_DEFAULT] = True
            coals.append(coal)
            self._options[CONF_COAL_TYPES] = coals
            return await self._save()

        return self.async_show_form(
            step_id="add_coal", data_schema=self._coal_schema()
        )

    def _coal_schema(self, coal: dict[str, Any] | None = None) -> vol.Schema:
        coal = coal or {}
        return vol.Schema(
            {
                vol.Required(COAL_NAME, default=coal.get(COAL_NAME, "")): str,
                vol.Required(
                    COAL_SIZE, default=coal.get(COAL_SIZE, 26)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10, max=40, step=1, unit_of_measurement="mm", mode="box"
                    )
                ),
                vol.Required(
                    COAL_SHAPE, default=coal.get(COAL_SHAPE, "cube")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=COAL_SHAPES,
                        translation_key="coal_shape",
                        mode="dropdown",
                    )
                ),
                vol.Required(
                    COAL_DEFAULT_COUNT, default=coal.get(COAL_DEFAULT_COUNT, 3)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=10, step=1, mode="box"
                    )
                ),
                vol.Required(
                    COAL_START_TIME,
                    default=coal.get(COAL_START_TIME, DEFAULT_START_TIME) // 60,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=30, step=1, unit_of_measurement="min", mode="box"
                    )
                ),
                vol.Required(
                    COAL_IS_DEFAULT, default=coal.get(COAL_IS_DEFAULT, False)
                ): bool,
            }
        )

    # ---- manage / edit / delete -----------------------------------------

    async def async_step_manage_coal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coals = self._coals()
        if not coals:
            return await self.async_step_add_coal()
        if user_input is not None:
            self._edit_id = user_input["coal"]
            return await self.async_step_edit_coal()

        options = [
            selector.SelectOptionDict(
                value=c[COAL_ID],
                label=f"{c.get(COAL_NAME)} · {c.get(COAL_SIZE)}mm"
                + (" ★" if c.get(COAL_IS_DEFAULT) else ""),
            )
            for c in coals
        ]
        return self.async_show_form(
            step_id="manage_coal",
            data_schema=vol.Schema(
                {
                    vol.Required("coal"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode="list"
                        )
                    )
                }
            ),
        )

    async def async_step_edit_coal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coals = self._coals()
        current = next((c for c in coals if c[COAL_ID] == self._edit_id), None)
        if current is None:
            return await self.async_step_init()

        if user_input is not None:
            if user_input.get("delete"):
                coals = [c for c in coals if c[COAL_ID] != self._edit_id]
                if coals and not any(c.get(COAL_IS_DEFAULT) for c in coals):
                    coals[0][COAL_IS_DEFAULT] = True
                self._options[CONF_COAL_TYPES] = coals
                return await self._save()

            current.update(
                {
                    COAL_NAME: user_input[COAL_NAME],
                    COAL_SIZE: int(user_input[COAL_SIZE]),
                    COAL_SHAPE: user_input[COAL_SHAPE],
                    COAL_DEFAULT_COUNT: int(user_input[COAL_DEFAULT_COUNT]),
                    COAL_START_TIME: int(user_input[COAL_START_TIME]) * 60,
                }
            )
            if user_input[COAL_IS_DEFAULT]:
                for c in coals:
                    c[COAL_IS_DEFAULT] = c[COAL_ID] == self._edit_id
            self._options[CONF_COAL_TYPES] = coals
            return await self._save()

        schema = self._coal_schema(current).extend(
            {vol.Optional("delete", default=False): bool}
        )
        return self.async_show_form(
            step_id="edit_coal",
            data_schema=schema,
            description_placeholders={"name": current.get(COAL_NAME, "")},
        )

    # ---- notify ----------------------------------------------------------

    async def async_step_notify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options[CONF_NOTIFY_SERVICE] = user_input.get(CONF_NOTIFY_SERVICE)
            self._options[CONF_NOTIFY_TITLE] = user_input.get(CONF_NOTIFY_TITLE)
            self._options[CONF_NOTIFY_MESSAGE] = user_input.get(CONF_NOTIFY_MESSAGE)
            return await self._save()

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_SERVICE,
                    description={
                        "suggested_value": self._options.get(CONF_NOTIFY_SERVICE)
                    },
                ): str,
                vol.Optional(
                    CONF_NOTIFY_TITLE,
                    description={
                        "suggested_value": self._options.get(
                            CONF_NOTIFY_TITLE, "CoalPilot 🔥"
                        )
                    },
                ): str,
                vol.Optional(
                    CONF_NOTIFY_MESSAGE,
                    description={
                        "suggested_value": self._options.get(
                            CONF_NOTIFY_MESSAGE,
                            "Deine {kohle} ist durch! ({dauer})",
                        )
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="notify", data_schema=schema)

    # ---- settings --------------------------------------------------------

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options[CONF_DEFAULT_TIME] = int(user_input[CONF_DEFAULT_TIME]) * 60
            self._options[CONF_CANCEL_ASKS_FEEDBACK] = user_input[
                CONF_CANCEL_ASKS_FEEDBACK
            ]
            return await self._save()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEFAULT_TIME,
                    default=self._options.get(CONF_DEFAULT_TIME, DEFAULT_START_TIME)
                    // 60,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=30, step=1, unit_of_measurement="min", mode="box"
                    )
                ),
                vol.Required(
                    CONF_CANCEL_ASKS_FEEDBACK,
                    default=self._options.get(CONF_CANCEL_ASKS_FEEDBACK, True),
                ): bool,
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)
