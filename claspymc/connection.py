#!/usr/bin/env python3

import sys
import threading

from .packet import \
    SetCompression, LoginSuccess, JoinGame, \
    OutgoingPluginMessage, IncomingPacket, Disconnect
from .crypto import CryptoState
from .keepalive import KeepAlive
from .player import Player

from .net import ProtocolError, IllegalData
from .types import mc_varint, mc_string, States
from .version import APP_NAME, APP_VERSION

class MCConnection:

    closed = False
    version = mc_varint(-1)
    def __init__(self, server, conn_info):
        self.server = server
        self.config = server.config
        self._sock, self.addr = conn_info
        self._sock.settimeout(self.config.get("timeout") or 15)

        self.crypto = CryptoState(self)
        self.sock = self.crypto.sock

        self.keepalive = KeepAlive(self)

        self.player = None
        self.compression = -1
        self.state = States.HANDSHAKING

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def assign_player(self, username):
        self.player = Player(self, username, resolve_uuid=True)
        self.server.players.append(self.player)
        self.server.entities.append(self.player.entity)

    def join_game(self):

        SetCompression(self).send()
        LoginSuccess(self).send()

        self.state = States.PLAY
        JoinGame(self).send()

        impl_name = mc_string("{}/{}".format(APP_NAME, APP_VERSION)).bytes()
        OutgoingPluginMessage(self, "MC|Brand", impl_name).send()

        self.player.spawn()

    def _worker(self):

        try:
            while self.state != States.PLAY:
                if self.closed:
                    return

                pkt = IncomingPacket.from_connection(self)
                pkt.recv()

            self.keepalive.start()

            while True:
                if self.closed:
                    return

                pkt = IncomingPacket.from_connection(self)
                pkt.recv()
                self.keepalive.check()

        except IllegalData as e:
            print(e, file=sys.stderr)
            pkt = Disconnect(self, str(e))
            pkt.send()

        except ProtocolError as e:
            print(e, file=sys.stderr)

        finally:
            self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            self.server.connections = [s for s in self.server.connections if s]
            self.server.players = [p for p in self.server.players if p]
            print("term <{}:{}>: ({} left)".format(self.addr[0], self.addr[1], len(self.server.connections)))
            self._sock.close()

    def __bool__(self):
        return not self.closed
