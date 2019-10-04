#!/usr/bin/env python
"""This file."""
import logging
import random

from .const import DOMAIN, ENDPOINTS, GROUP_ID_NULL
from .helpers import request

_LOGGER = logging.getLogger(__name__)


class DistGroupClient(object):
    """Represent a DistGroup Client."""

    def __init__(self, ip_address, entity_id=None):
        """Initialize DistGroup Client."""
        self.ip_address = ip_address
        self.entity_id = entity_id or "Unknown"

    def __repr__(self):
        """Return ip_address for representation."""
        return self.ip_address


class DistGroup(object):
    """Represent a distribution group."""

    def __init__(self, master, clients, hass=None):
        """Init DistGroup."""
        super(DistGroup, self).__init__()
        self._master = None
        self._clients = []
        self.master = master
        self.clients = clients
        self._hass = hass
        self._group_id = "%032x" % random.randrange(16 ** 32)

    @property
    def master(self):
        """Return master."""
        return self._master

    @master.setter
    def master(self, master):
        """Define master."""
        if isinstance(master, str):
            self._master = DistGroupClient(master)
        elif isinstance(master, DistGroup):
            self._master = master
        else:
            _LOGGER.warning("Unknown type of master")

    @property
    def clients(self):
        """Return clients."""
        return self._clients

    @clients.setter
    def clients(self, clients):
        """Define clients."""
        for client in clients:
            if isinstance(client, str):
                self._clients.append(DistGroupClient(client))
            elif isinstance(client, DistGroup):
                self._clients.append(client)
            else:
                _LOGGER.warning("Unknown type of client")

    @property
    def client_ips(self):
        """Return a list of ip_addresses."""
        return [client.ip_address for client in self.clients]

    @property
    def group_id(self):
        """Return group_id."""
        return self._group_id

    @classmethod
    def join_add(cls, master_id, entity_ids, hass):
        """Service to join/add master & client."""
        mc_devices = hass.data[DOMAIN].devices

        if master_id not in mc_devices:
            return

        master = mc_devices[master_id].ip_address
        clients = [
            mc_devices[entity_id].ip_address
            for entity_id in entity_ids
            if entity_id in mc_devices and entity_id != master_id
        ]

        if master and clients:
            dist_group = cls(master, clients, hass)
            if dist_group.link_group():
                _LOGGER.info(f"success: {dist_group.group_id}")
            else:
                _LOGGER.warning(f"Couldn't link group.")

    @classmethod
    def unjoin(cls, entity_ids, hass):
        """Service to unjoin entity_id(s) from Group."""
        mc_devices = hass.data[DOMAIN].devices
        clients = [
            mc_devices[entity_id] for entity_id in entity_ids if entity_id in mc_devices
        ]
        print(clients[0].ip_address)

    @classmethod
    def dist_info_updated(cls, ip_address, hass):
        """Check distribution group for updates."""
        dist_info = cls.get_dist_info(ip_address)
        group_id = dist_info.get("group_id")

        mc_group_id = None
        mc_groups = hass.data[DOMAIN].groups
        mc_group = None

        for mc_group_id in mc_groups:  # iterate each mc_group
            _LOGGER.debug("Checking group %s", mc_group_id)
            mc_group = mc_groups[mc_group_id]
            if ip_address == mc_group.master.ip_address:
                _LOGGER.info("Device belongs to group %s as master", mc_group.group_id)
                break
            elif ip_address in mc_group.client_ips:
                _LOGGER.info("Device belongs to group %s as client", mc_group.group_id)
                break
            else:
                _LOGGER.info("Device does not belong to any group yet")

        # if mc_group:
        #     print(mc_group.group_id)

        if group_id not in mc_groups and group_id != GROUP_ID_NULL:
            _LOGGER.debug("Externally managed distribution group.")
            return

        group_members = []
        if mc_group_id != group_id:
            _LOGGER.info("Update group membership")
            if group_id != GROUP_ID_NULL:
                group_members = [
                    "media_player.wohnzimmer_main",
                    "media_player.arbeitszimmer_main",
                ]

        role = dist_info.get("role")
        if role == "client":
            _LOGGER.info("Device is a client")
        elif role == "server":
            _LOGGER.info("Device is the master")
        else:
            _LOGGER.info("Device has no role")

        if not dist_info.get("client_list"):
            _LOGGER.info("Device is no active client")

        print(f"{ip_address}: {dist_info}")
        return {
            "server_zone": dist_info.get("server_zone"),
            "group_members": group_members,
        }

    @staticmethod
    def get_dist_info(ip_address):
        """Get distribution info from device."""
        req_url = ENDPOINTS["getDistributionInfo"].format(ip_address)
        return request(req_url)

    def link_group(self):
        """Link a distribution group."""
        if not self.check_compatibility():
            _LOGGER.debug("link_group(%s): Not compatible", self.group_id)
            return
        if not self.prepare_clients():
            _LOGGER.debug("link_group(%s): Clients not ready", self.group_id)
            return
        if not self.prepare_master():
            _LOGGER.debug("link_group(%s): Master not ready", self.group_id)
            return
        if not self.start_distribution():
            _LOGGER.debug("link_group(%s): Couldn't start distribution", self.group_id)
            return
        if not self.set_group_name("pymusiccast"):
            _LOGGER.debug("link_group(%s): Couldn't set group_name", self.group_id)
            return
        _LOGGER.info("link_group(%s): Linked successful", self.group_id)
        if self._hass:
            self._hass.data[DOMAIN].groups[self.group_id] = self
        return True

    def unlink_group(self):
        """Unlink a distribution group."""
        success = True
        for client in self.clients:
            success &= self.set_client_info(client)
        success &= self.set_server_info()
        success &= self.stop_distribution()
        success &= self.set_group_name()
        return success

    def check_compatibility(self):
        """Check compability betwenn master and clients."""
        master_features = self.get_features(self.master)
        compatible_client = master_features["distribution"]["compatible_client"]

        compatible_result = True

        for client in self.clients:
            client_features = self.get_features(client)
            client_version = int(client_features["distribution"]["version"])
            _LOGGER.debug("client: %s version: %d", client, client_version)
            compatible_result &= client_version in compatible_client

        return compatible_result

    def get_features(self, client):
        """Get system features for client."""
        req_url = ENDPOINTS["getFeatures"].format(client)
        return request(req_url)

    def get_status(self, client, zone="main"):
        """Get system status for client."""
        req_url = ENDPOINTS["getStatus"].format(client, zone)
        return request(req_url)

    def prepare_clients(self):
        """Prepare clients."""
        success = True
        for client in self.clients:
            status = self.get_status(client)
            if status.get("power") != "on":
                success &= self.set_power(client)
            if status.get("input") != "mc_link":
                success &= self.set_input(client)
            success &= self.set_client_info(client, self.group_id)
        return success

    def set_client_info(self, client, group_id="", zone="main"):
        """Set Group ID and target Zone for client."""
        req_url = ENDPOINTS["setClientInfo"].format(client)
        payload = {
            "group_id": group_id,
            "server_ip_address": self.master.ip_address,
            "zone": [zone],
        }
        response = request(req_url, method="POST", json=payload)
        if response["response_code"] != 0:
            print(response)
        return response["response_code"] == 0

    def set_server_info(self, group_id="", action=None, clients=None, zone="main"):
        """Set Group ID and clients for master."""
        req_url = ENDPOINTS["setServerInfo"].format(self.master)
        payload = {"group_id": group_id, "client_list": clients}
        if action and clients:
            payload["type"] = action
            payload["client_list"] = [client.ip_address for client in clients]
        response = request(req_url, method="POST", json=payload)
        return response["response_code"] == 0

    def set_group_name(self, group_name=""):
        """Set group name for client."""
        req_url = ENDPOINTS["setGroupName"].format(self.master)
        payload = {"name": group_name}
        response = request(req_url, method="POST", json=payload)
        return response["response_code"] == 0

    def set_power(self, client, zone="main", power="on"):
        """Send Power command."""
        req_url = ENDPOINTS["setPower"].format(client, zone)
        params = {"power": "on" if power else "standby"}
        response = request(req_url, params=params)
        return response["response_code"] == 0

    def set_input(self, client, zone="main", input_id="mc_link"):
        """Send Input command."""
        req_url = ENDPOINTS["setInput"].format(client, zone)
        params = {"input": input_id}
        response = request(req_url, params=params)
        return response["response_code"] == 0

    def prepare_master(self):
        """Prepare master."""
        return self.set_server_info(self.group_id, "add", self.clients)

    def start_distribution(self):
        """Start group distribution."""
        req_url = ENDPOINTS["startDistribution"].format(self.master)
        num = len(self._hass.data[DOMAIN].groups) if self._hass else 0
        params = {"num": num}
        response = request(req_url, params=params)
        return response["response_code"] == 0

    def stop_distribution(self):
        """Stop group distribution."""
        req_url = ENDPOINTS["stopDistribution"].format(self.master)
        response = request(req_url)
        return response["response_code"] == 0
