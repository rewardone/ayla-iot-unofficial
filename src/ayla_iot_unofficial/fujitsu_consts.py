from enum import IntEnum, unique

FGLAIR_APP_ID = "CJIOSP-id"
FGLAIR_APP_SECRET = "CJIOSP-Vb8MQL_lFiYQ7DKjN0eCFXznKZE"

OEM_MODEL = "oem_model"
PROP = "prop"
DISPLAY_TEMP = "display_temperature"
DEVICE_NAME = "device_name"
DEVICE_CAPABILITIES = "device_capabilities"
OPERATION_MODE = "operation_mode"
FAN_SPEED = "fan_speed"
ADJUST_TEMPERATURE = "adjust_temperature"
AF_HORIZONTAL_MOVE_STEP1 = "af_horizontal_move_step1"
AF_HORIZONTAL_SWING = "af_horizontal_swing"
AF_VERTICAL_MOVE_STEP1 = "af_vertical_move_step1"
AF_VERTICAL_SWING = "af_vertical_swing"

MIN_TEMP_HEAT = 16.0
MAX_TEMP_HEAT = 30.0

MIN_TEMP_COOL = 18.0
MAX_TEMP_COOL = 30.0

MIN_SENSED_TEMP = 4000
MAX_SENSED_TEMP = 9500
MIN_SENSED_CELSIUS = -10
MAX_SENSED_CELSIUS = 45


@unique
class ModelType(IntEnum):
    A = 0
    B = 1
    F = 2


DEVICE_MAP = {
    ModelType.A: [
        "AP-WA1E",
        "AP-WA2E",
        "AP-WA3E",
        "AP-WA4E",
        "AP-WA5E",
        "AP-WA6E",
        "AP-WC1E",
        "AP-WC2E",
        "AP-WC3E",
        "AP-WC4E",
        "AP-WD1E",
    ],
    ModelType.B: ["AP-WB1E", "AP-WB2E", "AP-WB3E", "AP-WB4E"],
    ModelType.F: ["AP-WF1E", "AP-WF2E", "AP-WF3E", "AP-WF4E"],
}

HORIZ_SWING_PARAM_MAP = {
    ModelType.B: AF_HORIZONTAL_MOVE_STEP1,
    ModelType.A: AF_HORIZONTAL_SWING,
    ModelType.F: AF_HORIZONTAL_SWING,
}

VERT_SWING_PARAM_MAP = {
    ModelType.B: AF_VERTICAL_MOVE_STEP1,
    ModelType.A: AF_VERTICAL_SWING,
    ModelType.F: AF_VERTICAL_SWING,
}

SWING_VAL_MAP = {
    ModelType.B: {True: 3, False: 0},
    ModelType.A: {True: 1, False: 0},
    ModelType.F: {True: 1, False: 0},
}


@unique
class FanSpeed(IntEnum):
    QUIET = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    AUTO = 4


@unique
class OpMode(IntEnum):
    OFF = 0
    ON = 1
    AUTO = 2
    COOL = 3
    DRY = 4
    FAN = 5
    HEAT = 6


@unique
class SwingMode(IntEnum):
    OFF = 0
    SWING_VERTICAL = 1
    SWING_HORIZONTAL = 2
    SWING_BOTH = 3


@unique
class Capability(IntEnum):
    OP_COOL = 1
    OP_DRY = 1 << 1
    OP_FAN = 1 << 2
    OP_HEAT = 1 << 3
    OP_AUTO = 1 << 4
    OP_MIN_HEAT = 1 << 13

    FAN_QUIET = 1 << 9
    FAN_LOW = 1 << 8
    FAN_MEDIUM = 1 << 7
    FAN_HIGH = 1 << 6
    FAN_AUTO = 1 << 5

    POWERFUL_MODE = 1 << 16
    ECO_MODE = 1 << 12
    ENERGY_SWING_FAN = 1 << 14
    COIL_DRY = 1 << 18
    OUTDOOR_LOW_NOISE = 1 << 17
    SWING_VERTICAL = 1 << 10
    SWING_HORIZONTAL = 1 << 11
