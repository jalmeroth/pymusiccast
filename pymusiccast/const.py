#!/usr/bin/env python
"""This file defines constants."""

ENDPOINTS = {
    "getDeviceInfo": "http://{}/YamahaExtendedControl/v1/system/getDeviceInfo",
    "getFeatures": "http://{}/YamahaExtendedControl/v1/system/getFeatures",
    "getPlayInfo": "http://{}/YamahaExtendedControl/v1/netusb/getPlayInfo",
    "getStatus": "http://{}/YamahaExtendedControl/v1/main/getStatus",
    "setInput": "http://{}/YamahaExtendedControl/v1/main/setInput",
    "setMute": "http://{}/YamahaExtendedControl/v1/main/setMute",
    "setPlayback": "http://{}/YamahaExtendedControl/v1/netusb/setPlayback",
    "setPower": "http://{}/YamahaExtendedControl/v1/main/setPower",
    "setVolume": "http://{}/YamahaExtendedControl/v1/main/setVolume",
}
