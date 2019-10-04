#!/usr/bin/env python
"""Provides routines for Multiroom-Linking."""
import argparse
import logging

from pymusiccast.dist import DistGroup

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


def setup_parser():
    """Set-up an ArgumentParser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-c", "--client", action="append", type=str)
    parser.add_argument("-m", "--master", type=str)
    return parser


def main():
    """Provide main routine."""
    args = setup_parser().parse_args()
    if getattr(args, "debug"):
        _LOGGER.setLevel(logging.DEBUG)
    _LOGGER.debug(args)
    master = getattr(args, "master")
    clients = getattr(args, "client")
    dist_group = DistGroup(master, clients)
    while True:
        print(
            5 * "=" + "Actions" + 5 * "=" + "\n"
            "0. link group" + "\n"
            "1. print master" + "\n"
            "2. print clients" + "\n"
            "3. unlink group" + "\n"
        )
        selection = input("Chose Action: ")
        if selection == "0":  # link group
            print(dist_group.link_group())
        elif selection == "1":  # print master
            print(dist_group.master)
        elif selection == "2":  # print clients
            print(dist_group.clients)
        elif selection == "3":  # unlink group
            print(dist_group.unlink_group())
        else:
            pass


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        _LOGGER.info("Good bye.")
