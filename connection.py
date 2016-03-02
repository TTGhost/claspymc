#!/usr/bin/env python3

import sys
import threading

from util import *
from packet import IncomingPacket

class MCConnection:

    closed = False
    version = mc_varint(-1)
    state = States.HANDSHAKING
    def __init__(self, server, conn_info):
        self.server = server
        self.config = server.config
        self.conn, self.addr = conn_info
        self.conn.settimeout(self.config.get("timeout") or 15)

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):

        while True:
            try:
                packet = IncomingPacket.from_connection(self)
                packet.recv()
            except ProtocolError as e:
                print(e, file=sys.stderr)
                break

        return self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            self.server.connections = [s for s in self.server.connections if s]
            print("term <{}:{}>: ({} left)".format(self.addr[0], self.addr[1], len(self.server.connections)))
            self.conn.close()

    def __bool__(self):
        return not self.closed
