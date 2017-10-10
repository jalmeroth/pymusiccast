""""This library brings support for \
Yamaha MusicCast devices to Home Assistant."""
import queue
import socket
import logging
import threading
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNKNOWN,
    STATE_PLAYING, STATE_PAUSED, STATE_IDLE
)
from requests.exceptions import RequestException
from .const import ENDPOINTS
from .helpers import request, message_worker, socket_worker
from .media_status import MediaStatus
from .exceptions import YMCInitError

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
        self._yamaha = None
        self._socket = None
        self.device_id = None
        self.device_info = None
        self.device_features = None
        self.update_status_timer = None
        try:
            self.initialize()
        except (OSError, RequestException) as err:
            raise YMCInitError(err)

    def initialize(self):
        """initialize the object"""
        self.device_info = self.get_device_info()
        _LOGGER.debug(self.device_info)
        self.device_id = (
            self.device_info.get('device_id')
            if self.device_info else "Unknown")
        self.initialize_socket()
        self.initialize_worker()

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

    def get_device_info(self):
        """Get info from device"""
        req_url = ENDPOINTS["getDeviceInfo"].format(self._ip_address)
        return request(req_url)

    def get_features(self):
        """Get features from device"""
        req_url = ENDPOINTS["getFeatures"].format(self._ip_address)
        return request(req_url)

    @staticmethod
    def get_location_info(ip_address):
        """Get location info from device"""
        req_url = ENDPOINTS["getLocationInfo"].format(ip_address)
        return request(req_url)

    def get_status(self):
        """Get status from device"""
        headers = {
            "X-AppName": "MusicCast/0.1(python)",
            "X-AppPort": str(self._udp_port)
        }
        req_url = ENDPOINTS["getStatus"].format(self._ip_address)
        return request(req_url, headers=headers)

    def get_play_info(self):
        """Get play info from device"""
        req_url = ENDPOINTS["getPlayInfo"].format(self._ip_address)
        return request(req_url)

    def handle_main(self, message):
        """Handles 'main' in message"""
        # _LOGGER.debug("message: {}".format(message))
        if self._yamaha:
            if 'power' in message:
                _LOGGER.debug("Power: %s", message.get('power'))
                self._yamaha.power = (
                    STATE_ON if message.get('power') == "on" else STATE_OFF)
            if 'input' in message:
                _LOGGER.debug("Input: %s", message.get('input'))
                self._yamaha._source = message.get('input')
            if 'volume' in message and 'max_volume' in message:
                _LOGGER.debug(
                    "Volume: %d / Max: %d",
                    message.get('volume'),
                    message.get('max_volume')
                )
                volume = message.get('volume') / message.get('max_volume')
                self._yamaha.volume = volume
                self._yamaha.volume_max = message.get('max_volume')
            if 'mute' in message:
                _LOGGER.debug("Mute: %s", message.get('mute'))
                self._yamaha.mute = message.get('mute', False)
        else:
            _LOGGER.debug("No yamaha-obj found")

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
                if zone.get('id') == 'main':
                    input_list = zone.get('input_list', [])
                    input_list.sort()
                    self._yamaha.source_list = input_list
                    break

    def handle_event(self, message):
        """Dispatch all event messages"""
        # _LOGGER.debug(message)
        if 'main' in message:
            self.handle_main(message['main'])

        if 'netusb' in message:
            self.handle_netusb(message['netusb'])

        if self._yamaha:                                    # Push updates
            # _LOGGER.debug("Push updates")
            self._yamaha.schedule_update_ha_state()

    def update_status(self, push=True):
        """Update device status"""
        status = self.get_status()
        if status:
            _LOGGER.debug(
                "update status: firing again in %d seconds", self._interval)
            self.update_status_timer = threading.Timer(
                self._interval, self.update_status)
            self.update_status_timer.setDaemon(True)
            self.update_status_timer.start()
            self.handle_main(status)

            # get features only once
            if not self.device_features:
                self.device_features = self.get_features()
                _LOGGER.debug(self.device_features)
                self.handle_features(self.device_features)

        if self._yamaha and push:                           # Push updates
            # _LOGGER.debug("Push updates")
            self._yamaha.schedule_update_ha_state()

    def set_yamaha_device(self, obj):
        """Set reference to device in HASS"""
        _LOGGER.debug("setYamahaDevice: %s", obj)
        self._yamaha = obj

    def set_power(self, power):
        """Send Power command."""
        req_url = ENDPOINTS["setPower"].format(self._ip_address)
        params = {"power": "on" if power else "standby"}
        return request(req_url, params=params)

    def set_mute(self, mute):
        """Send mute command."""
        req_url = ENDPOINTS["setMute"].format(self._ip_address)
        params = {"enable": "true" if mute else "false"}
        return request(req_url, params=params)

    def set_volume(self, volume):
        """Send Volume command."""
        req_url = ENDPOINTS["setVolume"].format(self._ip_address)
        params = {"volume": int(volume)}
        return request(req_url, params=params)

    def set_input(self, input_id):
        """Send Input command."""
        req_url = ENDPOINTS["setInput"].format(self._ip_address)
        params = {"input": input_id}
        return request(req_url, params=params)

    def set_playback(self, playback):
        """Send Playback command."""
        req_url = ENDPOINTS["setPlayback"].format(self._ip_address)
        params = {"playback": playback}
        return request(req_url, params=params)

    def __del__(self):
        if self._socket:
            _LOGGER.debug("Closing Socket.")
            self._socket.close()
