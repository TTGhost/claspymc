#!/usr/bin/env python3

import socket
import threading

from .connection import MCConnection
from .crypto import generate_keys
from .world import MCWorld

class MCServer:

    PROTOCOL = 107
    PROTOCOL_NAME = "1.9"
    closed = False
    def __init__(self, config):
        self.config = config
        af = socket.AF_INET6 if config.get("ipv6", False) else socket.AF_INET
        self.sock = socket.socket(af, socket.SOCK_STREAM)
        self.connections = []

        self.players = []
        self.entities = []
        self.private_key, self.public_key = generate_keys()
        self.world = MCWorld(config.get("world", None))

        self.thread = threading.Thread(target=self._worker)

    def start(self):
        self.thread.start()

    def join(self, *args, **kwargs):
        self.thread.join(*args, **kwargs)

    def _worker(self):
        host = self.config.get("host", "")
        port = self.config.get("port", 25565)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(self.config.get("max_connections", 32))

        print("est. <{}:{}>".format(host, port))

        while True:
            conn, addr = self.sock.accept()

            if len(self.connections) < self.config.get("max_connections", 32):
                self.connections.append(MCConnection(self, (conn, addr)))
                print("open <{}:{}>: ({} total)".format(addr[0], addr[1], len(self.connections)))
            else:
                # send unavailable connection error
                pass

    def response_data(self):
        d = {
            "version": {
                "name": self.PROTOCOL_NAME,
                "protocol": self.PROTOCOL
            },
            "players": {
                "max": self.config.get("players", {}).get("max", 10),
                "online": len([p for p in self.players if p])
            },
            "description": {
                "text": self.config.get("description", "A Minecraft Server running with ClaspyMC")
            }
        }
        return d

    def close(self):
        if not self.closed:
            for conn in self.connections:
                if conn: conn.close()
            self.sock.close()
            self.closed = True

    def __bool__(self):
        return not self.closed
