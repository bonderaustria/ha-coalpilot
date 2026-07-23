"""State, timer and learning logic for CoalPilot."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    ADJUST_STEP,
    COAL_DEFAULT_COUNT,
    COAL_ID,
    COAL_IS_DEFAULT,
    COAL_LEARNED_TIME,
    COAL_NAME,
    COAL_SESSIONS,
    COAL_SHAPE,
    COAL_SIZE,
    COAL_START_TIME,
    CONF_CANCEL_ASKS_FEEDBACK,
    CONF_COAL_TYPES,
    CONF_DEFAULT_TIME,
    CONF_NOTIFY_MESSAGE,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_TITLE,
    CONF_OVEN_ENTITY,
    DEFAULT_START_TIME,
    HISTORY_MAX,
    MAX_TIME,
    MIN_TIME,
    MODE_AUTO,
    MODE_FIXED,
    PHASE_FEEDBACK,
    PHASE_IDLE,
    PHASE_RUNNING,
    SIGNAL_UPDATE,
    SMOOTHING_ALPHA,
    STORAGE_KEY,
    STORAGE_VERSION,
    VERDICT_LONGER,
    VERDICT_PERFECT,
    VERDICT_SHORTER,
)

_LOGGER = logging.getLogger(__name__)

VERDICT_ICON = {
    VERDICT_SHORTER: "🥶",
    VERDICT_PERFECT: "🔥",
    VERDICT_LONGER: "🥵",
}


def _clamp(value: float) -> int:
    """Clamp a time in seconds into the allowed range."""
    return int(max(MIN_TIME, min(MAX_TIME, round(value))))


class CoalPilotCoordinator:
    """Holds the runtime state of one oven and persists learned data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(
            hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id)
        )
        self._unsub_tick = None

        # Persisted state
        self.learned: dict[str, int] = {}  # coal_id -> learned seconds
        self.sessions: dict[str, int] = {}  # coal_id -> completed sessions
        self.history: list[dict[str, Any]] = []
        self.stats_sessions_total: int = 0
        self.stats_runtime_total: int = 0  # seconds the oven has burned
        self.last_session: str | None = None

        # Volatile runtime state
        self.mode: str = MODE_AUTO
        self.phase: str = PHASE_IDLE
        self.remaining: int = DEFAULT_START_TIME
        self.total: int = DEFAULT_START_TIME
        self.fixed_time: int = DEFAULT_START_TIME
        self.selected_coal: str | None = None
        self.current_count: int = 1
        self._session_coal: str | None = None
        self._session_count: int = 1
        self._session_total: int = 0

    # ---- lifecycle -------------------------------------------------------

    async def async_load(self) -> None:
        """Load persisted state and seed defaults."""
        data = await self._store.async_load() or {}
        self.learned = {k: int(v) for k, v in data.get("learned", {}).items()}
        self.sessions = {k: int(v) for k, v in data.get("sessions", {}).items()}
        self.history = data.get("history", [])
        self.stats_sessions_total = int(data.get("stats_sessions_total", 0))
        self.stats_runtime_total = int(data.get("stats_runtime_total", 0))
        self.last_session = data.get("last_session")
        self.fixed_time = int(
            data.get("fixed_time", self._configured_default_time())
        )
        self.mode = data.get("mode", MODE_AUTO)

        default = self._default_coal()
        self.selected_coal = default[COAL_ID] if default else None
        if self.selected_coal:
            self.current_count = int(default.get(COAL_DEFAULT_COUNT, 1))
        self._sync_base_time()

    async def async_unload(self) -> None:
        self._cancel_tick()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "learned": self.learned,
                "sessions": self.sessions,
                "history": self.history,
                "stats_sessions_total": self.stats_sessions_total,
                "stats_runtime_total": self.stats_runtime_total,
                "last_session": self.last_session,
                "fixed_time": self.fixed_time,
                "mode": self.mode,
            }
        )

    # ---- config helpers --------------------------------------------------

    @property
    def options(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    def _configured_default_time(self) -> int:
        return int(self.options.get(CONF_DEFAULT_TIME, DEFAULT_START_TIME))

    @property
    def coal_types(self) -> list[dict[str, Any]]:
        return list(self.options.get(CONF_COAL_TYPES, []))

    def _default_coal(self) -> dict[str, Any] | None:
        coals = self.coal_types
        if not coals:
            return None
        for coal in coals:
            if coal.get(COAL_IS_DEFAULT):
                return coal
        return coals[0]

    def get_coal(self, coal_id: str | None) -> dict[str, Any] | None:
        if coal_id is None:
            return None
        for coal in self.coal_types:
            if coal[COAL_ID] == coal_id:
                return coal
        return None

    def learned_for(self, coal_id: str | None) -> int:
        """Return the learned time for a coal, falling back to its baseline."""
        if coal_id and coal_id in self.learned:
            return _clamp(self.learned[coal_id])
        coal = self.get_coal(coal_id)
        if coal:
            return _clamp(int(coal.get(COAL_START_TIME, self._configured_default_time())))
        return _clamp(self._configured_default_time())

    def _sync_base_time(self) -> None:
        if self.phase != PHASE_IDLE:
            return
        base = (
            self.fixed_time
            if self.mode == MODE_FIXED
            else self.learned_for(self.selected_coal)
        )
        self.total = base
        self.remaining = base

    # ---- notify state changes -------------------------------------------

    @callback
    def async_notify(self) -> None:
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATE.format(entry_id=self.entry.entry_id)
        )

    async def async_options_updated(self) -> None:
        """Re-sync when coal types / options change."""
        if self.selected_coal is None or self.get_coal(self.selected_coal) is None:
            default = self._default_coal()
            self.selected_coal = default[COAL_ID] if default else None
        self._sync_base_time()
        self.async_notify()

    # ---- oven switching --------------------------------------------------

    async def _set_oven(self, on: bool) -> None:
        entity_id = self.options.get(CONF_OVEN_ENTITY)
        if not entity_id:
            return
        domain = entity_id.split(".")[0]
        service_domain = domain if domain in ("switch", "input_boolean", "light") else "homeassistant"
        await self.hass.services.async_call(
            service_domain,
            "turn_on" if on else "turn_off",
            {"entity_id": entity_id},
            blocking=False,
        )

    # ---- timer -----------------------------------------------------------

    def _cancel_tick(self) -> None:
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None

    @callback
    def _tick(self, _now) -> None:
        if self.phase != PHASE_RUNNING:
            self._cancel_tick()
            return
        self.remaining = max(0, self.remaining - 1)
        if self.remaining <= 0:
            self.hass.async_create_task(self._async_expire())
        else:
            self.async_notify()

    async def _async_expire(self) -> None:
        self._cancel_tick()
        self.phase = PHASE_FEEDBACK
        await self._set_oven(False)
        await self._send_notify()
        self.async_notify()

    # ---- public actions --------------------------------------------------

    async def async_set_mode(self, mode: str) -> None:
        if self.phase != PHASE_IDLE or mode not in (MODE_AUTO, MODE_FIXED):
            return
        self.mode = mode
        self._sync_base_time()
        await self._async_save()
        self.async_notify()

    async def async_select_coal(self, coal_id: str, count: int | None = None) -> None:
        coal = self.get_coal(coal_id)
        if coal is None or self.phase != PHASE_IDLE:
            return
        self.selected_coal = coal_id
        self.current_count = count or int(coal.get(COAL_DEFAULT_COUNT, 1))
        self._sync_base_time()
        self.async_notify()

    async def async_set_fixed_time(self, seconds: int) -> None:
        self.fixed_time = _clamp(seconds)
        if self.mode == MODE_FIXED:
            self._sync_base_time()
        await self._async_save()
        self.async_notify()

    async def async_start(
        self,
        coal_type: str | None = None,
        count: int | None = None,
        mode: str | None = None,
        fixed_time: int | None = None,
    ) -> None:
        if self.phase == PHASE_RUNNING:
            return
        if mode in (MODE_AUTO, MODE_FIXED):
            self.mode = mode
        if fixed_time is not None:
            self.fixed_time = _clamp(fixed_time)
        if coal_type is not None and self.get_coal(coal_type) is not None:
            self.selected_coal = coal_type
        coal = self.get_coal(self.selected_coal)
        self.current_count = count or (
            int(coal.get(COAL_DEFAULT_COUNT, 1)) if coal else 1
        )

        base = (
            self.fixed_time
            if self.mode == MODE_FIXED
            else self.learned_for(self.selected_coal)
        )
        self.total = base
        self.remaining = base
        self.phase = PHASE_RUNNING
        self._session_coal = self.selected_coal
        self._session_count = self.current_count
        self._session_total = base

        await self._set_oven(True)
        self._cancel_tick()
        self._unsub_tick = async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=1)
        )
        await self._async_save()
        self.async_notify()

    async def async_finish(self) -> None:
        """Manual early stop -> ask for feedback (oven off)."""
        if self.phase != PHASE_RUNNING:
            return
        self._cancel_tick()
        # elapsed time is what actually burned
        self._session_total = self.total - self.remaining
        if not self.options.get(CONF_CANCEL_ASKS_FEEDBACK, True):
            await self._set_oven(False)
            await self._async_abort_to_idle()
            return
        self.phase = PHASE_FEEDBACK
        await self._set_oven(False)
        self.async_notify()

    async def async_stop(self) -> None:
        """Hard stop without feedback (oven off, discard session)."""
        self._cancel_tick()
        await self._set_oven(False)
        await self._async_abort_to_idle()

    async def _async_abort_to_idle(self) -> None:
        self.phase = PHASE_IDLE
        self._sync_base_time()
        self.async_notify()

    async def async_feedback(self, verdict: str) -> None:
        if self.phase != PHASE_FEEDBACK:
            return
        coal_id = self._session_coal
        burned = max(0, int(self._session_total))

        # --- learning (auto mode only, per coal type) ---
        if self.mode == MODE_AUTO and coal_id is not None:
            current = self.learned_for(coal_id)
            if verdict == VERDICT_PERFECT:
                target = burned or current
            elif verdict == VERDICT_SHORTER:
                target = burned - ADJUST_STEP
            elif verdict == VERDICT_LONGER:
                target = burned + ADJUST_STEP
            else:
                target = current
            # exponential moving average -> smooth, less jumpy
            new_learned = _clamp(
                current * (1 - SMOOTHING_ALPHA) + target * SMOOTHING_ALPHA
            )
            self.learned[coal_id] = new_learned

        # --- statistics ---
        self.stats_sessions_total += 1
        self.stats_runtime_total += burned
        if coal_id is not None:
            self.sessions[coal_id] = self.sessions.get(coal_id, 0) + 1

        # --- history ---
        coal = self.get_coal(coal_id)
        coal_label = self._coal_label(coal, self._session_count)
        entry = {
            "id": uuid.uuid4().hex[:8],
            "ts": int(time.time()),
            "icon": VERDICT_ICON.get(verdict, "🔥"),
            "time": _fmt(burned),
            "seconds": burned,
            "coal": coal_label,
            "coal_id": coal_id,
            "verdict": verdict,
        }
        self.history.insert(0, entry)
        self.history = self.history[:HISTORY_MAX]
        self.last_session = f"{_fmt(burned)} · {coal_label}"

        self.phase = PHASE_IDLE
        self._sync_base_time()
        await self._async_save()
        self.async_notify()

    # ---- notify ----------------------------------------------------------

    def _coal_label(self, coal: dict[str, Any] | None, count: int) -> str:
        if not coal:
            return "—"
        parts = [coal.get(COAL_NAME, "Kohle")]
        size = coal.get(COAL_SIZE)
        if size:
            parts.append(f"{size}mm")
        label = " ".join(parts)
        if count and count > 1:
            label += f" · {count}"
        return label

    async def _send_notify(self) -> None:
        service = self.options.get(CONF_NOTIFY_SERVICE)
        if not service:
            return
        coal = self.get_coal(self._session_coal)
        oven = self.options.get(CONF_OVEN_ENTITY, "")
        placeholders = {
            "{kohle}": self._coal_label(coal, self._session_count),
            "{coal}": self._coal_label(coal, self._session_count),
            "{dauer}": _fmt(self.total),
            "{duration}": _fmt(self.total),
            "{ofen}": self.entry.title,
            "{oven}": self.entry.title,
            "{uhrzeit}": time.strftime("%H:%M"),
            "{time}": time.strftime("%H:%M"),
        }
        title = self.options.get(CONF_NOTIFY_TITLE) or "CoalPilot 🔥"
        message = (
            self.options.get(CONF_NOTIFY_MESSAGE)
            or "Deine {kohle} ist durch! ({dauer})"
        )
        for token, value in placeholders.items():
            title = title.replace(token, str(value))
            message = message.replace(token, str(value))

        # service may be "notify.mobile_app_x" or just "mobile_app_x"
        if "." in service:
            domain, svc = service.split(".", 1)
        else:
            domain, svc = "notify", service
        try:
            await self.hass.services.async_call(
                domain, svc, {"title": title, "message": message}, blocking=False
            )
        except Exception:  # noqa: BLE001 - notify is best-effort
            _LOGGER.warning("CoalPilot notify via %s failed", service, exc_info=True)

    # ---- snapshot for the card ------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        coal = self.get_coal(self.selected_coal)
        return {
            "entry_id": self.entry.entry_id,
            "mode": self.mode,
            "phase": self.phase,
            "remaining": self.remaining,
            "total": self.total,
            "fixed_time": self.fixed_time,
            "selected_coal": self.selected_coal,
            "current_count": self.current_count,
            "learned": self.learned_for(self.selected_coal),
            "last_session": self.last_session,
            "coal_types": [
                {
                    COAL_ID: c[COAL_ID],
                    COAL_NAME: c.get(COAL_NAME),
                    COAL_SIZE: c.get(COAL_SIZE),
                    COAL_SHAPE: c.get(COAL_SHAPE),
                    COAL_DEFAULT_COUNT: c.get(COAL_DEFAULT_COUNT, 1),
                    COAL_LEARNED_TIME: self.learned_for(c[COAL_ID]),
                    COAL_IS_DEFAULT: bool(c.get(COAL_IS_DEFAULT)),
                    COAL_SESSIONS: self.sessions.get(c[COAL_ID], 0),
                }
                for c in self.coal_types
            ],
            "history": self.history[:5],
            "stats_sessions_total": self.stats_sessions_total,
        }


def _fmt(seconds: int) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
