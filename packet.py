#!/usr/bin/env python3

import json
from io import BytesIO

from util import *

class IncomingPacket:

    def __init__(self, conn, length):
        self.server = conn.server
        self.sock = conn.conn
        self.connection = conn

        self.length = length
        self.buffer = BytesIO(safe_recv(self.sock, self.length))

    def read(self, length):
        return self.buffer.read(length)

    def recv(self):
        raise NotImplementedError("incoming packet recv() not implemented")

    @staticmethod
    def from_connection(conn):
        length = mc_varint.recv(conn.conn)
        packet_id = mc_varint.recv(conn.conn)

        length -= len(packet_id)
        print("packet length {}, id {}".format(length, packet_id))
        print("conn state {}".format(conn.state))

        if conn.state == States.HANDSHAKING:
            if packet_id == 0x00:
                return HandshakePacket(conn, length)

        elif conn.state == States.STATUS:
            if packet_id == 0x00:
                return RequestPacket(conn, length)
            elif packet_id == 0x01:
                return PingPacket(conn, length)

        return UnknownPacket(conn, length)


class OutgoingPacket:

    packet_id = -1
    def __init__(self, conn):
        self.server = conn.server
        self.sock = conn.conn
        self.connection = conn

    def _send(self, payload):
        if self.packet_id == -1:
            raise NotImplementedError("packet id needs to be specified")

        if type(payload) is str:
            payload = mc_string(payload).bytes()
        elif isinstance(payload, mc_type):
            payload = bytes(payload)

        pid = mc_varint(self.packet_id)
        length = mc_varint(len(payload) + len(pid))

        length.send(self.sock)
        pid.send(self.sock)
        safe_send(self.sock, payload)

    def send(self):
        raise NotImplementedError("outgoing packet send() not implemented")

class UnknownPacket(IncomingPacket):

    def recv(self):
        raise ProtocolError("unknown packet")

class HandshakePacket(IncomingPacket):

    packet_id = 0
    def recv(self):
        self.connection.version = mc_varint.read(self)
        print("ver: {}".format(self.connection.version))
        host = mc_string.read(self)
        print("host: {}".format(host))
        port = mc_ushort.read(self)
        print("port: {}".format(port))
        self.connection.state = States(mc_varint.read(self))
        print("state: {}".format(self.connection.state))

class RequestPacket(IncomingPacket):

    packet_id = 0
    def recv(self):
        print("request packet")
        res = ResponsePacket(self.connection)
        res.send()

class ResponsePacket(OutgoingPacket):

    packet_id = 0
    def send(self):
        self._send(json.dumps(self.server.response_data()))

class PingPacket(IncomingPacket):

    packet_id = 1
    def recv(self):
        payload = mc_long.read(self)
        res = PongPacket(self.connection, payload)
        res.send()

class PongPacket(OutgoingPacket):

    packet_id = 1
    def __init__(self, conn, payload):
        super().__init__(conn)
        self.payload = payload

    def send(self):
        self._send(self.payload)
