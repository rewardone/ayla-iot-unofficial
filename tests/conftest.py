import pytest
import os
from src.ayla_iot_unofficial.ayla_iot_unofficial import new_ayla_api
from datetime import datetime, timedelta

@pytest.fixture
def dummy_api():
    """AylaApi object with invalid auth creds and attributes populated."""
    username = "myusername@mysite.com"
    password = "mypassword"

    dummy_api = new_ayla_api(username=username, password=password)
    dummy_api._access_token = "token123"
    dummy_api._refresh_token = "token321"
    dummy_api._is_authed = True
    dummy_api._auth_expiration = datetime.now() + timedelta(seconds=700)
    return dummy_api


@pytest.fixture
def sample_api():
    """AylaApi object using user-supplied auth creds via AYLA_USERNAME and 
    AYLA_PASSWORD environement variables."""
    username = os.getenv("AYLA_USERNAME")
    password = os.getenv("AYLA_PASSWORD")

    assert username is not None, "AYLA_USERNAME environment variable unset"
    assert password is not None, "AYLA_PASSWORD environment variable unset"

    return new_ayla_api(username=username, password=password)


@pytest.fixture
def sample_api_logged_in(sample_api):
    """Sample API object with user-supplied creds after performing auth flow."""
    sample_api.sign_in()
    return sample_api