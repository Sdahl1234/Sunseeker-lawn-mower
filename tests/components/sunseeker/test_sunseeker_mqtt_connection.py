"""Tests for Sunseeker MQTT connection and credential handling."""

import base64
import json
from queue import Queue
from threading import Timer
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import paho.mqtt.client as mqtt
import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _controller(
    apptype: str,
    model: str,
    region: str = "EU",
    store_password: MagicMock | None = None,
) -> object:
    """Construct a controller without connecting to a broker."""
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
    )

    mower = SimpleNamespace(language="en", debug=False, robotList=[])
    return SunseekermqttController(
        mower,
        "mower-user",
        "user-123",
        "access-token",
        region,
        apptype,
        model,
        "https://api.example",
        "app-id",
        mqtt_password="stored-password",
        store_mqtt_password=store_password,
    )


async def test_start_mqtt_selects_old_and_new_transports() -> None:
    """Test old accounts use legacy MQTT and new accounts upload before connecting."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_NEW,
        APPTYPE_OLD,
        MODEL_OLD,
        MODEL_X,
    )

    old_controller = _controller(APPTYPE_OLD, MODEL_OLD)
    old_controller.connect_mqtt = MagicMock()
    old_controller.upload_password = MagicMock()
    old_controller.connect_mqtt_new = MagicMock()
    old_controller.Start_mqtt()

    old_controller.connect_mqtt.assert_called_once_with()
    old_controller.upload_password.assert_not_called()
    old_controller.connect_mqtt_new.assert_not_called()

    new_controller = _controller(APPTYPE_NEW, MODEL_X)
    new_controller.password_uploaded = False
    new_controller.upload_password = MagicMock()
    new_controller.connect_mqtt = MagicMock()
    new_controller.connect_mqtt_new = MagicMock()
    new_controller.Start_mqtt()

    new_controller.upload_password.assert_called_once_with()
    new_controller.connect_mqtt_new.assert_called_once_with()
    new_controller.connect_mqtt.assert_not_called()


@pytest.mark.parametrize(
    ("region", "model", "expected_host", "expected_port"),
    [
        pytest.param(
            "EU", "X models", "wfsmqtt-specific.sk-robot.com", 1884, id="x-eu"
        ),
        pytest.param(
            "US", "S models", "wfsmqtt-specific-us.sk-robot.com", 1884, id="s-us"
        ),
        pytest.param(
            "EU", "V1 models", "app.mqttv1-eu.sk-robot.com", 32884, id="v1-eu"
        ),
        pytest.param(
            "US", "V1 models", "app.mqttv1-us.sk-robot.com", 32884, id="v1-us"
        ),
    ],
)
async def test_new_broker_region_and_model_routing(
    region: str, model: str, expected_host: str, expected_port: int
) -> None:
    """Test new MQTT models select regional hosts and V1-specific ports."""
    from custom_components.sunseeker.const import APPTYPE_NEW  # noqa: PLC0415

    controller = _controller(APPTYPE_NEW, model, region)
    client = MagicMock()
    with patch(
        "custom_components.sunseeker.sunseeker_mqtt.mqtt.Client",
        return_value=client,
    ) as client_factory:
        controller.connect_mqtt_new()

    client_factory.assert_called_once_with(
        client_id=controller.client_id + "new", protocol=mqtt.MQTTv311
    )
    client.username_pw_set.assert_called_once_with(
        "mower-userapp-id", "stored-password"
    )
    client.tls_set.assert_called_once()
    client.connect.assert_called_once_with(
        host=expected_host,
        keepalive=60,
        port=expected_port,
    )
    client.loop_start.assert_called_once_with()


async def test_rsa_mqtt_password_encryption_round_trip() -> None:
    """Test uploaded MQTT credentials decrypt to the original password."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    controller = _controller(APPTYPE_NEW, MODEL_X)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    encrypted = controller.encrypt_rsa_base64("mqtt-password", public_key)
    decrypted = private_key.decrypt(
        base64.b64decode(encrypted),
        padding.PKCS1v15(),
    ).decode()

    assert decrypted == "mqtt-password"


async def test_edit_mqtt_password_request() -> None:
    """Test the account API request used to upload an encrypted MQTT password."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    controller = _controller(APPTYPE_NEW, MODEL_X)
    response = MagicMock(status=200)
    response.read.return_value = b"ok"

    with patch("custom_components.sunseeker.sunseeker_mqtt.re.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value = response
        controller.edit_password_mqtt("encrypted-password")

    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.example/admin/user/edit"
    assert request.get_method() == "PUT"
    assert json.loads(request.data) == {
        "appIdCode": "app-id",
        "appType": 3,
        "appVersion": "1.7.0",
        "mqttsPassword": "encrypted-password",
        "operatingSystemCode": "android",
    }
    assert request.get_header("Authorization") == "bearer access-token"


async def test_upload_password_marks_credentials_uploaded() -> None:
    """Test password upload encrypts the current password and records success."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    controller = _controller(APPTYPE_NEW, MODEL_X)
    controller.encrypt_rsa_base64 = MagicMock(return_value="ciphertext")
    controller.edit_password_mqtt = MagicMock()
    controller.password_uploaded = False

    controller.upload_password()

    controller.encrypt_rsa_base64.assert_called_once_with(
        "stored-password", controller.public_key
    )
    controller.edit_password_mqtt.assert_called_once_with("ciphertext")
    assert controller.password_uploaded is True


async def test_new_mqtt_connection_subscribes_and_stores_accepted_password() -> None:
    """Test successful MQTT authentication subscribes and persists the password."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    store_password = MagicMock()
    controller = _controller(APPTYPE_NEW, MODEL_X, store_password=store_password)
    controller.mqtt_client_new = MagicMock()
    controller._password_retries = 2

    controller.on_mqtt_connect_new(controller.mqtt_client_new, None, None, 0)

    assert controller._password_retries == 0
    store_password.assert_called_once_with("stored-password")
    controller.mqtt_client_new.subscribe.assert_called_once_with(
        "/wirelessdevice/user-123/get", qos=0
    )


async def test_v1_success_subscribes_to_wireless_mower_topic() -> None:
    """Test V1 MQTT uses its dedicated topic family."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_V1  # noqa: PLC0415

    controller = _controller(APPTYPE_NEW, MODEL_V1)
    controller.mqtt_client_new = MagicMock()

    controller.on_mqtt_connect_new(controller.mqtt_client_new, None, None, 0)

    controller.mqtt_client_new.subscribe.assert_called_once_with(
        "/wirelessmower/user-123/get", qos=0
    )


async def test_rejected_credentials_schedule_password_retry() -> None:
    """Test rejected custom credentials schedule a delayed password renewal."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        PASSWORD_RETRY_DELAY,
    )

    controller = _controller(APPTYPE_NEW, MODEL_X)
    client = MagicMock()
    with patch(
        "custom_components.sunseeker.sunseeker_mqtt.DaemonTimer", autospec=True
    ) as timer_class:
        controller.on_mqtt_connect_new(client, None, None, 5)

    client.disconnect.assert_called_once_with()
    assert controller._password_retries == 1
    timer_class.assert_called_once_with(
        PASSWORD_RETRY_DELAY, controller._reconnect_with_new_password
    )
    controller._password_retry_timer.start.assert_called_once_with()


async def test_repeated_rejection_falls_back_to_shared_login() -> None:
    """Test repeated custom password rejection switches to fallback credentials."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        MAX_PASSWORD_RETRIES,
    )

    controller = _controller(APPTYPE_NEW, MODEL_X)
    controller._password_retries = MAX_PASSWORD_RETRIES
    controller._retry_with_fallback_login = MagicMock()
    client = MagicMock()

    controller.on_mqtt_connect_new(client, None, None, 4)

    client.disconnect.assert_called_once_with()
    assert controller._using_fallback is True
    controller._retry_with_fallback_login.assert_called_once_with()


async def test_fallback_rejection_uses_long_cooldown() -> None:
    """Test rejected fallback credentials reset retries and enter cooldown."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_V1  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        PASSWORD_RETRY_COOLDOWN,
    )

    controller = _controller(APPTYPE_NEW, MODEL_V1)
    controller._using_fallback = True
    controller._password_retries = 3
    client = MagicMock()
    with patch(
        "custom_components.sunseeker.sunseeker_mqtt.DaemonTimer", autospec=True
    ) as timer_class:
        controller.on_mqtt_connect_new(client, None, None, 5)

    assert controller._using_fallback is False
    assert controller._password_retries == 0
    timer_class.assert_called_once_with(
        PASSWORD_RETRY_COOLDOWN, controller._reconnect_with_new_password
    )
    controller._password_retry_timer.start.assert_called_once_with()


async def test_unload_stops_clients_and_queues() -> None:
    """Test unload stops both MQTT clients and sends worker sentinels."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    controller = _controller(APPTYPE_NEW, MODEL_X)
    legacy_client = MagicMock()
    new_client = MagicMock()
    controller.mqtt_client = legacy_client
    controller.mqtt_client_new = new_client
    device_queue: Queue = Queue()
    controller._device_queues["serial-1"] = device_queue
    timer = MagicMock(spec=Timer)
    controller._password_retry_timer = timer

    controller.unload()

    assert controller._unloading is True
    assert device_queue.get_nowait() is None
    timer.cancel.assert_called_once_with()
    assert controller._password_retry_timer is None
    legacy_client.disconnect.assert_called_once_with()
    legacy_client.loop_stop.assert_called_once_with()
    new_client.disconnect.assert_called_once_with()
    new_client.loop_stop.assert_called_once_with()
