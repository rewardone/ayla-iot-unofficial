from typing import Dict, List, TYPE_CHECKING
from enum import IntEnum, unique

from .device import Device

if TYPE_CHECKING:
    from .ayla_iot_unofficial import AylaApi


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

SUPPORTED_PROPS_MAP = {
    ModelType.A: [
        "operation_mode",
        "fan_speed",
        "adjust_temperature",
        "af_vertical_direction",
        "af_vertical_swing",
        "af_horizontal_direction",
        "af_horizontal_swing",
        "outdoor_low_noise",
        "indoor_fan_control",
        "human_det_auto_save",
        "min_heat",
        "powerful_mode",
        "coil_dry_mode",
        "economy_mode",
        "master_timer_on_off_1",
        "master_timer_on_off_2",
        "error_code",
        "demand_control",
        "filter_sign_reset_display",
        "op_status",
        "device_name",
        "building_name",
        "wifi_led_enable",
        "service_contact_name",
        "service_contact_phone",
        "service_contact_email",
        "af_horizontal_num_dir",
        "af_vertical_num_dir",
        "device_capabilities",
        "display_temperature",
        "get_prop",
        "human_det",
        "refresh",
    ],
    ModelType.B: [
        "operation_mode",
        "fan_speed",
        "adjust_temperature",
        "af_vertical_move_step1",
        "af_horizontal_move_step1",
        "economy_mode",
        "master_timer_on_off_1",
        "master_timer_on_off_2",
        "error_code",
        "demand_control",
        "filter_sign_reset_display",
        "op_status",
        "device_name",
        "building_name",
        "wifi_led_enable",
        "service_contact_name",
        "service_contact_phone",
        "service_contact_email",
        "device_capabilities",
        "refresh",
    ],
    ModelType.F: [
        "operation_mode",
        "fan_speed",
        "adjust_temperature",
        "af_vertical_direction",
        "af_vertical_swing",
        "af_horizontal_direction",
        "af_horizontal_swing",
        "outdoor_low_noise",
        "indoor_fan_control",
        "human_det_auto_save",
        "min_heat",
        "powerful_mode",
        "coil_dry_mode",
        "economy_mode",
        "master_timer_on_off_1",
        "master_timer_on_off_2",
        "error_code",
        "demand_control",
        "monitor1",
        "op_status",
        "device_name",
        "building_name",
        "wifi_led_enable",
        "service_contact_name",
        "service_contact_phone",
        "service_contact_email",
        "af_horizontal_num_dir",
        "af_vertical_num_dir",
        "device_capabilities",
        "display_temperature",
        "filter_sign_reset",
        "get_prop",
        "human_det",
        "refresh",
    ],
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


class FujitsuHVAC(Device):
    @staticmethod
    def supports(device: Dict) -> bool:
        if "oem_model" not in device:
            return False

        if device["oem_model"] in [
            model for models in DEVICE_MAP.values() for model in models
        ]:
            return True

        return False

    def __init__(self, ayla_api: "AylaApi", device_dct: Dict, europe: bool = False):
        super().__init__(ayla_api, device_dct, europe)
        if "oem_model" not in device_dct:
            raise Exception("This device is not supported by FujitsuHVAC.")

        self.model = None
        for modeltype, devices in DEVICE_MAP.items():
            if device_dct["oem_model"] in devices:
                self.model = modeltype

        if not self.model:
            raise Exception("This device is not supported by FujitsuHVAC.")

    def device_attr(self, name: str) -> any:
        if name not in SUPPORTED_PROPS_MAP[self.model]:
            raise AttributeError

        try:
            return self.property_values[name]
        except KeyError:
            raise AttributeError

    def poll_while(self):
        count = 0
        while count < 10:
            self.update(["prop"])
            print(self.properties_full["prop"])
            if self.properties_full["prop"]["datapoint"]["echo"] or self.properties_full["prop"]["datapoint"]["value"] != True:
                return
            count += 1
    
    def refresh_sensed_temp(self):
        end_point = self.set_property_endpoint('get_prop')
        data = {'datapoint': {'value': 1}}
        resp = self.ayla_api.self_request('post', end_point, json=data)
        self.poll_while()
        return self.properties_full["get_prop"]
        
    @property
    def capabilities(self) -> Dict[Capability, bool]:
        caps = self.device_attr("device_capabilities")
        ret = {}
        for c in Capability:
            if caps & c == c:
                ret[c] = True
            else:
                ret[c] = False

        return ret

    def _has_capability(self, capability: Capability) -> bool:
        try:
            return self.capabilities[capability]
        except KeyError:
            return False

    @property 
    def supported_op_modes(self) -> List[OpMode]:
        modes = [mode for mode in OpMode if self._has_capability(Capability[f"OP_{mode.name}"])]
        modes.append(OpMode.OFF)
        modes.append(OpMode.ON)
        return modes
    
    @property
    def op_mode(self) -> OpMode:
        return OpMode(self.device_attr("operation_mode"))

    @op_mode.setter
    def op_mode(self, val: OpMode):
        self.set_property_value("opetation_mode", val)

#    @property
#    def op_status(self) -> str:
#        return OpStatus(self.device_attr("op_status")).name

    @property
    def supported_fan_speeds(self) -> List[FanSpeed]:
        return [speed for speed in FanSpeed if self._has_capability(Capability[f"FAN_{speed.name}"])]
        
    @property
    def fan_speed(self) -> FanSpeed:
        return FanSpeed(self.device_attr("fan_speed"))

    @fan_speed.setter
    def fan_speed(self, val: FanSpeed):
        self.set_property_value("fan_speed", val)

    def _convert_sensed_temp_to_celsius(self, value: int) -> float:
        source_span = 9500 - 4000
        celsius_span = 45 - (-10)
        
        value_scaled = float(value - 4000) / float(source_span)
        
        return -10 + (value_scaled * celsius_span)

    @property
    def sensed_temp(self) -> float:
        return round(self._convert_sensed_temp_to_celsius(int(self.device_attr("display_temperature")))*2)/2

    @property
    def set_temp(self) -> float:
        return float(self.device_attr("adjust_temperature"))/10.0

    @set_temp.setter
    def set_temp(self, val: float):
        self.set_property_value("adjust_temperature", int(val*10.0))

    @property
    def supported_swing_modes(self) -> List[SwingMode]:
        modes = [mode for mode in SwingMode if self._has_capability(Capability[mode])]
        if SwingMode.SWING_HORIZONTAL in modes and SwingMode.SWING_VERTICAL in modes:
            modes.append(SwingMode.SWING_BOTH)
        
        return modes

    @property
    def swing_mode(self) -> SwingMode:
        if self.horizontal_swing and self.vertical_swing:
            return SwingMode.SWING_BOTH
        elif self.horizontal_swing:
            return SwingMode.SWING_HORIZONTAL
        elif self.vertical_swing:
            return SwingMode.SWING_VERTICAL
        else:
            return SwingMode.OFF

    @swing_mode.setter
    def swing_mode(self, val: SwingMode):
        if val == SwingMode.SWING_BOTH:
            self.horizontal_swing = True
            self.vertical_swing = True
        elif val == SwingMode.SWING_HORIZONTAL:
            self.horizontal_swing = True
            self.vertical_swing = False
        elif val == SwingMode.SWING_VERTICAL:
            self.vertical_swing = True
            self.horizontal_swing = False
        elif val == SwingMode.OFF:
            self.vertical_swing = False
            self.horizontal_swing = False

    @property
    def horizontal_swing(self) -> bool:
        if not self._has_capability(Capability.SWING_HORIZONTAL):
            raise Exception("Device does not support horizontal swing")
        
        if self.model == ModelType.B:
            return self.property_values["af_horizontal_move_step1"] == 3
        
        return self.property_values["af_horizontal_swing"] == 1
    
    @horizontal_swing.setter
    def horizontal_swing(self, val: bool):
        if not self._has_capability(Capability.SWING_HORIZONTAL):
            raise Exception("Device does not support horizontal swing")

        if self.model == ModelType.B:
            self.set_property_value("af_horizontal_move_step1", 3 if val else 0)
        
        self.set_property_value("af_horizontal_swing", 1 if val else 0)
        

    @property
    def vertical_swing(self) -> bool:
        if not self._has_capability(Capability.SWING_VERTICAL):
            raise Exception("Device does not support vertical swing")

        if self.model == ModelType.B:
            return self.property_values["af_vertical_move_step1"] == 3
        
        return self.property_values["af_vertical_swing"] == 1
    
    @horizontal_swing.setter
    def horizontal_swing(self, val: bool):
        if not self._has_capability(Capability.SWING_VERTICAL):
            raise Exception("Device does not support vertical swing")

        if self.model == ModelType.B:
            self.set_property_value("af_horizontal_move_step1", 3 if val else 0)
        
        self.set_property_value("af_horizontal_swing", 1 if val else 0)