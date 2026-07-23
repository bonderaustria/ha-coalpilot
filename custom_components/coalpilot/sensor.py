"""Sensors for CoalPilot: live state + long-term statistics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATE
from .coordinator import CoalPilotCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CoalPilotCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        CoalPilotHubSensor(coordinator),
        CoalPilotRemainingSensor(coordinator),
        CoalPilotLearnedSensor(coordinator),
    ]
    entities.extend(CoalPilotStatSensor(coordinator, desc) for desc in STAT_SENSORS)
    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class StatDesc:
    key: str
    name: str
    icon: str
    value: Callable[[CoalPilotCoordinator], Any]
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING


STAT_SENSORS: tuple[StatDesc, ...] = (
    StatDesc(
        key="sessions_total",
        name="Sessions total",
        icon="mdi:counter",
        value=lambda c: c.stats_sessions_total,
        unit="Sessions",
    ),
    StatDesc(
        key="runtime_total",
        name="Oven runtime total",
        icon="mdi:timer-sand",
        value=lambda c: round(c.stats_runtime_total / 3600, 3),
        unit=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    StatDesc(
        key="avg_burn",
        name="Average burn time",
        icon="mdi:chart-bell-curve",
        value=lambda c: (
            round(c.stats_runtime_total / c.stats_sessions_total / 60, 1)
            if c.stats_sessions_total
            else 0
        ),
        unit=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


class _BaseEntity(SensorEntity):
    """Common wiring: device info + live updates via dispatcher."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: CoalPilotCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="CoalPilot",
            model="Shisha Oven",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(entry_id=self.coordinator.entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class CoalPilotHubSensor(_BaseEntity):
    """Primary sensor the Lovelace card reads (phase + full snapshot)."""

    _attr_icon = "mdi:hookah"
    _attr_translation_key = "state"

    def __init__(self, coordinator: CoalPilotCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_state"

    @property
    def native_value(self) -> str:
        return self.coordinator.phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.as_dict()


class CoalPilotRemainingSensor(_BaseEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "remaining"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: CoalPilotCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_remaining"

    @property
    def native_value(self) -> int:
        return self.coordinator.remaining


class CoalPilotLearnedSensor(_BaseEntity):
    _attr_icon = "mdi:brain"
    _attr_translation_key = "learned"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoalPilotCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_learned"

    @property
    def native_value(self) -> int:
        return self.coordinator.learned_for(self.coordinator.selected_coal)


class CoalPilotStatSensor(_BaseEntity):
    """Long-term statistics sensor (HA recorder friendly)."""

    def __init__(self, coordinator: CoalPilotCoordinator, desc: StatDesc) -> None:
        super().__init__(coordinator)
        self.entity_description = None
        self._desc = desc
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{desc.key}"
        self._attr_translation_key = desc.key
        self._attr_icon = desc.icon
        self._attr_native_unit_of_measurement = desc.unit
        self._attr_device_class = desc.device_class
        self._attr_state_class = desc.state_class

    @property
    def native_value(self) -> Any:
        return self._desc.value(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._desc.key == "sessions_total":
            return {
                "per_coal": {
                    c.get("name", cid): self.coordinator.sessions.get(cid, 0)
                    for cid, c in (
                        (c["id"], c) for c in self.coordinator.coal_types
                    )
                }
            }
        return None
