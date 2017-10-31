#!/usr/bin/env python
"""This file holds helper functions."""
import json
import time
import logging
import requests
_LOGGER = logging.getLogger(__name__)


def request(url, *args, **kwargs):
    """Do the HTTP Request and return data"""
    method = kwargs.get('method', 'GET')
    timeout = kwargs.pop('timeout', 10)  # hass default timeout
    req = requests.request(method, url, *args, timeout=timeout, **kwargs)
    data = req.json()
    _LOGGER.debug(json.dumps(data))
    return data


def message_worker(device):
    """Loop through messages and pass them on to right device"""
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

            if 'device_id' in data:
                device_id = data.get('device_id')
                if device_id == device.device_id:
                    device.handle_event(data)
                else:
                    _LOGGER.warning("Received message for unknown device.")
            msg_q.task_done()

        time.sleep(0.2)


def socket_worker(sock, msg_q):
    """Socket Loop that fills message queue"""
    _LOGGER.debug("Starting Socket Thread.")
    while True:
        try:
            data, addr = sock.recvfrom(1024)    # buffer size is 1024 bytes
        except OSError as err:
            _LOGGER.error(err)
        else:
            _LOGGER.debug("received message: %s from %s", data, addr)
            msg_q.put(data)
        time.sleep(0.2)
