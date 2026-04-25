"""Diagnostics support for Sunseeker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import SunseekerDataCoordinator
from .const import DATAHANDLER, DOMAIN, ROBOTS

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "username",
    "user_id",
    "userid",
    "access_token",
    "refresh_token",
    "authorization",
    "Authorization",
    "token",
    "appId",
    "deviceSn",
    "deviceId",
    "devicesn",
    "serial_number",
    "serialNumber",
    "ipAddr",
    "DeviceWifiAddress",
    "DeviceBluetooth",
    "bluetoothMac",
    "base_sn",
    "stationSn",
}


def _coordinator_from_device(
    coordinators: list[SunseekerDataCoordinator], device: DeviceEntry
) -> SunseekerDataCoordinator | None:
    """Find the coordinator for a Home Assistant device entry."""
    for identifier_domain, identifier in device.identifiers:
        if identifier_domain != DOMAIN:
            continue
        for coordinator in coordinators:
            if identifier in (
                coordinator.unique_id,
                f"{DOMAIN}-{coordinator.devicesn}",
            ):
                return coordinator

    if device.serial_number:
        for coordinator in coordinators:
            if coordinator.devicesn == device.serial_number:
                return coordinator

    return None


def _build_device_payload(coordinator: SunseekerDataCoordinator) -> dict[str, Any]:
    """Build diagnostics payload for a single mower/device."""
    device = coordinator.device
    return {
        "coordinator": {
            "devicesn": coordinator.devicesn,
            "unique_id": coordinator.unique_id,
            "model": coordinator.model,
            "apptype": coordinator.apptype,
            "region": coordinator.region,
            "brand": coordinator.brand,
            "schedulefilepath": coordinator.schedulefilepath,
            "heatimagefilepath": coordinator.heatimagefilepath,
            "wifiimagefilepath": coordinator.wifiimagefilepath,
        },
        "device": {
            "devicesn": device.devicesn,
            "deviceId": device.deviceId,
            "DeviceName": device.DeviceName,
            "DeviceModel": device.DeviceModel,
            "ModelName": device.ModelName,
            "model": device.model,
            "apptype": device.apptype,
            "url": device.url,
            "host": device.host,
            "cmdurl": device.cmdurl,
            "deviceOnlineFlag": device.deviceOnlineFlag,
            "error_text": device.error_text,
            "map": {
                "mapid": device.map.mapid,
                "has_image_data": bool(device.map.image_data),
                "has_path_data": bool(device.map.mappathdata),
                "heatmap_url": device.map.heatmap_url,
                "wifimap_url": device.map.wifimap_url,
            },
            "devicedata": device.devicedata,
            "settings": device.settings,
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    data_handler = entry_data.get(DATAHANDLER)
    coordinators: list[SunseekerDataCoordinator] = entry_data.get(ROBOTS, [])

    payload: dict[str, Any] = {
        "config_entry": config_entry.as_dict(),
        "data_handler": {
            "brand": data_handler.brand if data_handler else None,
            "apptype": data_handler.apptype if data_handler else None,
            "region": data_handler.region if data_handler else None,
            "url": data_handler.url if data_handler else None,
            "host": data_handler.host if data_handler else None,
            "deviceArray": data_handler.deviceArray if data_handler else [],
            "session": data_handler.session if data_handler else {},
            "devicelist_OLD_models": (
                data_handler.devicelist_OLD_models if data_handler else {}
            ),
            "devicelist_V_models": data_handler.devicelist_V_models
            if data_handler
            else {},
            "devicelist_X_models": data_handler.devicelist_X_models
            if data_handler
            else {},
        },
        "devices": [_build_device_payload(coordinator) for coordinator in coordinators],
    }

    return async_redact_data(payload, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators: list[SunseekerDataCoordinator] = entry_data.get(ROBOTS, [])
    coordinator = _coordinator_from_device(coordinators, device)

    if coordinator is None:
        return {}

    payload = {
        "config_entry": config_entry.as_dict(),
        "device": _build_device_payload(coordinator),
    }

    return async_redact_data(payload, TO_REDACT)
