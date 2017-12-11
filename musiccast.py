#!/usr/bin/env python
"""Demo pymusiccast."""
import time
import socket
import logging
import argparse
from pymusiccast import McDevice

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


def setup_parser():
    """Setup an ArgumentParser."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5005)
    parser.add_argument('-i', '--interval', type=int, default=480)
    parser.add_argument('host', type=str, help='hostname')
    return parser


def main():
    """Connect to a McDevice"""
    args = setup_parser().parse_args()
    host = getattr(args, "host")
    port = getattr(args, "port")
    ipv4 = socket.gethostbyname(host)
    interval = getattr(args, "interval")

    receiver = McDevice(ipv4, udp_port=port, mc_interval=interval)
    receiver.handle_status()

    # wait for UDP messages
    while True:
        time.sleep(0.2)


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        _LOGGER.info("Good bye.")
