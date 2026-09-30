"""Domain vocabulary shared by the API, the persistence layer and the event stream.

These enumerations mirror `firmware/robot/robot_logic.h`. Keeping them in one
place means the wire format has a single source of truth on both sides.
"""

from enum import Enum


class EventType(str, Enum):
    DEVICE_ONLINE = "DEVICE_ONLINE"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    VIBRATION_DETECTED = "VIBRATION_DETECTED"
    VIBRATION_CLEARED = "VIBRATION_CLEARED"
    IR_DETECTED = "IR_DETECTED"
    IR_CLEARED = "IR_CLEARED"
    DISTANCE_UPDATED = "DISTANCE_UPDATED"
    TARGET_ACTIVITY_DETECTED = "TARGET_ACTIVITY_DETECTED"
    TARGET_ACTIVITY_CLEARED = "TARGET_ACTIVITY_CLEARED"
    ROBOT_MOVING = "ROBOT_MOVING"
    ROBOT_STOPPED = "ROBOT_STOPPED"
    EMITTER_ACTIVATED = "EMITTER_ACTIVATED"
    EMITTER_DEACTIVATED = "EMITTER_DEACTIVATED"
    OBSTACLE_DETECTED = "OBSTACLE_DETECTED"
    OBSTACLE_CLEARED = "OBSTACLE_CLEARED"
    ERROR = "ERROR"
    HEARTBEAT = "HEARTBEAT"


class EventCategory(str, Enum):
    """Coarse grouping used by the dashboard event filters."""

    EMITTER = "EMITTER"
    SENSORS = "SENSORS"
    ROBOT = "ROBOT"
    SYSTEM = "SYSTEM"
    ERROR = "ERROR"


CATEGORY_BY_EVENT_TYPE: dict[EventType, EventCategory] = {
    EventType.EMITTER_ACTIVATED: EventCategory.EMITTER,
    EventType.EMITTER_DEACTIVATED: EventCategory.EMITTER,
    EventType.VIBRATION_DETECTED: EventCategory.SENSORS,
    EventType.VIBRATION_CLEARED: EventCategory.SENSORS,
    EventType.IR_DETECTED: EventCategory.SENSORS,
    EventType.IR_CLEARED: EventCategory.SENSORS,
    EventType.DISTANCE_UPDATED: EventCategory.SENSORS,
    EventType.TARGET_ACTIVITY_DETECTED: EventCategory.SENSORS,
    EventType.TARGET_ACTIVITY_CLEARED: EventCategory.SENSORS,
    EventType.OBSTACLE_DETECTED: EventCategory.SENSORS,
    EventType.OBSTACLE_CLEARED: EventCategory.SENSORS,
    EventType.ROBOT_MOVING: EventCategory.ROBOT,
    EventType.ROBOT_STOPPED: EventCategory.ROBOT,
    EventType.DEVICE_ONLINE: EventCategory.SYSTEM,
    EventType.DEVICE_OFFLINE: EventCategory.SYSTEM,
    EventType.HEARTBEAT: EventCategory.SYSTEM,
    EventType.ERROR: EventCategory.ERROR,
}


def category_for(event_type: EventType) -> EventCategory:
    return CATEGORY_BY_EVENT_TYPE.get(event_type, EventCategory.SYSTEM)


class RobotState(str, Enum):
    IDLE = "IDLE"
    TARGET_DETECTED = "TARGET_DETECTED"
    APPROACHING = "APPROACHING"
    OBSTACLE_AVOIDANCE = "OBSTACLE_AVOIDANCE"
    EMITTER_ACTIVE = "EMITTER_ACTIVE"
    MONITORING = "MONITORING"
    ERROR = "ERROR"


# Only these states mean the chassis is commanded to move. TARGET_DETECTED is a
# stationary confirmation state: the robot stands still while it decides.
MOVING_STATES: frozenset[RobotState] = frozenset(
    {RobotState.APPROACHING, RobotState.OBSTACLE_AVOIDANCE}
)


class DeviceState(str, Enum):
    """Connectivity as observed by the server, not asserted by the device."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class TelemetrySource(str, Enum):
    """Who decided that the event happened."""

    DEVICE = "DEVICE"
    SERVER = "SERVER"


def is_known_event_type(value: str) -> bool:
    try:
        EventType(value)
    except ValueError:
        return False
    return True
