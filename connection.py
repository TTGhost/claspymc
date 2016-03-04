#!/usr/bin/env python3

import sys
import threading

from util import *
from packet import IncomingPacket, JoinGame, Disconnect
from keepalive import KeepAlive

class MCConnection:

    closed = False
    version = mc_varint(-1)
    state = States.HANDSHAKING
    player = None
    compression = -1
    def __init__(self, server, conn_info):
        self.server = server
        self.config = server.config
        self.conn, self.addr = conn_info
        self.conn.settimeout(self.config.get("timeout") or 15)

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

        self.keepalive = KeepAlive(self)

    def assign_player(self, player):
        self.player = player
        self.server.players.append(player)

        packet = JoinGame(self, player)
        packet.send()

    def _worker(self):

        try:
            while self.state != States.PLAY:
                packet = IncomingPacket.from_connection(self)
                packet.recv()

            self.keepalive.start()

            while True:
                packet = IncomingPacket.from_connection(self)
                packet.recv()
                self.keepalive.check()

        except IllegalData as e:
            print(e, file=sys.stderr)
            packet = Disconnect(self, str(e))
            packet.send()

        except ProtocolError as e:
            print(e, file=sys.stderr)

        return self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            self.server.connections = [s for s in self.server.connections if s]
            self.server.players = [p for p in self.server.players if p]
            print("term <{}:{}>: ({} left)".format(self.addr[0], self.addr[1], len(self.server.connections)))
            self.conn.close()

    def __bool__(self):
        return not self.closed
