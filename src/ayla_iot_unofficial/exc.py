"""Exceptions"""

# Default messages
AUTH_EXPIRED_MESSAGE = 'Ayla Networks API authentication expired.  Re-authenticate and retry.'
AUTH_FAILURE_MESSAGE = 'Error authenticating to Ayla Networks.'
NOT_AUTHED_MESSAGE   = 'Ayla Networks API not authenticated.  Authenticate first and retry.'


class AylaError(RuntimeError):
    """Parent class for all Ayla Networks exceptions"""


class AylaAuthError(AylaError):
    """Exception authenticating"""
    def __init__(self, msg=AUTH_FAILURE_MESSAGE, *args):
        super().__init__(msg, *args)


class AylaAuthExpiringError(AylaError):
    """Authentication expired and needs to be refreshed"""
    def __init__(self, msg=AUTH_EXPIRED_MESSAGE, *args):
        super().__init__(msg, *args)


class AylaNotAuthedError(AylaError):
    """Not authorized"""
    def __init__(self, msg=NOT_AUTHED_MESSAGE, *args):
        super().__init__(msg, *args)


class AylaReadOnlyPropertyError(AylaError):
    """Property is read-only and is not allowed to be set."""
    pass