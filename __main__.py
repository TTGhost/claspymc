#!/usr/bin/env python3

import sys
import json
import atexit
import argparse

__version__ = (0, 1, 0)
__version_info__ = ".".join(map(str, __version__))

APP_NAME = "claspymc"
APP_AUTHOR = "bell345"
APP_VERSION = __version_info__
PYTHON_VERSION = ".".join(map(str, sys.version_info[:3]))

DEFAULT_CONFIG = {
    'max_connections': 32,
    'timeout': 15,
    'servers': [
        {
            "port": 8080,
            "ipv6": True
        }
    ]
}

from server import MCServer

servers = []
def cleanup():
    for server in servers:
        if server: server.close()

atexit.register(cleanup)

def main():

    parser = argparse.ArgumentParser(prog=APP_NAME,
            description="A class-based lightweight Minecraft server written in Python 3.",
            epilog="(C) Thomas Bell 2016, MIT License. \"Minecraft\" is a trademark of Mojang AB.")
    parser.add_argument("--version", action="version", version=APP_VERSION)

    parser.add_argument("-c", "--config", default=None, type=argparse.FileType('r'),
            help="The JSON formatted configuration file.")
    args = parser.parse_args()

    try:
        config = DEFAULT_CONFIG
        if args.config:
            config.update(json.load(args.config))

        for conf in config.get("servers", []):
            conf.update(config)
            servers.append(MCServer(conf))

    except (KeyboardInterrupt, SystemExit, Exception) as e:
        print(e, file=sys.stderr)

    except (ValueError, KeyError) as e:
        print("Error parsing configuration: {}".format(e), file=sys.stderr)

if __name__ == "__main__":
    main()
