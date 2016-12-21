#!/usr/bin/env python3

import sys
import json
import atexit
import argparse

# TODO: complete Chunk Data packet

from .version import APP_NAME, APP_VERSION
from .server import MCServer

DEFAULT_CONFIG = {
    'max_connections': 32,
    'timeout': 15,
    "port": 25565,
    "ipv6": True,
    "online": False,
    "compression": 2,
    "difficulty": 1,
    "keepalive": {
        "send_interval": 10,
        "timeout": 30
    },
    "players": {
        "max": 10
    }
}


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

        for conf in config.get("servers", [{}]):
            conf.update(config)
            server = MCServer(conf)
            server.start()
            servers.append(server)

    except (KeyboardInterrupt, SystemExit, Exception) as e:
        print(e, file=sys.stderr)

    except (ValueError, KeyError) as e:
        print("Error parsing configuration: {}".format(e), file=sys.stderr)

if __name__ == "__main__":
    main()
