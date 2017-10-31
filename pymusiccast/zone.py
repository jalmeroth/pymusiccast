#!/usr/bin/env python
"""This is a docstring."""
import logging
from homeassistant.const import (
    STATE_ON, STATE_OFF
)
from .const import ENDPOINTS
from .helpers import request
_LOGGER = logging.getLogger(__name__)


class Zone(object):
    """docstring for Zone"""
    def __init__(self, receiver, zone_id='main'):
        super(Zone, self).__init__()
        self._status = None
        self._zone_id = zone_id
        self._receiver = receiver
        self._yamaha = None
        self._ip_address = self.receiver.ip_address
        self._status_sent = None

    @property
    def status(self):
        """Returns status."""
        return self._status

    @status.setter
    def status(self, stat):
        self._status = stat

    @property
    def zone_id(self):
        """Returns the zone_id."""
        return self._zone_id

    @property
    def receiver(self):
        """Returns the receiver."""
        return self._receiver

    @property
    def ip_address(self):
        """Returns the ip_address."""
        return self._ip_address

    @property
    def source_list(self):
        """Return source_list."""
        return self._yamaha.source_list

    @source_list.setter
    def source_list(self, source_list):
        """Sets source_list."""
        self._yamaha.source_list = source_list

    def handle_message(self, message):
        """Process UDP messages"""
        if self._yamaha:
            if 'power' in message:
                _LOGGER.debug("Power: %s", message.get('power'))
                self._yamaha.power = (
                    STATE_ON if message.get('power') == "on" else STATE_OFF)
            if 'input' in message:
                _LOGGER.debug("Input: %s", message.get('input'))
                self._yamaha._source = message.get('input')
            if 'volume' in message:
                volume = message.get('volume')

                if 'max_volume' in message:
                    volume_max = message.get('max_volume')
                else:
                    volume_max = self._yamaha.volume_max

                _LOGGER.debug("Volume: %d / Max: %d", volume, volume_max)

                self._yamaha.volume = volume / volume_max
                self._yamaha.volume_max = volume_max
            if 'mute' in message:
                _LOGGER.debug("Mute: %s", message.get('mute'))
                self._yamaha.mute = message.get('mute', False)
        else:
            _LOGGER.debug("No yamaha-obj found")

    def update_status(self, new_status=None):
        """Updates the zone status."""
        _LOGGER.debug("update_status: Zone %s", self.zone_id)

        if self.status and new_status is None:
            _LOGGER.debug("Zone: healthy.")
        else:
            old_status = self.status or {}

            if new_status:
                # merge new_status with existing for comparison
                _LOGGER.debug("Set status: provided")

                # make a copy of the old_status
                status = old_status.copy()

                # merge updated items into status
                status.update(new_status)

                # promote merged_status to new_status
                new_status = status
            else:
                _LOGGER.debug("Set status: own")
                new_status = self.get_status()

            _LOGGER.debug("old_status: %s", old_status)
            _LOGGER.debug("new_status: %s", new_status)
            _LOGGER.debug("is_equal: %s", old_status == new_status)

            if new_status != old_status:
                self.handle_message(new_status)
                self._status_sent = False
                self.status = new_status

        if not self._status_sent:
            self._status_sent = self.update_hass()

    def update_hass(self):
        """Update HASS."""
        return self._yamaha.update_hass() if self._yamaha else False

    def get_status(self):
        """Get status from device"""
        req_url = ENDPOINTS["getStatus"].format(self.ip_address, self.zone_id)
        return request(req_url)

    def set_yamaha_device(self, yamaha_device):
        """Set reference to device in HASS"""
        _LOGGER.debug("setYamahaDevice: %s", yamaha_device)
        self._yamaha = yamaha_device

    def set_power(self, power):
        """Send Power command."""
        req_url = ENDPOINTS["setPower"].format(self.ip_address, self.zone_id)
        params = {"power": "on" if power else "standby"}
        return request(req_url, params=params)

    def set_mute(self, mute):
        """Send mute command."""
        req_url = ENDPOINTS["setMute"].format(self.ip_address, self.zone_id)
        params = {"enable": "true" if mute else "false"}
        return request(req_url, params=params)

    def set_volume(self, volume):
        """Send Volume command."""
        req_url = ENDPOINTS["setVolume"].format(self.ip_address, self.zone_id)
        params = {"volume": int(volume)}
        return request(req_url, params=params)

    def set_input(self, input_id):
        """Send Input command."""
        req_url = ENDPOINTS["setInput"].format(self.ip_address, self.zone_id)
        params = {"input": input_id}
        return request(req_url, params=params)
