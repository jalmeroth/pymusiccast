#!/usr/bin/env python
"""This is a docstring."""
import logging

from .const import ENDPOINTS, STATE_OFF, STATE_ON, GROUP_ID_NULL
from .helpers import request

_LOGGER = logging.getLogger(__name__)


class Zone(object):
    """Represent a devices' Zone."""

    def __init__(self, receiver, zone_id="main"):
        """Initialize the zone."""
        super(Zone, self).__init__()
        self._status = None
        self._dist_info = {}
        self._zone_id = zone_id
        self._receiver = receiver
        self._yamaha = None
        self._ip_address = self.receiver.ip_address
        self._status_sent = None

    @property
    def status(self):
        """Return status."""
        return self._status

    @status.setter
    def status(self, stat):
        self._status = stat

    @property
    def dist_info(self):
        """Return distribution_info."""
        return self._dist_info

    @dist_info.setter
    def dist_info(self, dist_info):
        self._dist_info = dist_info

    @property
    def group_id(self):
        """Return the distribution group id."""
        return self._dist_info.get("group_id") or GROUP_ID_NULL

    @property
    def group_is_server(self):
        """Return true if this zone believes it is a server."""
        return (
            self._dist_info.get("role") == "server" and self.group_id != GROUP_ID_NULL
        )

    @property
    def group_clients(self):
        """Return the ip address of distribution group clients."""
        if not self.group_is_server:
            return []
        if self._dist_info.get("client_list") is None:
            return []
        return [e.get("ip_address") for e in self._dist_info.get("client_list")]

    @property
    def zone_id(self):
        """Return the zone_id."""
        return self._zone_id

    @property
    def receiver(self):
        """Return the receiver."""
        return self._receiver

    @property
    def ip_address(self):
        """Return the ip_address."""
        return self._ip_address

    @property
    def source_list(self):
        """Return source_list."""
        return self._yamaha.source_list

    @source_list.setter
    def source_list(self, source_list):
        """Set source_list."""
        self._yamaha.source_list = source_list

    def handle_message(self, message):
        """Process UDP messages."""
        if self._yamaha:
            if "power" in message:
                _LOGGER.debug("%s: Power: %s", self._ip_address, message.get("power"))
                self._yamaha.power = (
                    STATE_ON if message.get("power") == "on" else STATE_OFF
                )
            if "input" in message:
                _LOGGER.debug("%s: Input: %s", self._ip_address, message.get("input"))
                self._yamaha._source = message.get("input")
            if "sound_program" in message:
                _LOGGER.debug(
                    "%s: Sound Program: %s",
                    self._ip_address,
                    message.get("sound_program"),
                )
                self._yamaha._sound_mode = message.get("sound_program")
            if "volume" in message:
                volume = message.get("volume")

                if "max_volume" in message:
                    volume_max = message.get("max_volume")
                else:
                    volume_max = self._yamaha.volume_max

                _LOGGER.debug(
                    "%s: Volume: %d / Max: %d", self._ip_address, volume, volume_max
                )

                self._yamaha.volume = volume / volume_max
                self._yamaha.volume_max = volume_max
            if "mute" in message:
                _LOGGER.debug("%s: Mute: %s", self._ip_address, message.get("mute"))
                self._yamaha.mute = message.get("mute", False)
        else:
            _LOGGER.debug("%s: No yamaha-obj found", self._ip_address)

    def update_status(self, new_status=None):
        """Update the zone status."""
        _LOGGER.debug("%s: update_status: Zone %s", self._ip_address, self.zone_id)

        if self.status and new_status is None:
            _LOGGER.debug("%s: Zone: healthy.", self._ip_address)
        else:
            old_status = self.status or {}

            if new_status:
                # merge new_status with existing for comparison
                _LOGGER.debug("%s: Set status: provided", self._ip_address)

                # make a copy of the old_status
                status = old_status.copy()

                # merge updated items into status
                status.update(new_status)

                # promote merged_status to new_status
                new_status = status
            else:
                _LOGGER.debug("%s: Set status: own", self._ip_address)
                new_status = self.get_status()

            _LOGGER.debug("%s: old_status: %s", self._ip_address, old_status)
            _LOGGER.debug("%s: new_status: %s", self._ip_address, new_status)
            _LOGGER.debug(
                "%s: is_equal: %s", self._ip_address, old_status == new_status
            )

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
        """Get status from device."""
        req_url = ENDPOINTS["getStatus"].format(self.ip_address, self.zone_id)
        return request(req_url)

    def set_yamaha_device(self, yamaha_device):
        """Set reference to device in HASS."""
        _LOGGER.debug("%s: setYamahaDevice: %s", self._ip_address, yamaha_device)
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

    def update_dist_info(self, new_dist=None):
        """Get distribution info from device and update zone."""
        _LOGGER.debug("%s: update_dist_info: Zone %s", self.ip_address, self.zone_id)
        if new_dist is None:
            return
        print(new_dist)
        group_members = new_dist.get("group_members")
        self._yamaha.group_members = group_members
        self._status_sent = self.update_hass()

    @property
    def sound_mode_list(self):
        """Return sound_mode_list."""
        return self._yamaha.sound_mode_list

    @sound_mode_list.setter
    def sound_mode_list(self, sound_mode_list):
        """Sets sound_mode_list."""
        self._yamaha.sound_mode_list = sound_mode_list

    def set_sound_program(self, sound_program):
        """Send sound program command."""
        req_url = ENDPOINTS["setSoundProgram"].format(
            self.ip_address, self.zone_id, sound_program
        )
        params = {"program": sound_program}
        return request(req_url, params=params)
