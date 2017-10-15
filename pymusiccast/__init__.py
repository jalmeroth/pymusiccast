""""This library brings support for \
Yamaha MusicCast devices to Home Assistant."""
import queue
import socket
import logging
import threading
from homeassistant.const import (
    STATE_UNKNOWN, STATE_PLAYING, STATE_PAUSED, STATE_IDLE
)
from requests.exceptions import RequestException
from .const import ENDPOINTS
from .helpers import request, message_worker, socket_worker
from .media_status import MediaStatus
from .exceptions import YMCInitError
from .zone import Zone

_LOGGER = logging.getLogger(__name__)


class McDevice(object):
    """docstring for McDevice"""
    def __init__(self, ip_address, udp_port=5005, **kwargs):
        super(McDevice, self).__init__()
        _LOGGER.debug("McDevice: %s", ip_address)
        # construct message queue
        self.messages = queue.Queue()
        self._ip_address = ip_address
        self._udp_port = udp_port
        self._interval = kwargs.get('mc_interval', 480)
        self._zones = {}
        self._yamaha = None
        self._socket = None
        self._name = None
        self.device_id = None
        self.device_info = None
        self.device_features = None
        self.location_info = None
        self.update_status_timer = None
        try:
            self.initialize()
        except (OSError, RequestException) as err:
            raise YMCInitError(err)

    @property
    def ip_address(self):
        """Returns the ip_address."""
        return self._ip_address

    @property
    def zones(self):
        """Returns receiver zones."""
        return self._zones

    @zones.setter
    def zones(self, zones):
        """Sets receiver zones"""
        self._zones = zones

    @property
    def name(self):
        """Returns name of device."""
        return self._name

    @name.setter
    def name(self, name):
        """Sets name of device."""
        self._name = name

    def initialize(self):
        """initialize the object"""
        self.location_info = self.get_location_info()
        self.name = self.location_info.get('name', 'Unknown')
        self.device_info = self.get_device_info()
        self.device_id = (
            self.device_info.get('device_id')
            if self.device_info else "Unknown")
        self.initialize_socket()
        self.initialize_worker()
        self.initialize_zones()

    def initialize_socket(self):
        """initialize the socket"""
        self._socket = socket.socket(
            socket.AF_INET,     # IPv4
            socket.SOCK_DGRAM   # UDP
        )
        self._socket.bind(('', self._udp_port))
        _LOGGER.debug("Socket open.")
        _LOGGER.debug("Starting Socket Thread.")
        socket_thread = threading.Thread(
            name="SocketThread", target=socket_worker,
            args=(self._socket, self.messages,))
        socket_thread.setDaemon(True)
        socket_thread.start()

    def initialize_worker(self):
        """initialize the worker thread"""
        _LOGGER.debug("Starting Worker Thread.")
        worker_thread = threading.Thread(
            name="WorkerThread", target=message_worker, args=(self,))
        worker_thread.setDaemon(True)
        worker_thread.start()

    def initialize_zones(self):
        """initialize receiver zones"""
        zone_list = self.location_info.get('zone_list', {'main': True})

        for zone_id in zone_list:
            if zone_list[zone_id]:  # Location setup is valid
                self.zones[zone_id] = Zone(self, zone_id=zone_id)
            else:                   # Location setup is not valid
                _LOGGER.debug("Ignoring zone: %s", zone_id)

    def get_device_info(self):
        """Get info from device"""
        req_url = ENDPOINTS["getDeviceInfo"].format(self._ip_address)
        return request(req_url)

    def get_features(self):
        """Get features from device"""
        req_url = ENDPOINTS["getFeatures"].format(self._ip_address)
        return request(req_url)

    def get_location_info(self):
        """Get location info from device"""
        req_url = ENDPOINTS["getLocationInfo"].format(self._ip_address)
        return request(req_url)

    def get_status(self):
        """Get status from device"""
        headers = {
            "X-AppName": "MusicCast/0.1(python)",
            "X-AppPort": str(self._udp_port)
        }
        req_url = ENDPOINTS["getStatus"].format(self.ip_address, 'main')
        return request(req_url, headers=headers)

    def handle_netusb(self, message):
        """Handles 'netusb' in message"""
        # _LOGGER.debug("message: {}".format(message))
        if self._yamaha:
            if 'play_info_updated' in message:
                play_info = self.get_play_info()
                # _LOGGER.debug(play_info)
                if play_info:
                    self._yamaha.media_status = MediaStatus(
                        play_info, self._ip_address)
                    playback = play_info.get('playback')
                    # _LOGGER.debug("Playback: {}".format(playback))
                    if playback == "play":
                        self._yamaha.status = STATE_PLAYING
                    elif playback == "stop":
                        self._yamaha.status = STATE_IDLE
                    elif playback == "pause":
                        self._yamaha.status = STATE_PAUSED
                    else:
                        self._yamaha.status = STATE_UNKNOWN

    def handle_features(self, device_features):
        """Handles features of the device"""
        if device_features and 'zone' in device_features:
            for zone in device_features['zone']:
                zone_id = zone.get('id')
                if zone_id in self.zones:
                    _LOGGER.debug("handle_features: %s", zone_id)
                    input_list = zone.get('input_list', [])
                    input_list.sort()
                    self.zones[zone_id].source_list = input_list

    def handle_event(self, message):
        """Dispatch all event messages"""
        # _LOGGER.debug(message)
        for zone in self.zones:
            if zone in message:
                _LOGGER.debug("Received message for zone: %s", zone)
                self.zones[zone].handle_message(message[zone])

        if 'netusb' in message:
            self.handle_netusb(message['netusb'])

        self.update_hass()

    def update_status(self):
        """Update device status"""

        if not self.update_status_timer:
            _LOGGER.debug("update_status: First update")
            # try to get first device status, register for UDP Events
            status = self.get_status()
            # on success, schedule first timer
            if status:
                self.setup_update_timer()

                if not self.device_features:
                    # get device features only once
                    self.device_features = self.get_features()
                    self.handle_features(self.device_features)
                    self.update_hass()
        else:
            if not self.update_status_timer.is_alive():
                # e.g. computer was suspended, while hass was running
                _LOGGER.debug("update_status: Reschedule timer")
                self.setup_update_timer()

    def setup_update_timer(self):
        """Schedule a Timer Thread."""
        _LOGGER.debug(
            "update status: firing again in %d seconds", self._interval)
        self.update_status_timer = threading.Timer(
            self._interval, self.get_status)
        self.update_status_timer.setDaemon(True)
        self.update_status_timer.start()

    def update_hass(self):
        """Update HASS."""
        _LOGGER.debug("update_hass: Push updates")
        if self._yamaha and self._yamaha.entity_id:     # Push updates
            self._yamaha.schedule_update_ha_state()

    def set_yamaha_device(self, yamaha_device):
        """Set reference to device in HASS"""
        _LOGGER.debug("setYamahaDevice: %s", yamaha_device)
        self._yamaha = yamaha_device

    def get_play_info(self):
        """Get play info from device"""
        req_url = ENDPOINTS["getPlayInfo"].format(self._ip_address)
        return request(req_url)

    def set_playback(self, playback):
        """Send Playback command."""
        req_url = ENDPOINTS["setPlayback"].format(self._ip_address)
        params = {"playback": playback}
        return request(req_url, params=params)

    def __del__(self):
        if self._socket:
            _LOGGER.debug("Closing Socket.")
            self._socket.close()
