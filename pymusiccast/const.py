#!/usr/bin/env python
"""This file defines constants."""

ENDPOINTS = {
    "getDeviceInfo": "http://{}/YamahaExtendedControl/v1/system/getDeviceInfo",
    "getDistributionInfo": (
        "http://{}/YamahaExtendedControl/v1/dist/getDistributionInfo"
    ),
    "getFeatures": "http://{}/YamahaExtendedControl/v1/system/getFeatures",
    "getLocationInfo": "http://{}/YamahaExtendedControl/v1/system/getLocationInfo",
    "getNetworkStatus": "http://{}/YamahaExtendedControl/v1/system/getNetworkStatus",
    "getPlayInfo": "http://{}/YamahaExtendedControl/v1/netusb/getPlayInfo",
    "getStatus": "http://{}/YamahaExtendedControl/v1/{}/getStatus",
    "setClientInfo": "http://{}/YamahaExtendedControl/v1/dist/setClientInfo",
    "setGroupName": "http://{}/YamahaExtendedControl/v1/dist/setGroupName",
    "setInput": "http://{}/YamahaExtendedControl/v1/{}/setInput",
    "setMute": "http://{}/YamahaExtendedControl/v1/{}/setMute",
    "setPlayback": "http://{}/YamahaExtendedControl/v1/netusb/setPlayback",
    "setPower": "http://{}/YamahaExtendedControl/v1/{}/setPower",
    "setServerInfo": "http://{}/YamahaExtendedControl/v1/dist/setServerInfo",
    "setVolume": "http://{}/YamahaExtendedControl/v1/{}/setVolume",
    "startDistribution": "http://{}/YamahaExtendedControl/v1/dist/startDistribution",
    "stopDistribution": "http://{}/YamahaExtendedControl/v1/dist/stopDistribution",
}

STATE_UNKNOWN = "unknown"
STATE_ON = "on"
STATE_OFF = "off"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_IDLE = "idle"

GROUP_ID_NULL = 32 * "0"
DOMAIN = "yamaha_musiccast"
