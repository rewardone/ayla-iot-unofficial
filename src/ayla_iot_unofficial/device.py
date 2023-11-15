"""Basic non-device-specific data object"""

from .exc        import AylaReadOnlyPropertyError
from base64      import b64encode
from collections import abc, defaultdict
from datetime    import datetime
from enum        import Enum, IntEnum, unique
from logging     import getLogger
from pprint      import pformat
from re          import findall
from requests    import get
from typing      import Any, Dict, Iterable, List, Optional, Set, Union, TYPE_CHECKING

try:
    from ujson   import loads
except ImportError:
    from json    import loads

if TYPE_CHECKING:
    from .ayla_iot_unofficial import AylaApi

TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%SZ'
_LOGGER = getLogger(__name__)

PropertyName  = Union[str, Enum]
PropertyValue = Union[str, int, Enum]


def _parse_datetime(date_string: str) -> datetime:
    """Parse a datetime as returned by the Ayla Networks API"""
    return datetime.strptime(date_string, TIMESTAMP_FMT)


@unique
class VacuumPowerModes(IntEnum):
    """Vacuum power modes"""
    ECO = 1
    NORMAL = 0
    MAX = 2


@unique
class VacuumOperatingModes(IntEnum):
    """Vacuum operation modes"""
    STOP = 0
    PAUSE = 1
    START = 2
    RETURN = 3


@unique
class VacuumProperties(Enum):
    """Useful properties"""
    """ VACUUM DEVICES """
    AREAS_TO_CLEAN          = "Areas_To_Clean"
    BATTERY_CAPACITY        = "Battery_Capacity"
    CHARGING_STATUS         = "Charging_Status"
    CLEAN_COMPLETE          = "CleanComplete"
    CLEANING_STATISTICS     = "Cleaning_Statistics"
    DOCKED_STATUS           = "DockedStatus"
    ERROR_CODE              = "Error_Code"
    EVACUATING              = "Evacuating"  # Doesn't really work because update frequency on the dock (default 20s) is too slow
    FIND_DEVICE             = "Find_Device"
    LOW_LIGHT_MISSION       = "LowLightMission"
    NAV_MODULE_FW_VERSION   = "Nav_Module_FW_Version"
    OPERATING_MODE          = "Operating_Mode"
    POWER_MODE              = "Power_Mode"
    RECHARGE_RESUME         = "Recharge_Resume"
    RECHARGING_TO_RESUME    = "Recharging_To_Resume"
    ROBOT_FIRMWARE_VERSION  = "Robot_Firmware_Version"
    ROBOT_ROOM_LIST         = "Robot_Room_List"
    RSSI                    = "RSSI"


VACUUM_ERROR_MESSAGES = {
    1: "Side wheel is stuck",
    2: "Side brush is stuck",
    3: "Suction motor failed",
    4: "Brushroll stuck",
    5: "Side wheel is stuck (2)",
    6: "Bumper is stuck",
    7: "Cliff sensor is blocked",
    8: "Battery power is low",
    9: "No Dustbin",
    10: "Fall sensor is blocked",
    11: "Front wheel is stuck",
    13: "Switched off",
    14: "Magnetic strip error",
    16: "Top bumper is stuck",
    18: "Wheel encoder error",
}


class Device:
    """Generic device entity"""

    def __init__(self, ayla_api: "AylaApi", device_dct: Dict, europe: bool = False):
        """
            Start object with serial = dsn. For some devices (such as SharkIQ vacuums) a device serial number is needed instead.
                call _update_metadata() to update these values.
                Other objects (such as Culligan water softeners), the DSN is used in place of serial numbers
        """
        self.ayla_api               = ayla_api
        self._dsn                   = device_dct['dsn']
        self._key                   = device_dct['key']
        self._oem_model_number      = device_dct['oem_model']   # type: str
        self._device_model_number   = device_dct['model']       # type: Optional[str]
        self._device_serial_number  = device_dct['dsn']         # type: Optional[str]
        self._device_mac_address    = device_dct['mac']
        self._device_ip_address     = device_dct['lan_ip']
        self.properties_full        = defaultdict(dict)         # Using a defaultdict prevents errors before calling `update()`
        self.property_values        = DevicePropertiesView(self)
        self.triggers               = defaultdict(dict)
        self._settable_properties   = None                      # type: Optional[Set]
        self.europe                 = europe                    # type: bool
        self.eu_user_field_url      = "https://user-field-eu.aylanetworks.com"
        self.eu_ads_url             = "https://ads-eu.aylanetworks.com"
        self.user_field_url         = "https://user-field.aylanetworks.com"
        self.ads_url                = "https://ads-field.aylanetworks.com"

        # Properties
        self._name                  = device_dct['product_name']
        self._error                 = None

    @property
    def oem_model_number(self) -> str:
        return self._oem_model_number

    @property
    def device_model_number(self) -> Optional[str]:
        return self._device_model_number

    @property
    def device_serial_number(self) -> Optional[str]:
        return self._device_serial_number

    @property
    def name(self):
        return self._name

    @property
    def serial_number(self) -> str:
        return self._dsn

    @property
    def metadata_endpoint(self) -> str:
        """
            Endpoint for device metadata. This API returns a list of device metadata keys and values, based on wild cards.
            Possibly handle keys if an endpoint is discovered/needed
        """
        return f'{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/dsns/{self._dsn:s}/data.json'
    
    @property
    def dsn_all_properties_endpoint(self) -> str:
        """
            API endpoint to fetch updated device information
            This API retrieves all the properties for a specified device serial number (DSN).
        """
        return f'{self.eu_ads_url if self.europe else self.ads_url}/apiv1/dsns/{self.serial_number}/properties.json'
    
    def property_triggers_endpoint(self, property_name) -> str:
        """
            Certain properties have triggers (e.g. notifications, etc.) tied to them. Get the endpoint that contains the trigger data.
        """
        return f'{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/dsns/{self._dsn:s}/properties/{property_name:s}/triggers.json'

    def set_property_endpoint(self, property_name) -> str:
        """Get the API endpoint for a given property"""
        return f'{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/dsns/{self._dsn:s}/properties/{property_name:s}/datapoints.json'

    def _update_metadata(self):
        """ 
            Section for vacuum Metadata 
        
            Idealy this could generically handle any datums from metadata
            Update object with values from metadata
        """
        metadata = self.get_metadata()
        data = [d['datum'] for d in metadata if d.get('datum', {}).get('key', '') == 'sharkDeviceMobileData']
        if data:
            datum = data[0]
            # I do not know why they don't just use multiple keys for this
            try:
                values = loads(datum.get('value'))
            except ValueError:
                values = {}
            self._device_model_number   = values.get('vacModelNumber')
            self._device_serial_number  = values.get('vacSerialNumber')

    def get_metadata(self):
        """Fetch device metadata.  Not needed for basic operation."""
        resp = self.ayla_api.self_request('get', self.metadata_endpoint)
        return resp.json()

    async def async_get_metadata(self):
        """Fetch device metadata.  Not needed for basic operation."""
        async with await self.ayla_api.async_request('get', self.metadata_endpoint) as resp:
            resp_data = await resp.json()
        return resp_data

    def get_property_value(self, property_name: PropertyName) -> Any:
        """Get the value of a property from the properties dictionary"""
        if isinstance(property_name, Enum):
            property_name = property_name.value

        return self.property_values[property_name]

    def set_property_value(self, property_name: PropertyName, value: PropertyValue):
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
        resp = self.ayla_api.self_request('post', end_point, json=data)
        self.properties_full[property_name].update(resp.json())

    async def async_set_property_value(self, property_name: PropertyName, value: PropertyValue):
        """Update a property async"""
        if isinstance(property_name, Enum):
            property_name = property_name.value
        if isinstance(value, Enum):
            value = value.value

        end_point = self.set_property_endpoint(f'SET_{property_name}')
        data = {'datapoint': {'value': value}}
        async with await self.ayla_api.async_request('post', end_point, json=data) as resp:
            resp_data = await resp.json()
        self.properties_full[property_name].update(resp_data)

    def _clean_property_name(self, raw_property_name: str) -> str:
        """Clean up property names"""
        if raw_property_name[:4].upper() in ['SET_', 'GET_']:
            return raw_property_name[4:]
        else:
            return raw_property_name

    def update(self, property_list: Optional[Iterable[str]] = None):
        """Update the known device state from all properties and call _do_update to add the properties to the object property dictionary"""
        full_update = property_list is None
        if full_update:
            params = None
        else:
            params = {'names[]': property_list}

        resp = self.ayla_api.self_request('get', self.dsn_all_properties_endpoint, params=params)
        properties = resp.json()
        
        return self._do_update(full_update, properties)

    async def async_update(self, property_list: Optional[Iterable[str]] = None):
        """Async update the known device state from all properties and call _do_update to add the properties to the object property dictionary"""
        full_update = property_list is None
        if full_update:
            params = None
        else:
            params = {'names[]': property_list}

        async with await self.ayla_api.async_request('get', self.dsn_all_properties_endpoint, params=params) as resp:
            properties = await resp.json()

        # _do_update should not be thread blocking
        return self._do_update(full_update, properties)

    def _do_update(self, full_update: bool, properties: List[Dict]):
        """
            Update the internal state from fetched properties. This is called within update()/async_update()
            Categorize properties by Access (e.g. SET-able or Read-Only).
                Alternatively? This could use the read_only property bool instead of 'set_'.
        """
        property_names = {p['property']['name'] for p in properties}
        settable_properties = {self._clean_property_name(p) for p in property_names if p[:3].upper() == 'SET'}
        readable_properties = {
            self._clean_property_name(p['property']['name']): p['property']
            for p in properties if p['property']['name'].upper() != 'SET'
        }

        if full_update or self._settable_properties is None:
            self._settable_properties = settable_properties
        else:
            self._settable_properties = self._settable_properties.union(settable_properties)

        # Update the property map so we can update by name instead of by fickle number
        if full_update:
            # Did a full update, so let's wipe everything
            self.properties_full = defaultdict(dict)
        self.properties_full.update(readable_properties)

        return True

    @staticmethod
    def _get_most_recent_datum(data_list: List[Dict], date_field: str = 'updated_at') -> Dict:
        """Get the most recent data point from a list of annoyingly nested values"""
        datapoints = {
            _parse_datetime(d['datapoint'][date_field]): d['datapoint'] for d in data_list if 'datapoint' in d
        }
        if not datapoints:
            return {}
        latest_datum = datapoints[max(datapoints.keys())]
        return latest_datum

    def _get_file_property_endpoint(self, property_name: PropertyName) -> str:
        """Check that property_name is a file property and return its lookup endpoint"""
        if isinstance(property_name, Enum):
            property_name = property_name.value

        property_id = self.properties_full[property_name]['key']
        if self.properties_full[property_name].get('base_type') != 'file':
            raise ValueError(f'{property_name} is not a file property')
        return f'{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/properties/{property_id:d}/datapoints.json'

    def get_file_property_url(self, property_name: PropertyName) -> Optional[str]:
        """File properties are versioned and need a special lookup"""
        try:
            url = self._get_file_property_endpoint(property_name)
        except KeyError:
            return None

        resp = self.ayla_api.self_request('get', url)
        data_list = resp.json()
        latest_datum = self._get_most_recent_datum(data_list)
        return latest_datum.get('file')

    async def async_get_file_property_url(self, property_name: PropertyName) -> Optional[str]:
        """File properties are versioned and need a special lookup"""
        try:
            url = self._get_file_property_endpoint(property_name)
        except KeyError:
            return None

        async with await self.ayla_api.async_request('get', url) as resp:
            data_list = await resp.json()
        latest_datum = self._get_most_recent_datum(data_list)
        return latest_datum.get('file')

    def get_file_property(self, property_name: PropertyName) -> bytes:
        """Get the latest file for a file property and return as bytes"""
        # These do not require authentication, so we won't use the ayla_api
        url = self.get_file_property_url(property_name)
        resp = get(url)
        return resp.content

    async def async_get_file_property(self, property_name: PropertyName) -> bytes:
        """Get the latest file for a file property and return as bytes"""
        url = await self.async_get_file_property_url(property_name)
        session = self.ayla_api.websession
        async with session.get(url) as resp:
            return await resp.read()

    def get_property_triggers(self, property_name: PropertyName):
        """For a properties triggers, get them and add them to the device"""
        resp = self.ayla_api.self_request('get', self.property_triggers_endpoint(property_name))
        triggers = resp.json()
        #[{trigger:{key}}]
        for trigger in triggers:
            if trigger["trigger"]["key"] not in self.triggers.keys():
                self.triggers[trigger["trigger"]["key"]] = trigger["trigger"]

    async def async_get_property_triggers(self, property_name: PropertyName):
        """For a properties triggers, get them and add them to the device"""
        resp = await self.ayla_api.async_request('get', self.property_triggers_endpoint(property_name))
        triggers = await resp.json()
        #[{trigger:{key}}]
        for trigger in triggers:
            if trigger["trigger"]["key"] not in self.triggers.keys():
                self.triggers[trigger["trigger"]["key"]] = trigger["trigger"]

class Vacuum(Device):
    """ Extend device into a vacuum specific device """
    def __init__(self, ayla_api: "AylaApi", device_dct: Dict, europe: bool = False):
        super().__init__(ayla_api, device_dct, europe)
        self._update_metadata()   # update metadata needed for sharkIQ 

    def _encode_room_list(self, rooms: List[str]):
        """Base64 encode the list of rooms to clean"""
        if not rooms:
            # By default, clean all rooms
            return '*'

        room_list = self._get_device_room_list()
        _LOGGER.debug(f'Room list identifier is: {room_list["identifier"]}')

        # Header explained:
        # 0x80: Control character - some mode selection
        # 0x01: Start of Heading Character
        # 0x0B: Use Line Tabulation (entries separated by newlines)
        # 0xca: Control character - purpose unknown
        # 0x02: Start of text (indicates start of room list)
        header = '\x80\x01\x0b\xca\x02'

        # For each room in the list:
        # - Insert a byte representing the length of the room name string
        # - Add the room name
        # - Join with newlines (presumably because of the 0x0B in the header)
        rooms_enc = "\n".join([chr(len(room)) + room for room in rooms])

        # The footer starts with control character 0x1A
        # Then add the length indicator for the room list identifier
        # Then add the room list identifier
        footer = '\x1a' + chr(len(room_list['identifier'])) + room_list['identifier']

        # Now that we've computed the room list and footer and know their lengths, finish building the header
        # This character denotes the length of the remaining input
        header += chr(0
                      + 1  # Add one for a newline following the length specifier
                      + len(rooms_enc)
                      + len(footer)
                      )
        header += '\n'  # This is the newline reference above

        # Finally, join and base64 encode the parts
        return b64encode(
            # First encode the string as latin_1 to get the right endianness
            (header + rooms_enc + footer).encode('latin_1')
            # Then return as a utf8 string for ease of handling
        ).decode('utf8')

    def _get_device_room_list(self):
        """Gets the list of known rooms from the device, including the map identifier"""
        room_list = self.get_property_value(VacuumProperties.ROBOT_ROOM_LIST)
        split = room_list.split(':')
        return {
            # The room list is preceded by an identifier, which I believe identifies the list of rooms with the
            # onboard map in the robot
            'identifier': split[0],
            'rooms': split[1:],
        }

    def get_room_list(self) -> List[str]:
        """Gets the list of rooms known by the device"""
        return self._get_device_room_list()['rooms']

    def clean_rooms(self, rooms: List[str]) -> None:
        payload = self._encode_room_list(rooms)
        _LOGGER.debug('Room list payload: ' + payload)
        self.set_property_value(VacuumProperties.AREAS_TO_CLEAN, payload)
        self.set_vacuum_operating_mode(VacuumOperatingModes.START)

    async def async_clean_rooms(self, rooms: List[str]) -> None:
        payload = self._encode_room_list(rooms)
        _LOGGER.debug("Room list payload: " + payload)
        await self.async_set_property_value(VacuumProperties.AREAS_TO_CLEAN, payload)
        await self.async_set_vacuum_operating_mode(VacuumOperatingModes.START)

    def set_vacuum_operating_mode(self, mode: VacuumOperatingModes):
        """Set the vacuum operating mode.  This is just a convenience wrapper around `set_property_value`"""
        self.set_property_value(VacuumProperties.OPERATING_MODE, mode)

    async def async_set_vacuum_operating_mode(self, mode: VacuumOperatingModes):
        """Set the vacuum operating mode.  This is just a convenience wrapper around `set_property_value`"""
        await self.async_set_property_value(VacuumProperties.OPERATING_MODE, mode)

    def find_device(self):
        """Make the device emit an annoying chirp so you can find it"""
        self.set_property_value(VacuumProperties.FIND_DEVICE, 1)

    async def async_find_device(self):
        """Make the device emit an annoying chirp so you can find it"""
        await self.async_set_property_value(VacuumProperties.FIND_DEVICE, 1)

    @property
    def error_code(self) -> Optional[int]:
        """Error code"""
        return self.get_property_value(VacuumProperties.ERROR_CODE)

    @property
    def error_text(self) -> Optional[str]:
        """Error message"""
        err = self.error_code
        if err:
            return VACUUM_ERROR_MESSAGES.get(err, f'Unknown error ({err})')
        return None

class Softener(Device):
    """ Extend device into a water softener specific device """

    def __init__(self, ayla_api: "AylaApi", device_dct: Dict, europe: bool = False):
        super().__init__(ayla_api, device_dct, europe)

        self.alternate_mapping          = {
            "aqua_sensor_Zmin"          : "aqua_sensor_Zmin_1",
            "aqua_sensor_Zratio_current": "aqua_sensor_Zratio_curr_1",
            "BD_rinse"                  : "bd_rinse",
            "capacity_remaining_gallons": "capacity_remaining_volume_1",
            "days_since_last_regen"     : "days_since_last_regen_1",
            "error_flags"               : "system_error_flags",
            "flow_profiles_max_flow"    : "flow_profiles_max_flow_lim",
            "flow_profiles_min_flow"    : "flow_profiles_min_flow_lim",
            "gbe_fw_version"            : "gbx_fw_version",
            "hardness_in_grains_per_gal": "hardness_value",
            "iron_setting"              : "iron",
            "last_regen_date_time"      : "last_regen_date_time_1",
            "next_regen_on_date"        : "next_regen_date_time",
            "regen_interval_days_setting":"regen_interval_days",
            "salt_dosage_in_lbs"        : "salt_dosage",
            "sbt_salt_level_low"        : "low_salt_level",
            "set_vacation_mode"         : "set_away_mode",
            "vacation_mode"             : "away_mode",                      # instead of ensuring it works with 'clean properties', just add this key in addition
            "total_gallons_since_install":"water_usage_since_install_1",
            "total_gallons_today"       : "total_water_usage_today_1",
            "unit_status"               : "unit_status_1",
            "valve_position"            : "valve_position_1"
        }

        # # init should call update() and properties should be available
        # self.avg_daily_usage            = self.get_property_value("avg_daily_usage")
        # self.current_flow_rate          = self.get_property_value("current_flow_rate")
        # self.capacity_remaining_gallons = self.get_property_value("capacity_remaining_gallons")
        # self.hardness_in_grains_per_gal = self.get_property_value("hardness_in_grains_per_gal")
        # self.days_since_last_regen      = self.get_property_value("days_since_last_regen")
        # self.last_regen_date_time       = self.get_property_value("last_regen_date_time")
        # self.away_mode_water_use        = self.get_property_value("away_mode_water_use")
        # self.valve_position             = self.get_property_value("valve_position")
        # self.total_gallons_today        = self.get_property_value("total_gallons_today")
        # self.error_flags                = self.get_property_value("error_flags")
        # self.total_gallons_since_install= self.get_property_value("total_gallons_since_install")
        # self.total_regens_since_install = self.get_property_value("total_regens_since_install")
        self.avg_daily_properties       = ["avg_sun","avg_mon","avg_tue","avg_wed","avg_thr","avg_fri","avg_sat"]
        self.daily_usage_properties     = ["daily_usage_day_1", "daily_usage_day_2", "daily_usage_day_3", "daily_usage_day_4", "daily_usage_day_5", "daily_usage_day_6", "daily_usage_day_7"]
        self.hourly_usage_properties    = ["hourly_usage_hour_1", "hourly_usage_hour_2", "hourly_usage_hour_3", "hourly_usage_hour_4", "hourly_usage_hour_5", "hourly_usage_hour_6", "hourly_usage_hour_7", "hourly_usage_hour_8", "hourly_usage_hour_9", "hourly_usage_hour_10", "hourly_usage_hour_11", "hourly_usage_hour_12", "hourly_usage_hour_13", "hourly_usage_hour_14", "hourly_usage_hour_15", "hourly_usage_hour_16", "hourly_usage_hour_17", "hourly_usage_hour_18", "hourly_usage_hour_19", "hourly_usage_hour_20", "hourly_usage_hour_21", "hourly_usage_hour_22", "hourly_usage_hour_23", "hourly_usage_hour_24"]

    @property
    def datapoints_endpoint(self) -> str:
        "Provide the datapoints endpoint, used for polling, property updates, and more"
        return f'{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/batch_datapoints.json'

    def set_datapoint_payload(self, property, value) -> Dict:
        """Create a batch_datapoint update payload"""
        return {
            "batch_datapoints": [
                {
                    "datapoint": {
                        "value": value
                    },
                    "dsn": self._device_serial_number,
                    "name": property
                }
            ]
        }

    def get_property_value(self, property_name: PropertyName) -> Any:
        """Get the value of a property from the properties dictionary"""
        if isinstance(property_name, Enum):
            property_name = property_name.value

        if property_name in self.properties_full.keys():
            return self.property_values[property_name]
        elif self.alternate_mapping:
            if self.alternate_mapping[property_name] in self.properties_full.keys():
                return self.property_values[self.alternate_mapping[property_name]]
        else:
            return False

    def set_property_value(self, property_name: PropertyName, value: PropertyValue):
        """Update a property, overload from device"""
        if isinstance(property_name, Enum):
            property_name = property_name.value
        if isinstance(value, Enum):
            value = value.value
        
        if self.properties_full.get(property_name, {}).get('read_only'):
            raise AylaReadOnlyPropertyError(f'{property_name} is read only')
        else:
            """ Get the name of the property. Case sizing for 'SET' varies """
            property_name = self.properties_full.get(property_name).get("name")

        resp = self.ayla_api.self_request('post', self.datapoints_endpoint, json=self.set_datapoint_payload(property_name, value))
        # datapoint is created, but the value is not returned ... 
        self.update()

    async def async_set_property_value(self, property_name: PropertyName, value: PropertyValue):
        """Update a property async, overload from device"""
        if isinstance(property_name, Enum):
            property_name = property_name.value
        if isinstance(value, Enum):
            value = value.value

        if self.properties_full.get(property_name, {}).get('read_only'):
            raise AylaReadOnlyPropertyError(f'{property_name} is read only')
        else:
            """ Get the name of the property. Case sizing for 'SET' varies """
            property_name = self.properties_full.get(property_name).get("name")

        async with await self.ayla_api.async_request('post', self.datapoints_endpoint, json=self.set_datapoint_payload(property_name, value)) as resp:
            resp_data = await resp.json()
        await self.async_update()

    def send_poll(self):
        """Send a wifi_report to trigger updated properties, this requires an ayla api token"""

        resp = self.ayla_api.self_request('post', self.datapoints_endpoint, json=self.set_datapoint_payload("wifi_report", 1))
        if(resp.json()):
            return True
        else:
            return False

    async def async_send_poll(self):
        """Send a wifi_report to trigger updated properties, this requires an ayla api token"""

        datapoints = f'{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/batch_datapoints.json'

        async with await self.ayla_api.async_request('post', datapoints, json=self.set_datapoint_payload("wifi_report", 1)) as resp:
            json = await resp.json()

        if(json):
            return True
        else:
            return False

    def set_avg_daily_properties_list(self, newList):
        """The default avg_daily_properties are from Culligan data. Allow them to be changed."""
        self.avg_daily_properties       = newList

    def set_daily_usage_properties_list(self, newList):
        """The default daily_usage_properties are from Culligan data. Allow them to be changed."""
        self.daily_usage_properties     = newList

    def set_hourly_usage_properties_list(self, newList):
        """The default hourly_usage_properties are from Culligan data. Allow them to be changed."""
        self.hourly_usage_properties    = newList

    def get_average_daily_usage(self):
        """Convenience wrapper around `get_property_value`"""
        return self.avg_daily_usage

    async def async_get_average_daily_usage(self):
        """Convenience wrapper around `get_property_value`"""
        return self.avg_daily_usage
    
    def get_current_flow_rate(self):
        """Convenience wrapper around `get_property_value`"""
        return self.current_flow_rate

    async def async_get_current_flow_rate(self):
        """Convenience wrapper around `get_property_value`"""
        return self.current_flow_rate

    def get_capacity_remaining_gallons(self):
        """Convenience wrapper around `get_property_value`"""
        return self.capacity_remaining_gallons

    async def async_get_capacity_remaining_gallons(self):
        """Convenience wrapper around `get_property_value`"""
        return self.capacity_remaining_gallons
    
    def get_hardness_in_grains_per_gal(self):
        """Convenience wrapper around `get_property_value`"""
        return self.hardness_in_grains_per_gal

    async def async_get_hardness_in_grains_per_gal(self):
        """Convenience wrapper around `get_property_value`"""
        return self.hardness_in_grains_per_gal
    
    def get_days_since_last_regen(self):
        """Convenience wrapper around `get_property_value`"""
        return self.days_since_last_regen

    async def async_get_days_since_last_regen(self):
        """Convenience wrapper around `get_property_value`"""
        return self.days_since_last_regen
    
    def get_last_regen_date_time(self):
        """Convenience wrapper around `get_property_value`"""
        return self.last_regen_date_time

    async def async_get_last_regen_date_time(self):
        """Convenience wrapper around `get_property_value`"""
        return self.last_regen_date_time
    
    def get_away_mode_water_use(self):
        """Convenience wrapper around `get_property_value`"""
        return self.away_mode_water_use

    async def async_get_away_mode_water_use(self):
        """Convenience wrapper around `get_property_value`"""
        return self.away_mode_water_use

    def get_valve_position(self):
        """Convenience wrapper around `get_property_value`"""
        return self.valve_position

    async def async_get_valve_position(self):
        """Convenience wrapper around `get_property_value`"""
        return self.valve_position

    def get_total_gallons_today(self):
        """Convenience wrapper around `get_property_value`"""
        return self.total_gallons_today

    async def async_get_total_gallons_today(self):
        """Convenience wrapper around `get_property_value`"""
        return self.total_gallons_today
    
    def get_error_flags(self):
        """Convenience wrapper around `get_property_value`"""
        return self.error_flags

    async def async_get_error_flags(self):
        """Convenience wrapper around `get_property_value`"""
        return self.error_flags
    
    def get_total_gallons_since_install(self):
        """Convenience wrapper around `get_property_value`"""
        return self.total_gallons_since_install

    async def async_get_total_gallons_since_install(self):
        """Convenience wrapper around `get_property_value`"""
        return self.total_gallons_since_install
    
    def get_total_regens_since_install(self):
        """Convenience wrapper around `get_property_value`"""
        return self.total_regens_since_install

    async def async_get_total_regens_since_install(self):
        """Convenience wrapper around `get_property_value`"""
        return self.total_regens_since_install

    def start_vacation_mode(self):
        """
            Needs testing. Set vacation mode value from 0 (default) to 255 (max).
            Properties and values may vary per manufacturer.
        """
        if "vacation_mode" in self.properties_full.keys():
            PropertyName    = "vacation_mode"   # because _clean property, 'set' is removed ... "set_vacation_mode"
        elif "away_mode" in self.properties_full.keys():
            PropertyName    = "away_mode"       # because _clean property, 'set' is removed ... "set_away_mode"
        PropertyValue   = 1
        self.set_property_value(PropertyName, PropertyValue)
        return True

    async def async_start_vacation_mode(self):
        """
            Needs testing. Set vacation mode value from 0 (default) to 255 (max).
            Properties and values may vary per manufacturer.
        """
        if "vacation_mode" in self.properties_full.keys():
            PropertyName    = "vacation_mode"   # because _clean property, 'set' is removed ... "set_vacation_mode"
        elif "away_mode" in self.properties_full.keys():
            PropertyName    = "away_mode"       # because _clean property, 'set' is removed ... "set_away_mode"
        PropertyValue   = 1
        await self.async_set_property_value(PropertyName, PropertyValue)
        return True

    def stop_vacation_mode(self):
        """
            Needs testing. Set vacation mode value from 255 (max) to 0 (default).
            Properties and values may vary per manufacturer.
        """
        if "vacation_mode" in self.properties_full.keys():
            PropertyName    = "vacation_mode"   # because _clean property, 'set' is removed ... "set_vacation_mode"
        elif "away_mode" in self.properties_full.keys():
            PropertyName    = "away_mode"       # because _clean property, 'set' is removed ... "set_away_mode"
        PropertyValue   = 0
        self.set_property_value(PropertyName, PropertyValue)
        return True

    async def async_stop_vacation_mode(self):
        """
            Needs testing. Set vacation mode value from 255 (max) to 0 (default).
            Properties and values may vary per manufacturer.
        """
        if "vacation_mode" in self.properties_full.keys():
            PropertyName    = "vacation_mode"   # because _clean property, 'set' is removed ... "set_vacation_mode"
        elif "away_mode" in self.properties_full.keys():
            PropertyName    = "away_mode"       # because _clean property, 'set' is removed ... "set_away_mode"
        PropertyValue   = 0
        await self.async_set_property_value(PropertyName, PropertyValue)
        return True

    def start_bypass_mode(self):
        """Start indefinite bypass"""
        return self.start_bypass_timed_mode(6)
    
    async def async_start_bypass_mode(self):
        """Start indefinite bypass"""
        return await self.async_start_bypass_timed_mode(6)

    def start_bypass_timed_mode(self, presetTimeCode = 1):
        """
            Needs testing. Set standard_bypass value from 0 (default) to 255 (max).
            Properties and values may vary per manufacturer.
            1 = 30m
            2 = 60m
            3 = 90m
            4 = 120m
            5 = 180m
            6 = indefinite
        """
        if "standard_bypass" in self.properties_full.keys():
            PropertyName    = "standard_bypass"   # because _clean property, 'set' is removed ... "set_standard_bypass"
            PropertyValue   = presetTimeCode
            self.set_property_value(PropertyName, PropertyValue)
            return True
        else:
            return False

    async def async_start_bypass_timed_mode(self, presetTimeCode = 1):
        """
            Needs testing. Set standard_bypass value from 0 (default) to 255 (max).
            Properties and values may vary per manufacturer.
            1 = 30m
            2 = 60m
            3 = 90m
            4 = 120m
            5 = 180m
            6 = indefinite
        """
        if "standard_bypass" in self.properties_full.keys():
            PropertyName    = "standard_bypass"   # because _clean property, 'set' is removed ... "set_standard_bypass"
            PropertyValue   = presetTimeCode
            await self.async_set_property_value(PropertyName, PropertyValue)
            return True
        else:
            return False

    def stop_bypass_mode(self):
        """
            Needs testing. Set standard_bypass value to off (0). Value will return automatically to 255.
            Properties and values may vary per manufacturer.
        """
        if "standard_bypass" in self.properties_full.keys():
            PropertyName    = "standard_bypass"   # because _clean property, 'set' is removed ... "set_standard_bypass"
            PropertyValue   = 255
            self.set_property_value(PropertyName, PropertyValue)
            return True
        else:
            return False

    async def async_stop_bypass_mode(self):
        """
            Needs testing. Set standard_bypass value to off (0). Value will return automatically to 255.
            Properties and values may vary per manufacturer.
        """
        if "standard_bypass" in self.properties_full.keys():
            PropertyName    = "standard_bypass"   # because _clean property, 'set' is removed ... "set_standard_bypass"
            PropertyValue   = 0
            await self.async_set_property_value(PropertyName, PropertyValue)
            return True
        else:
            return False

class DevicePropertiesView(abc.Mapping):
    """Convenience API for device properties"""

    @staticmethod
    def _cast_value(value, value_type):
        """Cast property value to the appropriate type."""
        if value is None:
            return None
        type_map = {
            'boolean': bool,
            'decimal': float,
            'integer': int,
            'string': str,
        }
        return type_map.get(value_type, lambda x: x)(value)

    def __init__(self, device: Device):
        self._device = device

    def __getitem__(self, key):
        value = self._device.properties_full[key].get('value')
        value_type = self._device.properties_full[key].get('base_type')
        try:
            return self._cast_value(value, value_type)
        except (TypeError, ValueError) as exc:
            # If we failed to convert the type, just return the raw value
            _LOGGER.warning('Error converting property type (value: %r, type: %r)', value, value_type, exc_info=exc)
            return value

    def __iter__(self):
        for k in self._device.properties_full.keys():
            yield k

    def __len__(self) -> int:
        return self._device.properties_full.__len__()

    def __str__(self) -> str:
        return pformat(dict(self))