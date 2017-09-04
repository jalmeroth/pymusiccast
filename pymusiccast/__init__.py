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


def message_worker(device):
    """Loop through messages and pass them on to right device"""
    q = device._messages

    while True:

        if not q.empty():
            message = q.get()

            data = {}
            try:
                data = json.loads(message.decode("utf-8"))
            except ValueError:
                _LOGGER.error("Received invalid message: %s", message)

            if 'device_id' in data:
                device_id = data.get('device_id')
                if device_id == device._device_id:
                    device.handleEvent(data)
                else:
                    _LOGGER.warning("Received message for unknown device.")
            q.task_done()

        time.sleep(0.2)


def socket_worker(sock, q):
    """Socket Loop that fills message queue"""
    while True:
        data, addr = sock.recvfrom(1024)    # buffer size is 1024 bytes
        _LOGGER.debug("received message: %s from %s", data, addr)
        q.put(data)
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


class mcDevice(object):
    """docstring for mcDevice"""
    def __init__(self, ipAddress, udp_port=5005, **kwargs):
        super(mcDevice, self).__init__()
        _LOGGER.debug("mcDevice: %s", ipAddress)
        # construct message queue
        self._messages = queue.Queue()
        self.deviceInfo = None
        self.deviceFeatures = None
        self.updateStatus_timer = None
        self._ipAddress = ipAddress
        self._udp_port = udp_port
        self._interval = kwargs.get('mc_interval', 480)
        self._yamaha = None
        self._socket = None
        self._device_id = None
        self.initialize()

    def initialize(self):
        """initialize the object"""
        self.initialize_socket()
        self.deviceInfo = self.getDeviceInfo()
        _LOGGER.debug(self.deviceInfo)
        self._device_id = (
            self.deviceInfo.get('device_id') if self.deviceInfo else "Unknown")
        self.initialize_worker()
        # self.updateStatus()

    def initialize_socket(self):
        """initialize the socket"""
        self._socket = socket.socket(
            socket.AF_INET,     # IPv4
            socket.SOCK_DGRAM   # UDP
        )
        try:
            self._socket.bind(('', self._udp_port))
        except Exception as e:
            raise e
        else:
            _LOGGER.debug("Socket open.")
            _LOGGER.debug("Starting Socket Thread.")
            socket_thread = threading.Thread(
                name="SocketThread", target=socket_worker,
                args=(self._socket, self._messages,))
            socket_thread.setDaemon(True)
            socket_thread.start()

    def initialize_worker(self):
        """initialize the worker thread"""
        _LOGGER.debug("Starting Worker Thread.")
        worker_thread = threading.Thread(
            name="WorkerThread", target=message_worker, args=(self,))
        worker_thread.setDaemon(True)
        worker_thread.start()

    def getDeviceInfo(self):
        """Get info from device"""
        reqUrl = ENDPOINTS["getDeviceInfo"].format(self._ipAddress)
        return self.request(reqUrl)

    def getFeatures(self):
        """Get features from device"""
        reqUrl = ENDPOINTS["getFeatures"].format(self._ipAddress)
        return self.request(reqUrl)

    def getStatus(self):
        """Get status from device"""
        headers = {
            "X-AppName": "MusicCast/0.1(python)",
            "X-AppPort": str(self._udp_port)
        }
        reqUrl = ENDPOINTS["getStatus"].format(self._ipAddress)
        return self.request(reqUrl, headers=headers)

    def getPlayInfo(self):
        """Get play info from device"""
        reqUrl = ENDPOINTS["getPlayInfo"].format(self._ipAddress)
        return self.request(reqUrl)

    def handleMain(self, message):
        """Handles 'main' in message"""
        # _LOGGER.debug("message: {}".format(message))
        if self._yamaha:
            if 'power' in message:
                _LOGGER.debug("Power: %s", message.get('power'))
                self._yamaha._power = (
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
                self._yamaha._volume = volume
                self._yamaha._volume_max = message.get('max_volume')
            if 'mute' in message:
                _LOGGER.debug("Mute: %s", message.get('mute'))
                self._yamaha._mute = message.get('mute', False)
        else:
            _LOGGER.debug("No yamaha-obj found")

    def handleNetUSB(self, message):
        """Handles 'netusb' in message"""
        # _LOGGER.debug("message: {}".format(message))
        if self._yamaha:
            if 'play_info_updated' in message:
                playInfo = self.getPlayInfo()
                # _LOGGER.debug(playInfo)
                if playInfo:
                    self._yamaha._media_status = MediaStatus(
                        playInfo, self._ipAddress)
                    playback = playInfo.get('playback')
                    # _LOGGER.debug("Playback: {}".format(playback))
                    if playback == "play":
                        self._yamaha._status = STATE_PLAYING
                    elif playback == "stop":
                        self._yamaha._status = STATE_IDLE
                    elif playback == "pause":
                        self._yamaha._status = STATE_PAUSED
                    else:
                        self._yamaha._status = STATE_UNKNOWN

    def handleFeatures(self, deviceFeatures):
        """Handles features of the device"""
        if deviceFeatures and 'zone' in deviceFeatures:
            for zone in deviceFeatures['zone']:
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
                        self._yamaha._source_list = input_list
                    break

    def handleEvent(self, message):
        """Dispatch all event messages"""
        # _LOGGER.debug(message)
        if 'main' in message:
            self.handleMain(message['main'])

        if 'netusb' in message:
            self.handleNetUSB(message['netusb'])

        if self._yamaha:                                    # Push updates
            # _LOGGER.debug("Push updates")
            self._yamaha.schedule_update_ha_state()

    def updateStatus(self, push=True):
        """Update device status"""
        status = self.getStatus()
        if status:
            _LOGGER.debug(
                "updateStatus: firing again in %d seconds", self._interval)
            self.updateStatus_timer = threading.Timer(
                self._interval, self.updateStatus)
            self.updateStatus_timer.setDaemon(True)
            self.updateStatus_timer.start()
            self.handleMain(status)

            # get features only once
            if not self.deviceFeatures:
                self.deviceFeatures = self.getFeatures()
                _LOGGER.debug(self.deviceFeatures)
                self.handleFeatures(self.deviceFeatures)

        if self._yamaha and push:                           # Push updates
            # _LOGGER.debug("Push updates")
            self._yamaha.schedule_update_ha_state()

    def setYamahaDevice(self, obj):
        """Set reference to device in HASS"""
        _LOGGER.debug("setYamahaDevice: %s", obj)
        self._yamaha = obj

    def setPower(self, power):
        """Send Power command."""
        reqUrl = ENDPOINTS["setPower"].format(self._ipAddress)
        params = {"power": "on" if power else "standby"}
        return self.request(reqUrl, params=params)

    def setMute(self, mute):
        """Send mute command."""
        reqUrl = ENDPOINTS["setMute"].format(self._ipAddress)
        params = {"enable": "true" if mute else "false"}
        return self.request(reqUrl, params=params)

    def setVolume(self, volume):
        """Send Volume command."""
        reqUrl = ENDPOINTS["setVolume"].format(self._ipAddress)
        params = {"volume": int(volume)}
        return self.request(reqUrl, params=params)

    def setInput(self, inputId):
        """Send Input command."""
        reqUrl = ENDPOINTS["setInput"].format(self._ipAddress)
        params = {"input": inputId}
        return self.request(reqUrl, params=params)

    def setPlayback(self, playback):
        """Send Playback command."""
        reqUrl = ENDPOINTS["setPlayback"].format(self._ipAddress)
        params = {"playback": playback}
        return self.request(reqUrl, params=params)

    def request(self, url, *args, **kwargs):
        """Do the HTTP Request and return data"""
        method = kwargs.get('method', 'GET')
        timeout = kwargs.pop('timeout', 10)  # hass default timeout
        try:
            r = requests.request(method, url, *args, timeout=timeout, **kwargs)
        except Exception as e:
            _LOGGER.error(e)
        else:
            try:
                data = r.json()
            except Exception as e:
                _LOGGER.error(e)
            else:
                _LOGGER.debug(json.dumps(data))
                return data

    def __del__(self):
        if self._socket:
            _LOGGER.debug("Closing Socket.")
            self._socket.close()
