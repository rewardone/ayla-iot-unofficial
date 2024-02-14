"""
Simple implementation of the Ayla networks API

Some devices use the Ayla networks IoT API integration to provide IoT functionality to the device.
Documentation can be found at:
 - https://developer.aylanetworks.com/apibrowser/
 - https://docs.aylanetworks.com/cloud-services/api-browser/
"""

from aiohttp    import ClientSession, ClientTimeout    # async http
from requests   import post, request, Response         # http request library
from datetime   import datetime, timedelta             # datetime operations
from typing     import Dict, List, Optional            # object types

from .const import (
    EU_USER_FIELD_BASE,
    EU_ADS_BASE,
    EU_RULESSERVICE_BASE,
    USER_FIELD_BASE,
    ADS_BASE,
    RULESSERVICE_BASE,
    DEFAULT_TIMEOUT
)

# Custom error handling 
from .exc import (
    AylaError,
    AylaAuthError,
    AylaAuthExpiringError,
    AylaNotAuthedError,
    AylaReadOnlyPropertyError,
)

from .device import Device, Vacuum, Softener
from .fujitsu_hvac import FujitsuHVAC

_session = None

def new_ayla_api(username: str, password: str, app_id: str, app_secret: str, websession: Optional[ClientSession] = None, europe: bool = False, timeout=DEFAULT_TIMEOUT):
    """Get an AylaApi object"""
    if europe:
        return AylaApi(username, password, app_id, app_secret, websession=websession, europe=europe, timeout=timeout)
    else:
        return AylaApi(username, password, app_id, app_secret, websession=websession, timeout=timeout)


class AylaApi:
    """Simple Ayla Networks API wrapper"""

    def __init__(
            self,
            username: str,
            password: str,
            app_id: str,
            app_secret: str,
            websession: Optional[ClientSession] = None,
            europe: bool = False,
            timeout: int=DEFAULT_TIMEOUT):
        self._email             = username      # username should always be an email address
        self._password          = password
        self._access_token      = None          # type: Optional[str]
        self._refresh_token     = None          # type: Optional[str]
        self._auth_expiration   = None          # type: Optional[datetime]
        self._is_authed         = False         # type: bool
        self._app_id            = app_id
        self._app_secret        = app_secret
        self.websession         = websession
        self.europe             = europe
        self.eu_user_field_url  = EU_USER_FIELD_BASE
        self.eu_ads_url         = EU_ADS_BASE
        self.eu_rulesservice_url= EU_RULESSERVICE_BASE
        self.user_field_url     = USER_FIELD_BASE
        self.ads_url            = ADS_BASE
        self.rulesservice_url   = RULESSERVICE_BASE
        self.timeout            = timeout
        self._vacuum_devices    = ["Vacuum","SharkIQ"]
        self._softener_devices  = ["Softener","Smart HE","Water Softener"]

    async def ensure_session(self) -> ClientSession:
        """Ensure that we have an aiohttp ClientSession"""
        if self.websession is None:
            self.websession = ClientSession(timeout=ClientTimeout(total=self.timeout))
        return self.websession

    @property
    def _login_data(self) -> Dict[str, Dict]:
        """Prettily formatted data for the login flow"""
        return {
            "user": {
                "email": self._email,
                "password": self._password,
                "application": {"app_id": self._app_id, "app_secret": self._app_secret},
            }
        }

    @property
    def _sign_out_data(self) -> Dict:
        """Payload for the sign_out call"""
        return {"user": {"access_token": self._access_token}}

    def _set_credentials(self, status_code: int, login_result: Dict):
        """Update the internal credentials store. This tracks current bearer token and data needed for token refresh."""
        if status_code in [404, 401]:
            if "message" in login_result["error"]:
                msg = login_result["error"]["message"]
            else:
                msg = login_result["error"]

            if status_code == 404:
                msg += "  (Confirm app_id and app_secret are correct)"
            
            raise AylaAuthError(msg)

        self._access_token    = login_result["access_token"]
        self._refresh_token   = login_result["refresh_token"]
        self._auth_expiration = datetime.now() + timedelta(seconds=login_result["expires_in"])

        if status_code   != 200:
            self._is_authed   = False
        else:
            self._is_authed   = True

    def sign_in(self):
        """Authenticate to Ayla API synchronously using a POST with credentials."""
        login_data = self._login_data   # get a map for JSON formatting
        resp = post(f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/sign_in.json", json=login_data)
        self._set_credentials(resp.status_code, resp.json())

    def refresh_auth(self):
        """Refresh the authentication synchronously using object tracked refresh token."""
        refresh_data = {"user": {"refresh_token": self._refresh_token}}
        resp = post(f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/refresh_token.json", json=refresh_data)
        self._set_credentials(resp.status_code, resp.json())

    async def async_sign_in(self):
        """Authenticate to Ayla API asynchronously using a POST with credentials.."""
        session = await self.ensure_session()
        login_data = self._login_data
        async with session.post(f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/sign_in.json", json=login_data) as resp:
            self._set_credentials(resp.status, await resp.json())

    async def async_refresh_auth(self):
        """Refresh the authentication asynchronously using object tracked refresh token.."""
        session = await self.ensure_session()
        refresh_data = {"user": {"refresh_token": self._refresh_token}}
        async with session.post(f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/refresh_token.json", json=refresh_data) as resp:
            self._set_credentials(resp.status, await resp.json())

    def _clear_auth(self):
        """Clear authentication state"""
        self._is_authed         = False
        self._access_token      = None
        self._refresh_token     = None
        self._auth_expiration   = None

    def sign_out(self):
        """Sign out and invalidate the access token synchronously"""
        post(f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/sign_out.json", json=self._sign_out_data)
        self._clear_auth()

    async def async_sign_out(self):
        """Sign out and invalidate the access token asynchronously"""
        session = await self.ensure_session()
        async with session.post(f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/sign_out.json", json=self._sign_out_data) as _:
            pass
        self._clear_auth()

    @property
    def auth_expiration(self) -> Optional[datetime]:
        """When does the auth expire"""
        if not self._is_authed:
            return None
        elif self._auth_expiration is None:  # This should not happen, but let's be ready if it does...
            raise AylaNotAuthedError("Invalid state.  Please reauthorize.")
        else:
            return self._auth_expiration

    @property
    def token_expired(self) -> bool:
        """Return true if the token has already expired"""
        if self.auth_expiration is None:
            return True
        return datetime.now() > self.auth_expiration

    @property
    def token_expiring_soon(self) -> bool:
        """Return true if the token will expire soon"""
        if self.auth_expiration is None:
            return True
        return datetime.now() > self.auth_expiration - timedelta(seconds=600)  # Prevent timeout immediately following

    def check_auth(self, raise_expiring_soon=True):
        """Confirm authentication status"""
        if not self._access_token or not self._is_authed or self.token_expired:
            self._is_authed = False
            raise AylaNotAuthedError()
        elif raise_expiring_soon and self.token_expiring_soon:
            raise AylaAuthExpiringError()

    @property
    def auth_header(self) -> Dict[str, str]:
        self.check_auth()
        return {"Authorization": f"auth_token {self._access_token:s}"}

    def _get_headers(self, fn_kwargs) -> Dict[str, str]:
        """
        Extract the headers element from fn_kwargs, removing it if it exists
        and updating with self.auth_header.
        """
        try:
            headers = fn_kwargs['headers']
        except KeyError:
            headers = {}
        else:
            del fn_kwargs['headers']
        headers.update(self.auth_header)
        return headers

    def self_request(self, method: str, url: str, **kwargs) -> Response:
        """Perform an arbitrary request using the requests library synchronously"""
        headers = self._get_headers(kwargs)
        return request(method, url, headers=headers, timeout=self.timeout, **kwargs)

    async def async_request(self, http_method: str, url: str, **kwargs):
        """Perform an arbitrary request using the aiohttp library asynchronously"""
        session = await self.ensure_session()
        headers = self._get_headers(kwargs)
        return session.request(http_method, url, headers=headers, **kwargs)

    def get_user_profile(self) -> Dict[str, str]:
        """Get user profile synchronously"""
        resp = self.self_request("get", f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/get_user_profile.json")
        response = resp.json()
        if resp.status_code == 401:
            raise AylaAuthError(response)
        return response
    
    async def async_get_user_profile(self) -> Dict[str, str]:
        """Get user profile asynchronously"""
        async with await self.async_request("get", f"{self.eu_user_field_url if self.europe else self.user_field_url:s}/users/get_user_profile.json") as resp:
            response = await resp.json()
            if resp.status == 401:
                raise AylaAuthError()
        return response

    def list_devices(self) -> List[Dict]:
        """List devices synchronously"""
        resp = self.self_request("get", f"{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/devices.json")
        devices = resp.json()
        if resp.status_code == 401:
            raise AylaAuthError(devices["error"]["message"])
        return [d["device"] for d in devices]

    async def async_list_devices(self) -> List[Dict]:
        """List devices asynchronously"""
        async with await self.async_request("get", f"{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/devices.json") as resp:
            devices = await resp.json()
            if resp.status == 401:
                raise AylaAuthError(devices["error"]["message"])
        return [d["device"] for d in devices]

    def get_devices(self, update: bool = True) -> List[Device]:
        """Retrieve a device object of devices. Ability to update with metadata. Synchronous."""
        devices = list()
        for d in self.list_devices():
            if   d["product_name"] in self._vacuum_devices:
                devices.append(Vacuum  (self, d, europe=self.europe))
            elif d["product_name"] in self._softener_devices:
                devices.append(Softener(self, d, europe=self.europe))
            elif FujitsuHVAC.supports(d):
                devices.append(FujitsuHVAC(self, d, europe=self.europe))
            else:
                devices.append(Device  (self, d, europe=self.europe))
        # if update:
        #     for device in devices:
        #         device._update_metadata()       # update serial number if needed
        #         device.update()                 # obtain all properties
        return devices

    async def async_get_devices(self, update: bool = True) -> List[Device]:
        """Retrieve a device object of devices. Ability to update with metadata. Asynchronous."""
        devices = list()
        for d in await self.async_list_devices():
            if   d["product_name"] in self._vacuum_devices:
                devices.append(Vacuum  (self, d, europe=self.europe))
            elif d["product_name"] in self._softener_devices:
                devices.append(Softener(self, d, europe=self.europe))
            elif FujitsuHVAC.supports(d):
                devices.append(FujitsuHVAC(self, d, europe=self.europe))
            else:
                devices.append(Device  (self, d, europe=self.europe))
        # if update:
        #     for device in devices:
        #         await device._update_metadata() # update serial number if needed
        #         await device.async_update()     # obtain all properties
        return devices
    
    def get_actions(self) -> Dict[str, str]:
        """Get actions synchronously"""
        resp = self.self_request("get", f"{self.eu_rulesservice_url if self.europe else self.rulesservice_url:s}/rulesservice/v1/actions.json")
        response = resp.json()["actions"]
        if resp.status_code == 401:
            raise AylaAuthError(response)
        return response
        
    async def async_get_actions(self) -> Dict[str, str]:
        """Get actions asynchronously"""
        async with await self.async_request("get", f"{self.eu_rulesservice_url if self.europe else self.rulesservice_url:s}/rulesservice/v1/actions.json") as resp:
            response = await resp.json()["actions"]
            if resp.status == 401:
                raise AylaAuthError()
        return response
    
    def get_rules(self) -> Dict[str, str]:
        """Get rules synchronously"""
        resp = self.self_request("get", f"{self.eu_rulesservice_url if self.europe else self.rulesservice_url:s}/rulesservice/v1/rules.json")
        response = resp.json()["rules"]
        if resp.status_code == 401:
            raise AylaAuthError(response)
        return response
        
    async def async_get_rules(self) -> Dict[str, str]:
        """Get rules asynchronously"""
        async with await self.async_request("get", f"{self.eu_rulesservice_url if self.europe else self.rulesservice_url:s}/rulesservice/v1/rules.json") as resp:
            response = await resp.json()["rules"]
            if resp.status == 401:
                raise AylaAuthError()
        return response
    
    def get_rule_action(self, rule_uuid) -> Dict[str, str]:
        """Get rules synchronously"""
        resp = self.self_request("get", f"{self.eu_rulesservice_url if self.europe else self.rulesservice_url:s}/rulesservice/v1/rules/{rule_uuid}/actions.json")
        response = resp.json()["actions"]
        if resp.status_code == 401:
            raise AylaAuthError(response)
        return response
        
    async def async_get_rule_action(self, rule_uuid) -> Dict[str, str]:
        """Get rules asynchronously"""
        async with await self.async_request("get", f"{self.eu_rulesservice_url if self.europe else self.rulesservice_url:s}/rulesservice/v1/rules/{rule_uuid}/actions.json") as resp:
            response = await resp.json()["actions"]
            if resp.status == 401:
                raise AylaAuthError()
        return response
    
    def get_commands(self, device_id) -> Dict[str, str]:
        """Get commands synchronously"""
        resp = self.self_request("get", f"{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/devices/{device_id}/commands.json")
        response = resp.json()
        if resp.status_code == 401:
            raise AylaAuthError(response)
        return response
        
    async def async_get_commands(self, device_id) -> Dict[str, str]:
        """Get commands asynchronously"""
        async with await self.async_request("get", f"{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/devices/{device_id}/commands.json") as resp:
            response = await resp.json()
            if resp.status == 401:
                raise AylaAuthError()
        return response
    
    def get_all_notifications(self, device_id) -> Dict[str, str]:
        """Get notifications by all on device synchronously"""
        resp = self.self_request("get", f"{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/devices/{device_id}/notifications/all.json")
        response = resp.json()["notification"]
        if resp.status_code == 401:
            raise AylaAuthError(response)
        return response
        
    async def async_get_all_notifications(self, device_id) -> Dict[str, str]:
        """Get notifications by all on device asynchronously"""
        async with await self.async_request("get", f"{self.eu_ads_url if self.europe else self.ads_url:s}/apiv1/devices/{device_id}/notifications/all.json") as resp:
            response = await resp.json()["notification"]
            if resp.status == 401:
                raise AylaAuthError()
        return response
