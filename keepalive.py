#!/usr/bin/env python3

import threading
import time
from random import randint

from util import *
from packet import OutgoingKeepAlive

__author__ = 'Thomas Bell'

class Heartbeat:

    def __init__(self, conn, token):
        self.id = token
        self.sent = None
        self.connection = conn
        self.packet = OutgoingKeepAlive(self.connection, self.id)

    def send(self):
        self.sent = time.time()
        self.packet.send()

class KeepAlive:

    def __init__(self, conn):
        self.server = conn.server
        self.connection = conn
        self.sock = conn.sock
        self.config = conn.config.get("keepalive", {})
        self.heartbeats = []

        self.thread = threading.Thread(target=self._worker)

    def callback(self, token):
        for beat in self.heartbeats:
            if beat.id == token:
                self.heartbeats.remove(beat)

    def check(self):
        for beat in self.heartbeats:
            if beat.sent and time.time() - beat.sent > self.config.get("timeout", 30):
                raise ProtocolError("Player timed out")

    def _worker(self):
        try:
            while True:
                if not self.connection or not self.server:
                    break

                self.send()
                time.sleep(self.config.get("send_interval", 10))

        finally:
            self.connection.close()

    def send(self):
        heartbeat = Heartbeat(self.connection, randint(0, 127))
        heartbeat.send()
        self.heartbeats.append(heartbeat)

    def start(self):
        self.thread.start()
