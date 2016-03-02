#!/usr/bin/env python3

import json
from util import *

class PacketHandler:

    def __init__(self, pack):
        self.server = pack.server
        self.pack = pack
        self.sock = pack.sock
        self.connection = pack.connection

    def recv(self):
        raise ProtocolError("invalid packet type recv ({})".format(self.pack.packet_id))

    def send(self):
        payload = bytes(self)
        mc_varint(len(payload)).send(self.sock)
        mc_varint(self.packet_id).send(self.sock)
        mc_type._safe_send(self.sock, payload)

class HandshakePacket(PacketHandler):

    def recv(self):
        self.connection.version = mc_varint.recv(self.sock)
        host = mc_string.recv(self.sock)
        port = mc_ushort.recv(self.sock)
        self.connection.state = mc_varint.recv(self.sock)
        print("state change: {}".format(self.connection.state))

class RequestPacket(PacketHandler):

    def recv(self):
        ResponsePacket(self.sock).send()

class ResponsePacket(PacketHandler):

    def __bytes__(self):
        return json.dumps(self.server.response_data()).encode("utf8")

class PingPacket(PacketHandler):

    packet_id = 0
    def recv(self):
        self.ping_id = mc_long.recv(self.sock)
        self.send(self.sock)

    def __bytes__(self):
        return bytes(self.ping_id)


class Packet:

    def __init__(self, conn):
        self.server = conn.server
        self.connection = conn
        self.sock = conn.conn

    def recv(self):
        self.length = mc_varint.recv(self.sock)
        self.packet_id = mc_varint.recv(self.sock)
        self.handler = PacketHandler(self)

        print("packet id: {}".format(self.packet_id))

        if self.connection.state == States.HANDSHAKING:
            if self.packet_id == 0x00:
                self.handler = HandshakePacket(self)

        elif self.connection.state == States.STATUS:
            if self.packet_id == 0x00:
                self.handler = RequestPacket(self)
            elif self.packet_id == 0x01:
                self.handler = PingPacket(self)

        self.handler.recv()
