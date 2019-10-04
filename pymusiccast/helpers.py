#!/usr/bin/env python
"""This file holds helper functions."""
import json
import logging
import os
import time
from urllib.parse import urlparse

import requests

from .const import ENDPOINTS

_LOGGER = logging.getLogger(__name__)
_FAKE_FILE = os.environ.get("FAKE_DATA_FILE")
_FAKE_DATA = {}
_RESP_OK = {"response_code": 0}


def fake_response(method, url, *args, **kwargs):
    """Inject fake response for URL."""
    _LOGGER.debug("%s: %s (%s / %s)", method, url, args, kwargs)
    global _FAKE_FILE, _FAKE_DATA

    if not _FAKE_FILE:
        _LOGGER.debug("No FAKE_DATA specified.")
        return

    if not _FAKE_DATA:
        fake_file = os.path.expanduser(_FAKE_FILE)
        with open(fake_file, "rb") as fake:
            _FAKE_DATA = json.load(fake)

    result = None
    urlparsed = urlparse(url)
    ip_address = urlparsed.netloc
    serv_path = urlparsed.path

    if method == "GET" and "params" in kwargs:
        data = kwargs.get("params")
        if serv_path.endswith(("setPower", "setVolume", "setInput", "setMute")):
            obj_key = ENDPOINTS["getStatus"].format(ip_address, "main")
            _LOGGER.debug("%s: %s", serv_path, obj_key)
            _FAKE_DATA[obj_key].update(data)
        result = _RESP_OK
    elif method == "POST":
        result = _RESP_OK
    else:
        result = _FAKE_DATA.get(url)
    return result


def request(url, *args, **kwargs):
    """Do the HTTP Request and return data."""
    method = kwargs.pop("method", "GET")
    timeout = kwargs.pop("timeout", 10)  # hass default timeout
    try:
        request = requests.request(method, url, *args, timeout=timeout, **kwargs)
    except requests.exceptions.ConnectionError:
        _LOGGER.debug(url)
        data = fake_response(method, url, *args, **kwargs)
    else:
        data = request.json()
    urlparsed = urlparse(url)
    ip_address = urlparsed.netloc
    _LOGGER.debug("%s: %s", ip_address, json.dumps(data))
    return data


def message_worker(device):
    """Loop through messages and pass them on to right device."""
    _LOGGER.debug("Starting Worker Thread.")
    msg_q = device.messages

    while True:

        if not msg_q.empty():
            message = msg_q.get()

            data = {}
            try:
                data = json.loads(message.decode("utf-8"))
            except ValueError:
                _LOGGER.error("Received invalid message: %s", message)

            if "device_id" in data:
                device_id = data.get("device_id")
                if device_id == device.device_id:
                    device.handle_event(data)
                else:
                    _LOGGER.warning(
                        "%s: Received message for unknown device.", device.ip_address
                    )
            msg_q.task_done()
        time.sleep(0.2)


def socket_worker(sock, msg_q):
    """Socket Loop that fills message queue."""
    _LOGGER.debug("Starting Socket Thread.")
    while True:
        try:
            data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
        except OSError as err:
            _LOGGER.error(err)
        else:
            _LOGGER.debug("%s received message: %s", addr[0], data)
            msg_q.put(data)
        time.sleep(0.2)
