import aiohttp
import pytest
from src.ayla_iot_unofficial.ayla_iot_unofficial import new_ayla_api, AylaApi
from src.ayla_iot_unofficial.const import TEST_APP_ID, TEST_APP_SECRET
from src.ayla_iot_unofficial.exc import (
    AylaAuthError,
    AylaAuthExpiringError,
    AylaNotAuthedError,
    AUTH_EXPIRED_MESSAGE,
    NOT_AUTHED_MESSAGE,
)
from datetime import datetime, timedelta


def test_new_ayla_api():
    api = new_ayla_api("myusername@mysite.com", "mypassword")

    assert api._email == "myusername@mysite.com"
    assert api._password == "mypassword"
    assert api._access_token is None
    assert api._refresh_token is None
    assert api._auth_expiration is None
    assert api._is_authed == False
    assert api._app_id == TEST_APP_ID
    assert api._app_secret == TEST_APP_SECRET
    assert api.websession is None


class TestAylaApi:
    def test_init__required_vals(self):
        api = AylaApi(
            "myusername@mysite.com", "mypassword", "app_id_123", "appsecret_123"
        )

        assert api._email == "myusername@mysite.com"
        assert api._password == "mypassword"
        assert api._access_token is None
        assert api._refresh_token is None
        assert api._auth_expiration is None
        assert api._is_authed == False
        assert api._app_id == "app_id_123"
        assert api._app_secret == "appsecret_123"
        assert api.websession is None

    @pytest.mark.asyncio
    async def test_ensure_session(self, dummy_api):
        # Initially created with no websession
        assert dummy_api.websession is None

        session = await dummy_api.ensure_session()

        # Check that session was created and returned
        assert isinstance(session, aiohttp.ClientSession)
        assert dummy_api.websession is session

    def test_property__login_data(self, dummy_api):
        assert dummy_api._login_data == {
            "user": {
                "email": "myusername@mysite.com",
                "password": "mypassword",
                "application": {
                    "app_id": TEST_APP_ID,
                    "app_secret": TEST_APP_SECRET,
                },
            }
        }

    def test_set_credentials__404_response(self, dummy_api):
        with pytest.raises(AylaAuthError) as e:
            dummy_api._set_credentials(404, {"error": {"message": "Not found"}})
        assert (
            e.value.args[0] == "Not found (Confirm app_id and app_secret are correct)"
        )

    def test_set_credentials__401_response(self, dummy_api):
        with pytest.raises(AylaAuthError) as e:
            dummy_api._set_credentials(401, {"error": {"message": "Unauthorized"}})
        assert e.value.args[0] == "Unauthorized"

    def test_set_credentials__valid_response(self, dummy_api):
        assert dummy_api._access_token is "token123"
        assert dummy_api._refresh_token is "token321"
        assert dummy_api._auth_expiration.timestamp() == pytest.approx(
            (datetime.now() + timedelta(seconds=700)).timestamp()
        )
        assert dummy_api._is_authed == True

        t1 = datetime.now() + timedelta(seconds=3600)
        dummy_api._set_credentials(
            200,
            {
                "access_token": "token123",
                "refresh_token": "token321",
                "expires_in": 3600,
            },
        )

        assert dummy_api._access_token == "token123"
        assert dummy_api._refresh_token == "token321"
        assert dummy_api._auth_expiration.timestamp() == pytest.approx(t1.timestamp())
        assert dummy_api._is_authed == True

    def test_property__sign_out_data(self, dummy_api):
        assert dummy_api.sign_out_data == {
            "user": {"access_token": dummy_api._access_token}
        }

    def test_clear_auth(self, dummy_api):
        assert dummy_api._is_authed == True

        dummy_api._clear_auth()

        assert dummy_api._access_token is None
        assert dummy_api._refresh_token is None
        assert dummy_api._auth_expiration is None
        assert dummy_api._is_authed == False

    def test_property__auth_expiration__not_authed(self, dummy_api):
        dummy_api._is_authed = False
        dummy_api._auth_expiration = None

        assert dummy_api.auth_expiration is None

    def test_property__auth_expiration__no_expiration(self, dummy_api):
        # mock the invalid state
        dummy_api._is_authed = True
        dummy_api._auth_expiration = None

        # Check that the correct exception is raised when accessing property
        with pytest.raises(AylaNotAuthedError) as e:
            _ = dummy_api.auth_expiration
        assert e.value.args[0] == "Invalid state.  Please reauthorize."

    def test_property__auth_expiration__not_authed(self, dummy_api):
        dummy_api._is_authed = True
        t = datetime.now() + timedelta(seconds=3600)
        dummy_api._auth_expiration = t

        assert dummy_api.auth_expiration == t

    def test_property__token_expired__false(self, dummy_api):
        dummy_api._is_authed = True
        dummy_api._auth_expiration = datetime.now() + timedelta(seconds=3600)
        assert dummy_api.token_expired == False

    def test_property__token_expired__true(self, dummy_api):
        dummy_api._is_authed = True
        dummy_api._auth_expiration = datetime.now() - timedelta(seconds=3600)
        assert dummy_api.token_expired == True

    def test_property__token_expired__not_authed(self, dummy_api):
        dummy_api._is_authed = False
        dummy_api._auth_expiration = datetime.now() + timedelta(seconds=3600)
        assert dummy_api.token_expired == True

    def test_property__token_expiring_soon__false(self, dummy_api):
        dummy_api._is_authed = True
        # "soon" is considered to be within 600 seconds from the current time
        dummy_api._auth_expiration = datetime.now() + timedelta(seconds=605)
        assert dummy_api.token_expiring_soon == False

    def test_property__token_expiring_soon__true(self, dummy_api):
        dummy_api._is_authed = True
        dummy_api._auth_expiration = datetime.now() + timedelta(seconds=595)
        assert dummy_api.token_expiring_soon == True

    def test_property__token_expiring_soon__not_authed(self, dummy_api):
        dummy_api._is_authed = False
        dummy_api._auth_expiration = datetime.now() + timedelta(seconds=3600)
        assert dummy_api.token_expiring_soon == True

    @pytest.mark.parametrize(
        "access_token,auth_state,auth_timedelta",
        [
            ("token123", True, timedelta(seconds=-100)),  # auth expiry passed
            (None, True, timedelta(seconds=700)),  # invalid token
            ("token123", False, timedelta(seconds=-100)),  # not authed
        ],
    )
    def test_check_auth__not_authed(
        self, dummy_api, access_token, auth_state, auth_timedelta
    ):
        dummy_api._access_token = access_token
        dummy_api._is_authed = auth_state
        dummy_api._auth_expiration = datetime.now() + auth_timedelta

        with pytest.raises(AylaNotAuthedError) as e:
            dummy_api.check_auth()

        assert e.value.args[0] == NOT_AUTHED_MESSAGE
        assert dummy_api._is_authed == False

    def test_check_auth__expiring_soon_exception(self, dummy_api):
        dummy_api._auth_expiration = datetime.now() + timedelta(seconds=400)

        with pytest.raises(AylaAuthExpiringError) as e:
            dummy_api.check_auth(raise_expiring_soon=True)

        assert e.value.args[0] == AUTH_EXPIRED_MESSAGE

        # No exception raised when set to False
        dummy_api.check_auth(raise_expiring_soon=False)

    def test_check_auth__valid(self, dummy_api):
        assert dummy_api.check_auth() is None

    def test_auth_header(self, dummy_api):
        dummy_api._access_token = "myfaketoken"
        assert dummy_api.auth_header == {
            "Authorization": "auth_token myfaketoken"
        }

    def test_get_headers__no_kwargs(self, dummy_api):
        headers = dummy_api._get_headers({})
        assert headers == dummy_api.auth_header

    def test_get_headers__kwargs_(self, dummy_api):
        headers = dummy_api._get_headers({"headers": {"X-Test": "val"}})

        assert headers == {
            "X-Test": "val",
            "Authorization": f"auth_token {dummy_api._access_token}"
        }