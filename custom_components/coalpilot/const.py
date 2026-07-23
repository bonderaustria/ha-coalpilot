"""Constants for the CoalPilot integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "coalpilot"

# Config entry data / options keys
CONF_NAME: Final = "name"
CONF_OVEN_ENTITY: Final = "oven_entity"
CONF_NOTIFY_SERVICE: Final = "notify_service"
CONF_NOTIFY_TITLE: Final = "notify_title"
CONF_NOTIFY_MESSAGE: Final = "notify_message"
CONF_COAL_TYPES: Final = "coal_types"
CONF_DEFAULT_TIME: Final = "default_time"
CONF_CANCEL_ASKS_FEEDBACK: Final = "cancel_asks_feedback"

# Coal type fields
COAL_ID: Final = "id"
COAL_NAME: Final = "name"
COAL_SIZE: Final = "size_mm"
COAL_SHAPE: Final = "shape"
COAL_DEFAULT_COUNT: Final = "default_count"
COAL_START_TIME: Final = "start_time"  # seconds, user-provided baseline
COAL_LEARNED_TIME: Final = "learned_time"  # seconds, learned
COAL_IS_DEFAULT: Final = "is_default"
COAL_SESSIONS: Final = "sessions"  # completed session count for this coal

COAL_SHAPES: Final = ["cube", "flat", "natural"]

# Phases
PHASE_IDLE: Final = "idle"
PHASE_RUNNING: Final = "running"
PHASE_FEEDBACK: Final = "feedback"

# Modes
MODE_AUTO: Final = "auto"
MODE_FIXED: Final = "fixed"

# Feedback verdicts
VERDICT_SHORTER: Final = "shorter"
VERDICT_PERFECT: Final = "perfect"
VERDICT_LONGER: Final = "longer"

# Learning parameters
ADJUST_STEP: Final = 30  # seconds per feedback nudge
MIN_TIME: Final = 60  # seconds, hard floor
MAX_TIME: Final = 30 * 60  # seconds, hard cap
SMOOTHING_ALPHA: Final = 0.4  # EMA weight for the newest data point
DEFAULT_START_TIME: Final = 14 * 60  # seconds, first-run default

# Storage
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = "coalpilot.{entry_id}"
HISTORY_MAX: Final = 100  # keep a rich history; card only shows the last 5

# Services
SERVICE_START: Final = "start"
SERVICE_STOP: Final = "stop"
SERVICE_FINISH: Final = "finish"
SERVICE_FEEDBACK: Final = "feedback"
SERVICE_SET_FIXED_TIME: Final = "set_fixed_time"
SERVICE_RESET_LEARNING: Final = "reset_learning"
SERVICE_TEST_NOTIFY: Final = "test_notify"

ATTR_COAL_TYPE: Final = "coal_type"
ATTR_COUNT: Final = "count"
ATTR_MODE: Final = "mode"
ATTR_FIXED_TIME: Final = "fixed_time"
ATTR_VERDICT: Final = "verdict"

# Dispatcher signal
SIGNAL_UPDATE: Final = "coalpilot_update_{entry_id}"
