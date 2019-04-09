#!/usr/bin/env python
"""This is a docstring."""
import random
import logging
from .const import ENDPOINTS, STATE_ON, STATE_OFF
from .helpers import request
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
    def group_id(self):
        """Returns the distribution group id."""
        return self._distribution_info.get("group_id")

    @property
    def group_is_server(self):
        """Returns true if this zone believes it is a server"""
        return self._distribution_info.get('role') == 'server' and self.group_id != '00000000000000000000000000000000'

    @property
    def group_clients(self):
        """Returns the ip address of distribution group clients."""
        if not self.group_is_server:
            return []
        if self._distribution_info.get('client_list') is None:
            return []
        return [e.get('ip_address') for e in self._distribution_info.get('client_list')]

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
                _LOGGER.debug("%s: Power: %s", self._ip_address, message.get('power'))
                self._yamaha.power = (
                    STATE_ON if message.get('power') == "on" else STATE_OFF)
            if 'input' in message:
                _LOGGER.debug("%s: Input: %s", self._ip_address, message.get('input'))
                self._yamaha._source = message.get('input')
            if 'volume' in message:
                volume = message.get('volume')

                if 'max_volume' in message:
                    volume_max = message.get('max_volume')
                else:
                    volume_max = self._yamaha.volume_max

                _LOGGER.debug("%s: Volume: %d / Max: %d", self._ip_address, volume, volume_max)

                self._yamaha.volume = volume / volume_max
                self._yamaha.volume_max = volume_max
            if 'mute' in message:
                _LOGGER.debug("%s: Mute: %s", self._ip_address, message.get('mute'))
                self._yamaha.mute = message.get('mute', False)
        else:
            _LOGGER.debug("%s: No yamaha-obj found", self._ip_address)

    def update_status(self, new_status=None):
        """Updates the zone status."""
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
            _LOGGER.debug("%s: is_equal: %s", self._ip_address, old_status == new_status)

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

    def update_distribution_info(self, new_distribution_info=None):
        """Get distribution info from device and update zone"""
        _LOGGER.debug("%s: update_distribution_info: Zone %s", self._ip_address, self.zone_id)

        if self.distribution_info and new_distribution_info is None:
            _LOGGER.debug("%s: distrib: healthy.", self._ip_address)
        else:
            old_distribution_info = self.distribution_info or {}

            if new_distribution_info:
                # merge new_distribution_info with existing for comparison
                _LOGGER.debug("%s: Set distribution_info: provided", self._ip_address)

                # make a copy of the old_distribution_info
                distribution_info = old_distribution_info.copy()

                # merge updated items into status
                distribution_info.update(new_distribution_info)

                # promote merged_status to new_status
                new_distribution_info = distribution_info
            else:
                _LOGGER.debug("S%s: et distribution_info: own", self._ip_address)
                new_distribution_info = self._receiver.update_distribution_info()

            if new_distribution_info != old_distribution_info:
                _LOGGER.debug("%s: old_distribution_info: %s", self._ip_address, old_distribution_info)
                _LOGGER.debug("%s: new_distribution_info: %s", self._ip_address, new_distribution_info)
                _LOGGER.debug("%s: is_equal: %s", self._ip_address, old_distribution_info == new_distribution_info)
                self.handle_distribution_info(new_distribution_info)
                self._status_sent = False
                self.distribution_info = new_distribution_info
            # if server, check for connected clients:
            if self.group_is_server:
                self.distribution_group_check_clients()

        if not self._status_sent:
            self._status_sent = self.update_hass()

    def handle_distribution_info(self, message):
        """Process UDP messages"""
        if self._yamaha:
            _LOGGER.debug("%s: updating group of entity", self._ip_address)
            self._yamaha.update_group()
        else:
            _LOGGER.debug("%s: No yamaha-obj found", self._ip_address)

    def distribution_group_set_name(self, group_name):
        """For SERVER: Set the new name of the group"""
        req_url = ENDPOINTS["setGroupName"].format(self._ip_address)
        payload = {'name': group_name}
        return request(req_url, method='POST', json=payload)

    def distribution_group_add(self, clients):
        """For SERVER: Add clients to distribution group and start serving the clients"""
        if len(clients) == 0:
            return
        # TODO: check that we can switch as a server...
        group_id = self.group_id
        if group_id == '00000000000000000000000000000000':
            group_id = '%032x' % random.randrange(16**32)
        _LOGGER.debug("%s: Setting the clients to be clients: %s", self._ip_address, clients)
        for client in clients:
            req_url = ENDPOINTS["setClientInfo"].format(client)
            payload = {'group_id': group_id,
                       'zone': self._zone_id,
                       'server_ip_address': self._ip_address
                       }
            resp = request(req_url, method='POST', json=payload)

        _LOGGER.debug("%s: adding to the server the clients: %s", self._ip_address, clients)
        req_url = ENDPOINTS["setServerInfo"].format(self._ip_address)
        payload = {'group_id': group_id,
                   'type': 'add',
                   'client_list': clients}
        resp = request(req_url, method='POST', json=payload)

        _LOGGER.debug("%s: Starting the distribution", self._ip_address)
        req_url = ENDPOINTS["startDistribution"].format(self.ip_address)
        params = {"num": int(0)}
        resp = request(req_url, params=params)
        return resp

    def distribution_group_check_clients(self):
        """For SERVER: Contacting clients to ensure they are still serving our group."""
        if not self.group_is_server:
            return
        _LOGGER.debug("%s: Checking client status. Current registered clients: %s", self._ip_address, self.group_clients)
        clients_to_remove = []
        for client in self.group_clients:
            # check if it is still a client with correct group and input
            req_url = ENDPOINTS["getDistributionInfo"].format(client)
            response = request(req_url)
            if response.get('role') != 'client' or response.get('group_id') != self.group_id:
                clients_to_remove.append(client)
                continue
            req_url = ENDPOINTS["getStatus"].format(client, self.zone_id)
            response = request(req_url)
            if response.get('input') != "mc_link":
                clients_to_remove.append(client)
        if len(clients_to_remove) > 0:
            _LOGGER.debug("%s: Clients: %s does not seem to be connected anymore... removing", self._ip_address, clients_to_remove)
            self.distribution_group_remove(clients_to_remove)

    def distribution_group_remove(self, clients):
        """For SERVER: Remove clients, stop distribution if no more."""
        if not self.group_is_server or len(clients) == 0:
            return
        old_clients = self.group_clients.copy()

        for client in clients:
            _LOGGER.debug("%s: Resetting client: %s", self._ip_address, client)
            req_url = ENDPOINTS["setClientInfo"].format(client)
            payload = {'group_id': '',
                       'zone': self._zone_id}
            resp = request(req_url, method='POST', json=payload)
            if client in old_clients:
                old_clients.remove(client)

        _LOGGER.debug("%s: Removing from server the clients: %s", self._ip_address, clients)
        req_url = ENDPOINTS["setServerInfo"].format(self._ip_address)
        payload = {'group_id': self.group_id,
                   'type': 'remove',
                   'client_list': clients}
        resp = request(req_url, method='POST', json=payload)

        if len(old_clients) > 0:
            req_url = ENDPOINTS["startDistribution"].format(self.ip_address)
            params = {"num": int(0)}
            _LOGGER.debug("%s: Updating the distribution with remaining clients: %s", self._ip_address, old_clients)
            resp = request(req_url, params=params)
        else:
            _LOGGER.debug("%s: No more clients, resetting server", self._ip_address)
            req_url = ENDPOINTS["setServerInfo"].format(self._ip_address)
            payload = {'group_id': ''}
            request(req_url, method='POST', json=payload)

            req_url = ENDPOINTS["stopDistribution"].format(self.ip_address)
            _LOGGER.debug("%s: Stopping the distribution", self._ip_address)
            resp = request(req_url)
        return resp

    def distribution_group_stop(self):
        """For SERVER: Remove all the clients and stop the distribution group"""
        if not self.group_is_server:
            return
        _LOGGER.debug("%s: stopDistribution client_list: %s", self._ip_address, self.group_clients)
        self.distribution_group_remove(self.group_clients)

    def distribution_group_leave(self):
        """For CLIENT: The client disconnect from group. (The server will need to then updates its group)"""
        if self.group_is_server:
            self.distribution_group_stop()
            return
        _LOGGER.debug("%s: client is leaving the group", self._ip_address)
        req_url = ENDPOINTS["setClientInfo"].format(self.ip_address)
        payload = {'group_id': '',
                   'zone': self._zone_id}
        resp = request(req_url, method='POST', json=payload)
        return resp
