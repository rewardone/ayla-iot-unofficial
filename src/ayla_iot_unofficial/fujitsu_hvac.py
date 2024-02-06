from time import sleep as syncsleep
from asyncio import sleep
from typing import Any, Dict, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
from enum import Enum

from .device import Device, PropertyName, PropertyValue, AylaReadOnlyPropertyError
from .fujitsu_consts import (
    OEM_MODEL,
    PROP,
    DISPLAY_TEMP,
    DEVICE_NAME,
    DEVICE_CAPABILITIES,
    OPERATION_MODE,
    ADJUST_TEMPERATURE,
    FAN_SPEED,
    HORIZ_SWING_PARAM_MAP,
    VERT_SWING_PARAM_MAP,
    SWING_VAL_MAP,
    MIN_SENSED_TEMP,
    MAX_SENSED_TEMP,
    MIN_SENSED_CELSIUS,
    MAX_SENSED_CELSIUS,
    MIN_TEMP_HEAT,
    MAX_TEMP_HEAT,
    MIN_TEMP_COOL,
    MAX_TEMP_COOL,
    DEVICE_MAP,
    Capability,
    OpMode,
    SwingMode,
    FanSpeed,
)

if TYPE_CHECKING:
    from .ayla_iot_unofficial import AylaApi

class DeviceNotSupportedError(Exception):
    pass

class SettingNotSupportedError(Exception):
    pass


def _convert_sensed_temp_to_celsius(value: int) -> float:
    source_span = MAX_SENSED_TEMP - MIN_SENSED_TEMP
    celsius_span = MAX_SENSED_CELSIUS - MIN_SENSED_CELSIUS 

    value_scaled = float(value - MIN_SENSED_TEMP) / float(source_span)

    return MIN_SENSED_CELSIUS + (value_scaled * celsius_span)

class FujitsuHVAC(Device):
    @staticmethod
    def supports(device: Dict) -> bool:
        if OEM_MODEL not in device:
            return False

        if device[OEM_MODEL] in [
            model for models in DEVICE_MAP.values() for model in models
        ]:
            return True

        return False

    def __init__(self, ayla_api: "AylaApi", device_dct: Dict, europe: bool = False):
        super().__init__(ayla_api, device_dct, europe)
        if OEM_MODEL not in device_dct:
            raise DeviceNotSupportedError("This device is not supported by FujitsuHVAC.")

        self.model = None
        for modeltype, devices in DEVICE_MAP.items():
            if device_dct[OEM_MODEL] in devices:
                self.model = modeltype

        if not self.model:
            raise DeviceNotSupportedError("This device is not supported by FujitsuHVAC.")

    def set_property_value(self, property_name: PropertyName, value: PropertyValue, poll=False, keep_polling_value=None):
        """Update a property"""
        if isinstance(property_name, Enum):
            property_name = property_name.value
        if isinstance(value, Enum):
            value = value.value
        
        if self.properties_full.get(property_name, {}).get('read_only'):
            raise AylaReadOnlyPropertyError(f'{property_name} is read only')
        else:
            """ Get the name of the property. Case sizing for 'SET' varies """
            property_name = self.properties_full.get(property_name).get("name")

        end_point = self.set_property_endpoint(property_name)
        data = {'datapoint': {'value': value}}
        if poll:
            data['datapoint']['echo'] = 0

        resp = self.ayla_api.self_request('post', end_point, json=data)
        if poll:
            self.poll_while(property_name, keep_polling_value)
        else:
            self.properties_full[property_name].update(resp)

    async def async_set_property_value(self, property_name: PropertyName, value: PropertyValue, poll=False, keep_polling_value=None):
        """Update a property async. Override the parent version since it adds SET_ in front of the property name."""
        if isinstance(property_name, Enum):
            property_name = property_name.value
        if isinstance(value, Enum):
            value = value.value
        
        if self.properties_full.get(property_name, {}).get('read_only'):
            raise AylaReadOnlyPropertyError(f'{property_name} is read only')
        else:
            """ Get the name of the property. Case sizing for 'SET' varies """
            property_name = self.properties_full.get(property_name).get("name")

        end_point = self.set_property_endpoint(property_name)
        data = {'datapoint': {'value': value}}
        if poll:
            data['datapoint']['echo'] = 0

        async with await self.ayla_api.async_request('post', end_point, json=data) as resp:
            resp_data = await resp.json()

        if poll:
            await self.async_poll_while(property_name, keep_polling_value)
        else:
            self.properties_full[property_name].update(resp_data)


    async def async_update(self, props: list[str] | None=None):
        await super().async_update(props)
        await self.refresh_sensed_temp()

    def get_last_datapoint(self, property: str) -> dict[str, Any] | None:
        endpoint = self.set_property_endpoint(property)
        extra_param = {"limit": 1}
        data = self.ayla_api.self_request("get", endpoint, params=extra_param).json()

        if len(data) > 0:
            return data[-1]["datapoint"]

    async def async_get_last_datapoint(self, property: str) -> dict[str, Any] | None:
        endpoint = self.set_property_endpoint(property)
        extra_param = {"limit": 1}
        async with await self.ayla_api.async_request("get", endpoint, params=extra_param) as resp:
            data = await resp.json()

        if len(data) > 0:
            return data[-1]["datapoint"]
        
        return None

    def poll_while(self, property: str, keep_polling_value: Any):
        count = 0
        datapoint = self.get_last_datapoint(property)
        while count < 10:
            datapoint = self.get_last_datapoint(property)
            if datapoint and datapoint["value"] != keep_polling_value and datapoint["echo"] == True:
                break

            count += 1
            syncsleep(1)

    async def async_poll_while(self, property: str, keep_polling_value: Any):
        count = 0
        datapoint = await self.async_get_last_datapoint(property)
        while count < 10:
            datapoint = await self.async_get_last_datapoint(property)
            if datapoint and datapoint["value"] != keep_polling_value and datapoint["echo"] == True:
                break

            count += 1
            await sleep(1)

    async def refresh_sensed_temp(self):
        await self.async_set_property_value(PROP, 1, poll=True, keep_polling_value=1)
        await super().async_update([DISPLAY_TEMP])

    @property
    def device_name(self) -> str:
        return self.property_values[DEVICE_NAME]

    @property
    def capabilities(self) -> Dict[Capability, bool]:
        caps = self.property_values[DEVICE_CAPABILITIES]
        ret = {}
        for c in Capability:
            if caps & c == c:
                ret[c] = True
            else:
                ret[c] = False

        return ret

    def has_capability(self, capability: Capability) -> bool:
        try:
            return self.capabilities[capability]
        except KeyError:
            return False

    @property
    def supported_op_modes(self) -> list[OpMode]:
        modes = [
            mode
            for mode in OpMode
            if getattr(Capability, f"OP_{mode.name}", False)
            and self.has_capability(Capability[f"OP_{mode.name}"])
        ]
        modes.append(OpMode.OFF)
        modes.append(OpMode.ON)
        return modes

    @property
    def op_mode(self) -> OpMode:
        return OpMode(self.property_values[OPERATION_MODE])

    @op_mode.setter
    def op_mode(self, val: OpMode):
        if val not in self.supported_op_modes:
            raise SettingNotSupportedError(f"Device does not support operation mode {val.name}")

        self.set_property_value(OPERATION_MODE, val)

    async def async_set_op_mode(self, val: OpMode):
        if val not in self.supported_op_modes:
            raise SettingNotSupportedError(f"Device does not support operation mode {val.name}")

        await self.async_set_property_value(OPERATION_MODE, val)

    @property
    def supported_fan_speeds(self) -> list[FanSpeed]:
        return [
            speed
            for speed in FanSpeed
            if self.has_capability(Capability[f"FAN_{speed.name}"])
        ]

    @property
    def fan_speed(self) -> FanSpeed:
        return FanSpeed(self.property_values[FAN_SPEED])

    @fan_speed.setter
    def fan_speed(self, val: FanSpeed):
        if val not in self.supported_fan_speeds:
            raise SettingNotSupportedError(f"Device does not support fan speed {val.name}")

        self.set_property_value(FAN_SPEED, val)

    async def async_set_fan_speed(self, val: FanSpeed):
        if val not in self.supported_fan_speeds:
            raise SettingNotSupportedError(f"Device does not support fan speed {val.name}")

        await self.async_set_property_value(FAN_SPEED, val)

    @property
    def sensed_temp(self) -> float:
        return (
            round(
                _convert_sensed_temp_to_celsius(
                    int(self.property_values[DISPLAY_TEMP])
                )
                * 2
            )
            / 2
        )

    def temperature_range_for_mode(self, mode: OpMode) -> (float, float):
        if mode not in self.supported_op_modes:
            raise SettingNotSupportedError(f"Device does not support operation mode {mode.name}")
        
        if mode == OpMode.HEAT:
            return (MIN_TEMP_HEAT, MAX_TEMP_HEAT)

        return (MIN_TEMP_COOL, MAX_TEMP_COOL)

    @property
    def temperature_range(self) -> (float, float):
        return self.temperature_range_for_mode(self.op_mode)

    @property
    def set_temp(self) -> float:
        return float(self.property_values[ADJUST_TEMPERATURE]) / 10.0

    @set_temp.setter
    def set_temp(self, val: float):
        self.set_property_value(ADJUST_TEMPERATURE, int(val * 10.0))

    async def async_set_set_temp(self, val: float):
        await self.async_set_property_value(ADJUST_TEMPERATURE, int(val * 10.0))

    @property
    def supported_swing_modes(self) -> list[SwingMode]:
        modes = [
            mode
            for mode in SwingMode
            if getattr(Capability, mode.name, False)
            and self.has_capability(Capability[mode.name])
        ]
        if SwingMode.SWING_HORIZONTAL in modes and SwingMode.SWING_VERTICAL in modes:
            modes.append(SwingMode.SWING_BOTH)

        if len(modes) > 0:
            modes.append(SwingMode.OFF)

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
        if val not in self.supported_swing_modes:
            raise SettingNotSupportedError(f"Device does not support swing mode {val.name}")

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

    async def async_set_swing_mode(self, val: SwingMode):
        if val not in self.supported_swing_modes:
            raise SettingNotSupportedError(f"Device does not support swing mode {val.name}")

        if val == SwingMode.SWING_BOTH:
            await self.async_set_horizontal_swing(True)
            await self.async_set_vertical_swing(True)
        elif val == SwingMode.SWING_HORIZONTAL:
            await self.async_set_horizontal_swing(True)
            await self.async_set_vertical_swing(False)
        elif val == SwingMode.SWING_VERTICAL:
            await self.async_set_vertical_swing(True)
            await self.async_set_horizontal_swing(False)
        elif val == SwingMode.OFF:
            await self.async_set_vertical_swing(False)
            await self.async_set_horizontal_swing(False)

    @property
    def horizontal_swing(self) -> bool:
        if not self.has_capability(Capability.SWING_HORIZONTAL):
            raise SettingNotSupportedError("Device does not support horizontal swing")

        return self.property_values[HORIZ_SWING_PARAM_MAP[self.model]] == SWING_VAL_MAP[self.model][True]

    @horizontal_swing.setter
    def horizontal_swing(self, val: bool):
        if not self.has_capability(Capability.SWING_HORIZONTAL):
            raise SettingNotSupportedError("Device does not support horizontal swing")

        self.set_property_value(HORIZ_SWING_PARAM_MAP[self.model], SWING_VAL_MAP[self.model][val])

    async def async_set_horizontal_swing(self, val: bool):
        if not self.has_capability(Capability.SWING_HORIZONTAL):
            raise SettingNotSupportedError("Device does not support horizontal swing")

        await self.async_set_property_value(HORIZ_SWING_PARAM_MAP[self.model], SWING_VAL_MAP[self.model][val])

    @property
    def vertical_swing(self) -> bool:
        if not self.has_capability(Capability.SWING_VERTICAL):
            raise SettingNotSupportedError("Device does not support vertical swing")

        return self.property_values[VERT_SWING_PARAM_MAP[self.model]] == SWING_VAL_MAP[self.model][True]

    @vertical_swing.setter
    def vertical_swing(self, val: bool):
        if not self.has_capability(Capability.SWING_VERTICAL):
            raise SettingNotSupportedError("Device does not support vertical swing")

        self.set_property_value(VERT_SWING_PARAM_MAP[self.model], SWING_VAL_MAP[self.model][val])

    async def async_set_vertical_swing(self, val: bool):
        if not self.has_capability(Capability.SWING_VERTICAL):
            raise SettingNotSupportedError("Device does not support vertical swing")

        await self.async_set_property_value(VERT_SWING_PARAM_MAP[self.model], SWING_VAL_MAP[self.model][val])