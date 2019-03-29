#!/usr/bin/env python
"""This is a docstring."""
import random
import logging
from .const import ENDPOINTS, STATE_ON, STATE_OFF
from .helpers import request_get
_LOGGER = logging.getLogger(__name__)


class Zone(object):
    """docstring for Zone"""
    def __init__(self, receiver, zone_id='main'):
        super(Zone, self).__init__()
        self._status = None
        self._distribution_info = None
        self._zone_id = zone_id
        self._receiver = receiver
        self._yamaha = None
        self._ip_address = self.receiver.ip_address
        self._status_sent = None
        self._group_id = None
        self._group_clients = []

    @property
    def status(self):
        """Returns status."""
        return self._status

    @status.setter
    def status(self, stat):
        self._status = stat

    @property
    def distribution_info(self):
        """Returns distribution_info."""
        return self._distribution_info

    @distribution_info.setter
    def distribution_info(self, stat):
        self._distribution_info = stat

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
        return request_get(req_url)

    def set_yamaha_device(self, yamaha_device):
        """Set reference to device in HASS"""
        _LOGGER.debug("setYamahaDevice: %s", yamaha_device)
        self._yamaha = yamaha_device

    def set_power(self, power):
        """Send Power command."""
        req_url = ENDPOINTS["setPower"].format(self.ip_address, self.zone_id)
        params = {"power": "on" if power else "standby"}
        return request_get(req_url, params=params)

    def set_mute(self, mute):
        """Send mute command."""
        req_url = ENDPOINTS["setMute"].format(self.ip_address, self.zone_id)
        params = {"enable": "true" if mute else "false"}
        return request_get(req_url, params=params)

    def set_volume(self, volume):
        """Send Volume command."""
        req_url = ENDPOINTS["setVolume"].format(self.ip_address, self.zone_id)
        params = {"volume": int(volume)}
        return request_get(req_url, params=params)

    def set_input(self, input_id):
        """Send Input command."""
        req_url = ENDPOINTS["setInput"].format(self.ip_address, self.zone_id)
        params = {"input": input_id}
        return request_get(req_url, params=params)

    def update_distribution_info(self, new_distribution_info=None):
        """Get distribution info from device and update zone"""
        _LOGGER.debug("update_distribution_info: Zone %s", self.zone_id)

        if self.status and new_distribution_info is None:
            _LOGGER.debug("Zone: healthy.")
        else:
            old_distribution_info = self.distribution_info or {}

            if new_distribution_info:
                # merge new_distribution_info with existing for comparison
                _LOGGER.debug("Set distribution_info: provided")

                # make a copy of the old_distribution_info
                distribution_info = old_distribution_info.copy()

                # merge updated items into status
                distribution_info.update(new_distribution_info)

                # promote merged_status to new_status
                new_distribution_info = distribution_info
            else:
                _LOGGER.debug("Set distribution_info: own")
                new_distribution_info = self.get_distribution_info()

            _LOGGER.debug("old_distribution_info: %s", old_distribution_info)
            _LOGGER.debug("new_distribution_info: %s", new_distribution_info)
            _LOGGER.debug("is_equal: %s", old_distribution_info == new_distribution_info)

            if new_distribution_info != old_distribution_info:
                self.handle_distribution_info(new_distribution_info)
                self._status_sent = False
                self.distribution_info = new_distribution_info

        if not self._status_sent:
            self._status_sent = self.update_hass()

    def handle_distribution_info(self, message):
        """Process UDP messages"""
        if self._yamaha:
            if 'role' in message:
                _LOGGER.debug("Role: %s", message.get('role'))
                self._yamaha.group_distribution = (
                    STATE_OFF if not message.get('client_list') else STATE_ON)
        else:
            _LOGGER.debug("No yamaha-obj found")
    
        
    def distribution_group_set_name(self, group_name):
        """Set the new name of the group"""
        req_url = ENDPOINTS["setGroupName"].format(self._ip_address)
        payload = {'name': group_name}
        return  request_get(req_url, method='POST', json=payload)

    def distribution_group_add(self, clients):
        """Add clients to distribution group and start serving the clients"""
        #TODO: check that we can switch as a server...
        if self._group_id==None:
          self._group_id = '%032x' % random.randrange(16**32)
          
        for client in clients:
            req_url = ENDPOINTS["setClientInfo"].format(client)
            payload = {'group_id': self._group_id,
                       'zone': self._zone_id,
                       'server_ip_address': self._ip_address
            }
                       #'server_ip_address': self._ip_address}
            #payload = "group_id":"9A237BF5AB80ED3C7251DFF49825CA42", "zone":["main", "zone2"] }
            #payload = "group_id":"9A237BF5AB80ED3C7251DFF49825CA42", "zone":["main", "zone2"], "server_ip_address":"192.168.1.46" }
            #_LOGGER.debug("setClientInfo payload: ")
            #_LOGGER.debug(payload)
            resp = request_get(req_url, method='POST', json=payload)
            #TODO: check response?
            self._group_clients.append(client)
            
        req_url = ENDPOINTS["setServerInfo"].format(self._ip_address)
        payload = {'group_id': self._group_id,
                   'type': 'add',
                   'client_list': clients}
        #payload = { "group_id":"9A237BF5AB80ED3C7251DFF49825CA42", "type":"add", "client_list":["192.168.1.45"] }
        #_LOGGER.debug("setServerInfo payload: " )
        #_LOGGER.debug(payload)
        resp = request_get(req_url, method='POST', json=payload)
        #TODO: Check response before continuing
        
        req_url = ENDPOINTS["startDistribution"].format(self.ip_address)
        params = {"num": int(0)}
        _LOGGER.debug("Response startDistribution:")
        resp = request_get(req_url, params=params)
        return resp
        
        
    def distribution_group_remove(self, clients):
        """Remove clients, stop distribution if no more."""
        for client in clients:
            _LOGGER.debug("Resetting client: %s", client)
            req_url = ENDPOINTS["setClientInfo"].format(client)
            payload = {'group_id': '',
                       'zone': self._zone_id}
            resp = request_get(req_url, method='POST', json=payload)
            if client in self._group_clients:
                self.remove(client)
        
        req_url = ENDPOINTS["setServerInfo"].format(self._ip_address)
        payload = {'group_id': self._group_id,
                   'type': 'remove',
                   'client_list': clients}
        #_LOGGER.debug("setServerInfo payload: " )
        #_LOGGER.debug(payload)
        resp = request_get(req_url, method='POST', json=payload)
        
        if len(self._group_clients) > 0:
            req_url = ENDPOINTS["startDistribution"].format(self.ip_address)
            params = {"num": int(0)}
            _LOGGER.debug("Response updateDistribution:")
            resp = request_get(req_url, params=params)
        else:
            self._group_id=None
            req_url = ENDPOINTS["setServerInfo"].format(self._ip_address)
            payload = {'group_id': ''}
            _LOGGER.debug("Response resetServerInfo:")
            return request_get(req_url, method='POST', json=payload)
            
            req_url = ENDPOINTS["stopDistribution"].format(self.ip_address)
            _LOGGER.debug("Response stopDistribution:")
            resp = request_get(req_url)
            
        return resp
        
    def distribution_group_stop(self):
        """Remove all the clients and stop the distribution group"""
        self.distribution_group_remove(self._group_clients)
        
        
