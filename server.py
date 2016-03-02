#!/usr/bin/env python3

import socket
import threading

from util import *
from connection import MCConnection

class MCServer:

    PROTOCOL = 107
    PROTOCOL_NAME = "1.9"
    closed = False
    def __init__(self, config):
        self.config = config
        af = socket.AF_INET6 if config.get("ipv6", False) else socket.AF_INET
        self.sock = socket.socket(af, socket.SOCK_STREAM)
        self.connections = []
        self.thread = threading.Thread(target=self._worker)
        self.thread.start()
        print("Started server")

        self.players = []

    def _worker(self):
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.config.get("host", ""), self.config.get("port", 80)))
        self.sock.listen(self.config.get("max_connections", 32))

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
