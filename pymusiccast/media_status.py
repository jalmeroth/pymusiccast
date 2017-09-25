#!/usr/bin/env python
"""This file defines the MediaStatus object."""


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
