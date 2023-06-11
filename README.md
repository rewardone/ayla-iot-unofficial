# ayla-iot-unofficial
An unofficial python library for interacting with the Ayla IoT API. 
Intended to be generic for multi-device use.

Designed primarily to be a support package for [Home Assistant](https://www.home-assistant.io/) integrations.

This library is heavily based off of [sharkiq](https://github.com/JeffResc/sharkiq) by [@JeffResc](https://github.com/JeffResc).

[PyPi](https://pypi.org/project/ayla-iot-unofficial/)

# Ayla References
This device is integrated by/with Ayla Networks and (generally) uses their documentation. 

These can be used as starting references:
* https://developer.aylanetworks.com/apibrowser
* https://docs.aylanetworks.com/reference/getting_started
* https://connection.aylanetworks.com/s/article/2080270
 
## Installation
From PyPi
```bash
pip install ayla-iot-unofficial
```

Build from source
```bash
pip install build
pip build
pip install ayla-iot-unofficial
```

## Library Requirements
Requires typical http interaction and datatype packages like requests, aiohttp, ujson

## User Requirements
Reqiures a username and password (typically a smart device's app login credentials)
Requires an app_id and app_secret (granted by Ayla to the smart device's app for operation/integration)

The app_id and app_secret may need to be obtained from proxy traffic or other method.

## Usage
### Class Object
Instantiate a new class object through new_ayla_api() or Ayla() directly.

For devices that may be region specific, the new_ayla_api() function will create an Ayla() object based on the europe boolean.

### Ayla Access_Token
Standard use should call sign_in() on the Ayla object after creation. This will perform the POST login request to obtain an access_token. 

Some devices communicate with a different IoT domain but still expose the Ayla access_token. This access token can be passed into the Ayla object using _set_credentials() and the proper arguments.

### Devices
By default, calling get_devices() will return a list of class specific device objects with updated properties for use.

See device.py for implemented device classes.

## Typical Operation
```python
python3 -m pip install ayla-iot-unofficial
```

```python
import ayla_iot_unofficial

USERNAME = 'me@email.com'
PASSWORD = '$7r0nkP@s$w0rD'

ayla_api = new_ayla_api(USERNAME, PASSWORD, APP_ID, APP_SECRET)
ayla_api.sign_in()

devices = ayla_api.get_devices()

# Example Vacuum Devices
shark   = devices[0]

shark.set_operating_mode(OperatingModes.START)
shark.return_to_base()

# Example Water Softener Devices
softener = devices[1]

softener.capacity_remaining_gallons
softener.set_vacation_mode()
```

## License
[MIT](https://choosealicense.com/licenses/mit/)