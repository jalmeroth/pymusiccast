""""This library brings support for \
Yamaha MusicCast devices to Home Assistant."""
import json
import time
import queue
import socket
import logging
import threading
import requests
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNKNOWN,
    STATE_PLAYING, STATE_PAUSED, STATE_IDLE
)
_LOGGER = logging.getLogger(__name__)

ENDPOINTS = {
    "getDeviceInfo": "http://{}/YamahaExtendedControl/v1/system/getDeviceInfo",
    "getFeatures": "http://{}/YamahaExtendedControl/v1/system/getFeatures",
    "getPlayInfo": "http://{}/YamahaExtendedControl/v1/netusb/getPlayInfo",
    "getStatus": "http://{}/YamahaExtendedControl/v1/main/getStatus",
    "setInput": "http://{}/YamahaExtendedControl/v1/main/setInput",
    "setMute": "http://{}/YamahaExtendedControl/v1/main/setMute",
    "setPlayback": "http://{}/YamahaExtendedControl/v1/netusb/setPlayback",
    "setPower": "http://{}/YamahaExtendedControl/v1/main/setPower",
    "setVolume": "http://{}/YamahaExtendedControl/v1/main/setVolume",
}


def request(url, *args, **kwargs):
    """Do the HTTP Request and return data"""
    method = kwargs.get('method', 'GET')
    timeout = kwargs.pop('timeout', 10)  # hass default timeout
    try:
        req = requests.request(method, url, *args, timeout=timeout, **kwargs)
    except requests.exceptions.RequestException as error:
        _LOGGER.error(error)
    else:
        try:
            data = req.json()
        except requests.exceptions.RequestException as error:
            _LOGGER.error(error)
        else:
            _LOGGER.debug(json.dumps(data))
            return data


def message_worker(device):
    """Loop through messages and pass them on to right device"""
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
    while True:
        data, addr = sock.recvfrom(1024)    # buffer size is 1024 bytes
        _LOGGER.debug("received message: %s from %s", data, addr)
        msg_q.put(data)
        time.sleep(0.2)


class MediaStatus(object):
    """docstring for MediaStatus"""
    def __init__(self, data, host):
        super(MediaStatus, self).__init__()
        self.host = host
        self.play_time = 0
        self.total_time = 0
        self.artist = None
        self.album = None
        self.track = None
        self.albumart_url = None
        self.initialize(data)

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self.total_time

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return "http://{}{}".format(self.host, self.albumart_url)

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self.artist

    @property
    def media_album(self):
        """Album of current playing media, music track only."""
        return self.album

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self.track

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.media_track

    def initialize(self, data):
        """ initialize variable from loaded data """
        for item in data:
            if hasattr(self, item):
                setattr(self, item, data[item])


class McDevice(object):
    """docstring for McDevice"""
    def __init__(self, ipAddress, udp_port=5005, **kwargs):
        super(McDevice, self).__init__()
        _LOGGER.debug("McDevice: %s", ipAddress)
        # construct message queue
        self.messages = queue.Queue()
        self.device_info = None
        self.device_features = None
        self.update_status_timer = None
        self._ip_address = ipAddress
        self._udp_port = udp_port
        self._interval = kwargs.get('mc_interval', 480)
        self._yamaha = None
        self._socket = None
        self.device_id = None
        self.initialize()

    def initialize(self):
        """initialize the object"""
        self.initialize_socket()
        self.device_info = self.get_device_info()
        _LOGGER.debug(self.device_info)
        self.device_id = (
            self.device_info.get('device_id')
            if self.device_info else "Unknown")
        self.initialize_worker()

    def initialize_socket(self):
        """initialize the socket"""
        self._socket = socket.socket(
            socket.AF_INET,     # IPv4
            socket.SOCK_DGRAM   # UDP
        )
        try:
            self._socket.bind(('', self._udp_port))
        except Exception as error:
            raise error
        else:
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
                    if self._yamaha:
                        # selected source first
                        if self._yamaha._source:
                            # remove selected source from index
                            input_list.remove(self._yamaha._source)
                            # put selected source at first
                            input_list = [self._yamaha._source] + input_list
                            _LOGGER.debug(
                                "source: %s input_list: %s",
                                self._yamaha._source, input_list
                            )
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
