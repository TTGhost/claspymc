#!/usr/bin/env python3

import json
import uuid
import zlib
from io import BytesIO
from urllib.parse import quote

from util import *

class IncomingPacket:

    def __init__(self, conn, buffer):
        self.server = conn.server
        self.sock = conn.conn
        self.connection = conn

        # self.buffer = BytesIO(safe_recv(self.sock, self.length))
        self.buffer = buffer

    def read(self, length):
        return self.buffer.read(length)

    def recv(self):
        raise NotImplementedError("incoming packet recv() not implemented")

    @staticmethod
    def from_connection(conn):
        packet_length = mc_varint.recv(conn.conn)

        if conn.compression < 0:
            packet_id = mc_varint.recv(conn.conn)
            length = packet_length - len(packet_id)
            buffer = BytesIO(safe_recv(conn.conn, length))

        else:
            length = mc_varint.recv(conn.conn)
            if length < conn.compression:
                raise ProtocolError("packet too small for compression")

            compress_length = packet_length - len(length)
            buffer = BytesIO(zlib.decompress(safe_recv(conn.conn, compress_length)))
            packet_id = mc_varint.read(buffer)

        print("packet length {}, id {}".format(length, packet_id))
        print("conn state {}".format(conn.state))

        if conn.state == States.HANDSHAKING:
            if packet_id == 0x00:
                return HandshakePacket(conn, buffer)

        elif conn.state == States.STATUS:
            if packet_id == 0x00:
                return RequestPacket(conn, buffer)
            elif packet_id == 0x01:
                return PingPacket(conn, buffer)

        elif conn.state == States.LOGIN:
            if packet_id == 0x00:
                return LoginStart(conn, buffer)

        elif conn.state == States.PLAY:
            if packet_id == 0x00:
                return IncomingKeepAlive(conn, buffer)

        return UnknownPacket(conn, buffer)


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
            payload = payload.bytes()

        pid = mc_varint(self.packet_id)
        payload = pid.bytes() + payload
        length = mc_varint(len(payload))

        if self.connection.compression < 0:
            length.send(self.sock)
            safe_send(self.sock, payload)
        else:
            if len(payload) >= self.connection.compression:
                payload = zlib.compress(payload)
            else:
                length = mc_varint(0)

            packet_length = mc_varint(len(payload) + len(length))

            packet_length.send(self.sock)
            length.send(self.sock)
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

class LoginStart(IncomingPacket):

    packet_id = 0
    def recv(self):
        print("login packet")
        self.connection.username = mc_string.read(self)

        compression = SetCompression(self.connection)
        compression.send()

        res = LoginSuccess(self.connection)
        res.send()

class LoginSuccess(OutgoingPacket):

    packet_id = 2
    def send(self):
        print(self.connection.username)
        user_name = quote(str(self.connection.username))
        try:
            res = cache.get("https://api.mojang.com/users/profiles/minecraft/{}".format(user_name))
            user_id = json.loads(res)["id"]
        except:
            user_id = str(uuid.uuid4())

        payload = mc_string(user_id).bytes()
        payload += mc_string(user_name).bytes()
        self._send(payload)

        self.connection.state = States.PLAY

class SetCompression(OutgoingPacket):

    packet_id = 3
    def __init__(self, conn, threshold=None):
        super().__init__(conn)
        if threshold is None:
            threshold = conn.config.get("compression", -1)
        self.threshold = threshold

    def send(self):
        print("compression packet")
        self._send(mc_varint(self.threshold))
        self.connection.compression = self.threshold

class IncomingKeepAlive(IncomingPacket):

    packet_id = 0
    def recv(self):
        token = int(mc_varint.read(self))
        self.connection.keepalive.callback(self, token)

class OutgoingKeepAlive(OutgoingPacket):

    packet_id = 0
    def __init__(self, conn, token):
        super().__init__(conn)
        self.id = token

    def send(self):
        self._send(mc_varint(self.id))
