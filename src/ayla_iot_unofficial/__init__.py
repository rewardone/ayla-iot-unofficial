"""Python API for Ayla IoT devices"""

from .ayla_iot_unofficial import (
    AylaApi,
    new_ayla_api
)

from .exc import (
    AylaError,
    AylaAuthError,
    AylaAuthExpiringError,
    AylaNotAuthedError,
    AylaReadOnlyPropertyError,
)

__version__ = '1.2.4'