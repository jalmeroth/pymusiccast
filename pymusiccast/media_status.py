#!/usr/bin/env python
"""This file defines the MediaStatus object."""
import logging
from datetime import datetime
_LOGGER = logging.getLogger(__name__)


class MediaStatus(object):
    """docstring for MediaStatus"""
    def __init__(self, data, host):
        super(MediaStatus, self).__init__()
        self.received = datetime.utcnow()
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
    def media_position(self):
        """Position of current playing media in seconds."""
        return self.play_time if self.media_duration else None

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

    def __eq__(self, new_media_status):
        """Comparison: are two objects equal"""
        # we handle MediaStatus-objects only
        if not isinstance(new_media_status, MediaStatus):
            return False

        # copy dictionary of object’s attributes.
        old = self.__dict__.copy()
        new = new_media_status.__dict__.copy()

        # remove play_times before later comparison
        old_play_time = old.pop('play_time')
        new_play_time = new.pop('play_time')

        diff_play_time = new_play_time - old_play_time
        # _LOGGER.debug("Playtime: %d", diff_play_time)

        # remove received datetimes before later comparison
        old_received = old.pop('received')
        new_received = new.pop('received')

        # how many seconds have passed between both status updates
        seconds_passed = int((new_received - old_received).total_seconds())
        # _LOGGER.debug("Seconds: %d", seconds_passed)

        # positive value of difference between time/position
        diff = abs(seconds_passed - diff_play_time)
        # _LOGGER.debug("DIFF: %d", diff)

        # we tolerate 10 seconds shift
        return False if diff > 10 else old == new

    def __ne__(self, new_media_status):
        """Comparison: are two objects not equal"""
        return not self == new_media_status
