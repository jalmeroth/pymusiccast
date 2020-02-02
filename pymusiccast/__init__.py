"""This library brings support for Yamaha MusicCast devices to Home Assistant."""
import logging
import queue
import socket
import threading

from requests.exceptions import RequestException

from .const import ENDPOINTS, STATE_IDLE, STATE_PAUSED, STATE_PLAYING, STATE_UNKNOWN
from .exceptions import YMCInitError
from .helpers import message_worker, request, socket_worker
from .media_status import MediaStatus
from .zone import Zone
from .dist import DistGroup

_LOGGER = logging.getLogger(__name__)


class McDevice(object):
    """Represent a MusicCast device."""

    def __init__(self, ip_address, udp_port=5005, **kwargs):
        """Initialize the McDevice."""
        super(McDevice, self).__init__()
        _LOGGER.debug("%s: New McDevice", ip_address)
        # construct message queue
        self.messages = queue.Queue()
        self._ip_address = ip_address
        self._udp_port = udp_port
        self._interval = kwargs.get("mc_interval", 480)
        self._zones = {}
        self._yamaha = None
        self._socket = None
        self._name = None
        self._hass = kwargs.get("hass")
        self.device_id = None
        self.device_info = None
        self.device_features = None
        self.location_info = None
        self.network_status = None
        self.update_status_timer = None
        try:
            self.initialize()
        except (OSError, RequestException) as err:
            raise YMCInitError(err)

    @property
    def ip_address(self):
        """Return the ip_address."""
        return self._ip_address

    @property
    def zones(self):
        """Return receiver zones."""
        return self._zones

    @zones.setter
    def zones(self, zones):
        """Set receiver zones."""
        self._zones = zones

    @property
    def name(self):
        """Return name of device."""
        return self._name

    @name.setter
    def name(self, name):
        """Set name of device."""
        self._name = name

    @property
    def healthy_update_timer(self):
        """Check state of update timer."""
        state = None
        if self.update_status_timer and self.update_status_timer.is_alive():
            _LOGGER.debug("%s: Timer: healthy", self._ip_address)
            state = True
        else:
            _LOGGER.debug("%s: Timer: not healthy", self._ip_address)
            state = False
        return state

    def initialize(self):
        """Initialize the object."""
        self.network_status = self.get_network_status()
        self.name = self.network_status.get("network_name", "Unknown")
        self.location_info = self.get_location_info()
        self.device_info = self.get_device_info()
        self.device_id = (
            self.device_info.get("device_id") if self.device_info else "Unknown"
        )
        self.initialize_socket()
        self.initialize_worker()
        self.initialize_zones()

    def initialize_socket(self):
        """Initialize the socket."""
        try:
            _LOGGER.debug("%s: Trying to open socket.", self._ip_address)
            self._socket = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM  # IPv4  # UDP
            )
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("", self._udp_port))
        except socket.error as err:
            raise err
        else:
            _LOGGER.debug("%s: Socket open.", self._ip_address)
            socket_thread = threading.Thread(
                name="SocketThread",
                target=socket_worker,
                args=(self._socket, self.messages),
            )
            socket_thread.setDaemon(True)
            socket_thread.start()

    def initialize_worker(self):
        """Initialize the worker thread."""
        worker_thread = threading.Thread(
            name="WorkerThread", target=message_worker, args=(self,)
        )
        worker_thread.setDaemon(True)
        worker_thread.start()

    def initialize_zones(self):
        """Initialize receiver zones."""
        zone_list = self.location_info.get("zone_list", {"main": True})

        for zone_id in zone_list:
            if zone_list[zone_id]:  # Location setup is valid
                self.zones[zone_id] = Zone(self, zone_id=zone_id)
            else:  # Location setup is not valid
                _LOGGER.debug("%s: Ignoring zone: %s", self._ip_address, zone_id)

    def get_device_info(self):
        """Get info from device."""
        req_url = ENDPOINTS["getDeviceInfo"].format(self._ip_address)
        return request(req_url)

    def get_features(self):
        """Get features from device."""
        req_url = ENDPOINTS["getFeatures"].format(self._ip_address)
        return request(req_url)

    def get_location_info(self):
        """Get location info from device."""
        req_url = ENDPOINTS["getLocationInfo"].format(self._ip_address)
        return request(req_url)

    def get_network_status(self):
        """Get network status from device."""
        req_url = ENDPOINTS["getNetworkStatus"].format(self._ip_address)
        return request(req_url)

    def get_status(self):
        """Get status from device to register/keep alive UDP."""
        headers = {
            "X-AppName": "MusicCast/0.1(python)",
            "X-AppPort": str(self._udp_port),
        }
        req_url = ENDPOINTS["getStatus"].format(self.ip_address, "main")
        return request(req_url, headers=headers)

    def handle_status(self):
        """Handle status from device."""
        status = self.get_status()
        _LOGGER.debug("%s: getting status.", self._ip_address)
        if status:
            # Update main-zone
            self.zones["main"].update_status(status)

    def handle_netusb(self, message):
        """Handle 'netusb' in message."""
        # _LOGGER.debug("message: {}".format(message))
        needs_update = 0
        if self._yamaha:
            if "play_info_updated" in message:
                play_info = self.get_play_info()
                # _LOGGER.debug(play_info)
                if play_info:
                    new_media_status = MediaStatus(play_info, self._ip_address)
                    if self._yamaha.media_status != new_media_status:
                        # we need to send an update upwards
                        self._yamaha.new_media_status(new_media_status)
                        needs_update += 1

                    playback = play_info.get("playback")
                    # _LOGGER.debug("Playback: {}".format(playback))
                    if playback == "play":
                        new_status = STATE_PLAYING
                    elif playback == "stop":
                        new_status = STATE_IDLE
                    elif playback == "pause":
                        new_status = STATE_PAUSED
                    else:
                        new_status = STATE_UNKNOWN
                    if self._yamaha.status is not new_status:
                        _LOGGER.debug("%s: playback: %s", self._ip_address, new_status)
                        self._yamaha.status = new_status
                        needs_update += 1
        return needs_update

    def handle_features(self, device_features):
        """Handle features of the device."""
        self.device_features = device_features

        if device_features and "zone" in device_features:
            for zone in device_features["zone"]:
                zone_id = zone.get("id")
                if zone_id in self.zones:
                    _LOGGER.debug("%s: handle_features: %s", self._ip_address, zone_id)
                    input_list = zone.get("input_list", [])
                    input_list.sort()
                    self.zones[zone_id].source_list = input_list
                    sound_program_list = zone.get("sound_program_list", [])
                    sound_program_list.sort()
                    self.zones[zone_id].sound_mode_list = sound_program_list

    def handle_event(self, message):
        """Dispatch all event messages."""
        # _LOGGER.debug(message)
        needs_update = 0
        for zone in self.zones:
            if zone in message:
                _LOGGER.debug(
                    "%s: Received message for zone: %s: %s",
                    self._ip_address,
                    zone,
                    message,
                )
                self.zones[zone].update_status(message[zone])

        if "netusb" in message:
            needs_update += self.handle_netusb(message["netusb"])

        if "dist" in message:
            if message["dist"].get("dist_info_updated"):
                info_updated = DistGroup.dist_info_updated(self.ip_address, self._hass)
                if info_updated:
                    server_zone = info_updated.get("server_zone")
                    self.zones[server_zone].update_dist_info(info_updated)

        if needs_update > 0:
            _LOGGER.debug("%s: needs_update: %d", self._ip_address, needs_update)
            self.update_hass()

    def update_hass(self):
        """Update HASS."""
        return self._yamaha.update_hass() if self._yamaha else False

    def update_status(self, reset=False):
        """Update device status."""
        if self.healthy_update_timer and not reset:
            return

        # get device features only once
        if not self.device_features:
            self.handle_features(self.get_features())

        # Get status from device to register/keep alive UDP
        self.handle_status()

        # Schedule next execution
        self.setup_update_timer()

    def setup_update_timer(self, reset=False):
        """Schedule a Timer Thread."""
        _LOGGER.debug(
            "%s: Timer: firing again in %d seconds", self._ip_address, self._interval
        )
        self.update_status_timer = threading.Timer(
            self._interval, self.update_status, [True]
        )
        self.update_status_timer.setDaemon(True)
        self.update_status_timer.start()

    def set_yamaha_device(self, yamaha_device):
        """Set reference to device in HASS."""
        _LOGGER.debug("%s: setYamahaDevice: %s", self._ip_address, yamaha_device)
        self._yamaha = yamaha_device

    def get_play_info(self):
        """Get play info from device."""
        req_url = ENDPOINTS["getPlayInfo"].format(self._ip_address)
        return request(req_url)

    def set_playback(self, playback):
        """Send Playback command."""
        req_url = ENDPOINTS["setPlayback"].format(self._ip_address)
        params = {"playback": playback}
        return request(req_url, params=params)

    def __del__(self):
        """Deconstructor."""
        if self._socket:
            _LOGGER.debug("%s: Closing Socket.", self._ip_address)
            self._socket.close()
