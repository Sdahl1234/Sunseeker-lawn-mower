"""Tests for Sunseeker authentication and token refresh."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _client(apptype: str):
    """Create a client configured for a selected app protocol."""
    from custom_components.sunseeker.const import REGION_EU  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker import (  # noqa: PLC0415
        SunseekerRoboticmower,
    )

    return SunseekerRoboticmower(
        "Sunseeker",
        apptype,
        REGION_EU,
        "user@example.test",
        "plain password",
        "en-us",
        "app-id",
    )


def _urlopen_context(response_data: dict, status: int = 200) -> MagicMock:
    """Build a context manager response for urllib.request.urlopen."""
    response = MagicMock(status=status)
    response.read.return_value = json.dumps(response_data).encode()
    context = MagicMock()
    context.__enter__.return_value = response
    return context


async def test_new_oauth_uses_plaintext_fallback_after_encrypted_rejection() -> None:
    """Test new OAuth retries with plaintext when encrypted password is rejected."""
    from custom_components.sunseeker.const import APPTYPE_NEW  # noqa: PLC0415

    client = _client(APPTYPE_NEW)
    with patch(
        "custom_components.sunseeker.sunseeker.re.urlopen",
        side_effect=[
            _urlopen_context({"error": "invalid encrypted password"}, status=400),
            _urlopen_context({"access_token": "new-token", "refresh_token": "refresh"}),
        ],
    ) as urlopen:
        assert client.login() is True

    requests = [call.args[0] for call in urlopen.call_args_list]
    first_payload, second_payload = [json.loads(request.data) for request in requests]
    assert first_payload["password"] == client.encrypt_oauth_password(client.password)
    assert second_payload["password"] == client.password
    assert first_payload["username"] == second_payload["username"] == client.username
    assert all(request.get_method() == "POST" for request in requests)
    assert client.session == {"access_token": "new-token", "refresh_token": "refresh"}


async def test_new_oauth_success_stops_after_encrypted_request() -> None:
    """Test successful encrypted OAuth authentication does not send fallback."""
    from custom_components.sunseeker.const import APPTYPE_NEW  # noqa: PLC0415

    client = _client(APPTYPE_NEW)
    with patch(
        "custom_components.sunseeker.sunseeker.re.urlopen",
        return_value=_urlopen_context(
            {"access_token": "new-token", "refresh_token": "refresh"}
        ),
    ) as urlopen:
        assert client.login() is True

    urlopen.assert_called_once()
    request = urlopen.call_args.args[0]
    assert json.loads(request.data)["password"] == client.encrypt_oauth_password(
        client.password
    )


@pytest.mark.parametrize(
    "missing", ["username", "password"], ids=["username", "password"]
)
async def test_on_load_skips_login_with_missing_credentials(missing: str) -> None:
    """Test missing credentials do not initiate login or integration setup."""
    from custom_components.sunseeker.const import APPTYPE_OLD  # noqa: PLC0415

    client = _client(APPTYPE_OLD)
    setattr(client, missing, "")
    client.login = MagicMock()
    client.on_after_login = MagicMock()

    client.on_load()

    client.login.assert_not_called()
    client.on_after_login.assert_not_called()


@pytest.mark.parametrize(
    ("apptype", "refresh_method", "http_method"),
    [
        pytest.param("Old app", "refresh_token", "post", id="old-app"),
        pytest.param("New app", "refresh_token_new", "get", id="new-app"),
    ],
)
async def test_refresh_token_updates_devices_controllers_and_timer(
    apptype: str, refresh_method: str, http_method: str
) -> None:
    """Test both refresh APIs propagate access tokens and reschedule expiry."""
    client = _client(apptype)
    client.session = {"refresh_token": "refresh-token", "expires_in": 3600}
    device = SimpleNamespace(devicesn="serial-refresh", access_token="old-device-token")
    controller = SimpleNamespace(access_token="old-mqtt-token")
    client.robotList = [device]
    client.deviceArray = [device.devicesn]
    client.mqtt_controllers = [controller]
    old_refresh_timeout = MagicMock()
    old_refresh_interval = MagicMock()
    client.refresh_token_timeout = old_refresh_timeout
    client.refresh_token_interval = old_refresh_interval
    response = MagicMock()
    response.json.return_value = {
        "access_token": "refreshed-token",
        "refresh_token": "rotated-refresh-token",
        "expires_in": 7200,
    }
    timer = MagicMock()

    with (
        patch(
            f"custom_components.sunseeker.sunseeker.requests.{http_method}",
            return_value=response,
        ) as request,
        patch(
            "custom_components.sunseeker.sunseeker.DaemonTimer", return_value=timer
        ) as timer_class,
    ):
        getattr(client, refresh_method)()

    assert client.session["access_token"] == "refreshed-token"
    assert client.session["refresh_token"] == "rotated-refresh-token"
    assert device.access_token == "refreshed-token"
    assert controller.access_token == "refreshed-token"
    if refresh_method == "refresh_token":
        old_refresh_timeout.cancel.assert_called_once_with()
    old_refresh_interval.cancel.assert_called_once_with()
    timer_class.assert_called_once_with(7200, getattr(client, refresh_method))
    timer.start.assert_called_once_with()
    if http_method == "post":
        assert request.call_args.kwargs["data"] == {
            "grant_type": "refresh_token",
            "refresh_token": "refresh-token",
            "scope": "server",
        }
    else:
        assert "refresh_token=refresh-token" in request.call_args.kwargs["url"]


async def test_refresh_token_does_not_schedule_after_unload() -> None:
    """Test refresh updates are not rescheduled once the client is unloaded."""
    from custom_components.sunseeker.const import APPTYPE_OLD  # noqa: PLC0415

    client = _client(APPTYPE_OLD)
    client.session = {"refresh_token": "refresh-token"}
    client._unloaded = True
    client.refresh_token_interval = MagicMock()
    response = MagicMock()
    response.json.return_value = {"access_token": "refreshed-token"}

    with (
        patch(
            "custom_components.sunseeker.sunseeker.requests.post",
            return_value=response,
        ),
        patch("custom_components.sunseeker.sunseeker.DaemonTimer") as timer_class,
    ):
        client.refresh_token()

    client.refresh_token_interval.cancel.assert_not_called()
    timer_class.assert_not_called()


@pytest.mark.parametrize(
    ("apptype", "model", "expected_suffix", "list_attribute"),
    [
        pytest.param(
            "Old app",
            "Old models",
            "/mower/device-user/list",
            "devicelist_OLD_models",
            id="old",
        ),
        pytest.param(
            "New app",
            "MODEL_SXV",
            "/app_wireless_mower/device-user/getCustomDevice?all=true",
            "devicelist_NEW_models",
            id="new",
        ),
    ],
)
async def test_get_device_list_routes_and_caches_response(
    apptype: str, model: str, expected_suffix: str, list_attribute: str
) -> None:
    """Test old and wireless device discovery use their own endpoint and cache."""
    client = _client(apptype)
    client.session = {"access_token": "token"}
    response_data = {"code": 0, "data": []}
    response = MagicMock()
    response.json.return_value = response_data
    with patch(
        "custom_components.sunseeker.sunseeker.requests.get",
        return_value=response,
    ) as get:
        assert client.get_device_list(apptype, model) == response_data

    assert get.call_args.kwargs["url"].endswith(expected_suffix)
    assert getattr(client, list_attribute) == response_data


async def test_get_device_list_rejected_response_is_cached_but_not_returned() -> None:
    """Test rejected list responses are retained for diagnostics and return None."""
    from custom_components.sunseeker.const import APPTYPE_NEW  # noqa: PLC0415

    client = _client(APPTYPE_NEW)
    client.session = {"access_token": "token"}
    response = MagicMock()
    response.json.return_value = {"code": 9, "msg": "denied", "data": []}
    with patch(
        "custom_components.sunseeker.sunseeker.requests.get",
        return_value=response,
    ):
        assert client.get_device_list(APPTYPE_NEW, "MODEL_SXV") is None

    assert client.devicelist_NEW_models == {"code": 9, "msg": "denied", "data": []}


@pytest.mark.parametrize(
    ("apptype", "refresh_method"),
    [
        pytest.param("Old app", "refresh_token", id="old"),
        pytest.param("New app", "refresh_token_new", id="new"),
    ],
)
async def test_refresh_token_callback_delays_selected_protocol(
    apptype: str, refresh_method: str
) -> None:
    """Test device auth callbacks cancel old timeout and schedule the right refresh."""
    client = _client(apptype)
    previous_timeout = MagicMock()
    client.refresh_token_timeout = previous_timeout
    timer = MagicMock()
    with patch(
        "custom_components.sunseeker.sunseeker.DaemonTimer", return_value=timer
    ) as timer_class:
        client.refresh_token_callback()

    previous_timeout.cancel.assert_called_once_with()
    timer_class.assert_called_once_with(60, getattr(client, refresh_method))
    timer.start.assert_called_once_with()


async def test_old_app_startup_creates_legacy_mqtt_controller() -> None:
    """Test old-app login starts its mower and one legacy MQTT controller."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        MODEL_OLD,
    )

    client = _client(APPTYPE_OLD)
    client.session = {
        "username": "account-user",
        "user_id": "user-1",
        "access_token": "access-1",
        "expires_in": 600,
    }
    client.get_device_list = MagicMock(
        return_value={
            "data": [
                {
                    "deviceSn": "old-serial",
                    "deviceId": "old-device",
                    "appUserId": "user-1",
                    "deviceModelName": "Legacy mower",
                    "modelName": "Legacy",
                }
            ]
        }
    )
    mqtt_controller = MagicMock()
    timer = MagicMock()

    with (
        patch("custom_components.sunseeker.sunseeker.SunseekerDevice") as device_class,
        patch(
            "custom_components.sunseeker.sunseeker.SunseekermqttController",
            return_value=mqtt_controller,
        ) as mqtt_class,
        patch(
            "custom_components.sunseeker.sunseeker.DaemonTimer", return_value=timer
        ) as timer_class,
    ):
        client.on_after_login()

    assert client.login_ok is True
    assert client.deviceArray == ["old-serial"]
    device_class.return_value.InitDevice.assert_called_once_with()
    client.get_device_list.assert_called_once_with(APPTYPE_OLD, MODEL_OLD)
    assert mqtt_class.call_count == 1
    assert mqtt_class.call_args.args[6] == MODEL_OLD
    mqtt_controller.Start_mqtt.assert_called_once_with()
    timer_class.assert_called_once_with(600, client.refresh_token)
    timer.start.assert_called_once_with()


async def test_mixed_wireless_startup_creates_v1_and_sxv_controllers() -> None:
    """Test mixed V1/X accounts start both MQTT protocol families."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_NEW,
        MODEL_SXV,
        MODEL_V1,
    )

    client = _client(APPTYPE_NEW)
    client.session = {
        "username": "account-user",
        "user_id": "user-2",
        "access_token": "access-2",
        "expires_in": 900,
    }
    client.get_device_list = MagicMock(
        return_value={
            "data": [
                {
                    "deviceSn": "v1-serial",
                    "deviceId": "v1-device",
                    "appUserId": "user-2",
                    "deviceModelName": "V1 mower",
                    "modelName": "V1",
                },
                {
                    "deviceSn": "x-serial",
                    "deviceId": "x-device",
                    "appUserId": "user-2",
                    "deviceModelName": "X7 Gen 2",
                    "modelName": "X7 Gen 2",
                },
            ]
        }
    )
    mqtt_controllers = [MagicMock(), MagicMock()]
    timer = MagicMock()

    with (
        patch("custom_components.sunseeker.sunseeker.SunseekerDevice"),
        patch(
            "custom_components.sunseeker.sunseeker.SunseekermqttController",
            side_effect=mqtt_controllers,
        ) as mqtt_class,
        patch(
            "custom_components.sunseeker.sunseeker.DaemonTimer", return_value=timer
        ) as timer_class,
    ):
        client.on_after_login()

    assert client.deviceArray == ["v1-serial", "x-serial"]
    assert client.need_V1_mqtt is True
    assert client.need_sxv_mqtt is True
    assert [call.args[6] for call in mqtt_class.call_args_list] == [MODEL_V1, MODEL_SXV]
    for mqtt_controller in mqtt_controllers:
        mqtt_controller.Start_mqtt.assert_called_once_with()
    timer_class.assert_called_once_with(900, client.refresh_token_new)
    timer.start.assert_called_once_with()


async def test_empty_device_list_still_schedules_token_refresh() -> None:
    """Test a valid account with no devices starts no MQTT clients but refreshes token."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_NEW,
        MODEL_SXV,
    )

    client = _client(APPTYPE_NEW)
    client.session = {
        "username": "account-user",
        "user_id": "user-3",
        "access_token": "access-3",
        "expires_in": 0,
    }
    client.get_device_list = MagicMock(return_value={"data": []})
    timer = MagicMock()

    with (
        patch(
            "custom_components.sunseeker.sunseeker.SunseekermqttController"
        ) as mqtt_class,
        patch(
            "custom_components.sunseeker.sunseeker.DaemonTimer", return_value=timer
        ) as timer_class,
    ):
        client.on_after_login()

    client.get_device_list.assert_called_once_with(APPTYPE_NEW, MODEL_SXV)
    mqtt_class.assert_not_called()
    assert client.mqtt_controllers == []
    timer_class.assert_called_once_with(3600, client.refresh_token_new)
    timer.start.assert_called_once_with()
