#!/usr/bin/env python3

import json
import uuid
import zlib
import numpy as np
from io import BytesIO
from urllib.parse import quote

from util import *
from player import Player

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
        print("decompressed packet: {}".format(buffer.read()))
        buffer.seek(0)

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
            if packet_id == 0x0B:
                return IncomingKeepAlive(conn, buffer)
            elif packet_id == 0x04:
                return ClientSettings(conn, buffer)
            elif packet_id == 0x09:
                return IncomingPluginMessage(conn, buffer)

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
        username = mc_string.read(self)

        compression = SetCompression(self.connection)
        compression.send()

        res = LoginSuccess(self.connection, username)
        res.send()

class LoginSuccess(OutgoingPacket):

    packet_id = 2
    def __init__(self, conn, username):
        super().__init__(conn)
        self.username = username

    def send(self):
        player = Player(self.connection, self.username)

        payload = mc_string(player.uuid).bytes()
        payload += mc_string(player.username).bytes()
        self._send(payload)

        self.connection.assign_player(player)
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

    packet_id = 0x0B
    def recv(self):
        token = int(mc_varint.read(self))
        self.connection.keepalive.callback(token)

class OutgoingKeepAlive(OutgoingPacket):

    packet_id = 0x1F
    def __init__(self, conn, token):
        super().__init__(conn)
        self.id = token

    def send(self):
        self._send(mc_varint(self.id))

class JoinGame(OutgoingPacket):

    packet_id = 0x23
    def __init__(self, conn, player):
        super().__init__(conn)
        self.player = player

    def send(self):
        print("join packet")
        payload = b''
        payload += bytes(self.player.entity.entity_id)
        payload += bytes(self.player.gamemode)
        payload += bytes(self.player.dimension)
        payload += bytes(self.player.difficulty)
        payload += bytes(mc_ubyte(self.player.connection.server.config.get("players", {}).get("max", 10)))
        payload += mc_string("default").bytes()
        payload += b'\x00'
        # payload = b'\x23\x00\x00\x00\xfc\x00\x00\x01\x14\x07\x64\x65\x66\x61\x75\x6c\x74\x00'
        self._send(payload)
        # safe_send(self.sock, b'\x13\x00\x23\x00\x00\x00\xfc\x00\x00\x01\x14\x07\x64\x65\x66\x61\x75\x6c\x74\x00')

class ClientSettings(IncomingPacket):

    packet_id = 0x04
    def recv(self):
        locale = mc_string.read(self)
        view_dist = mc_ubyte.read(self)
        chat_mode = mc_varint.read(self)
        chat_colours = mc_bool.read(self)
        skin_parts = mc_ubyte.read(self)
        main_hand = mc_varint.read(self)

class IncomingPluginMessage(IncomingPacket):

    packet_id = 0x09
    def recv(self):
        channel = mc_string.read(self)
        if channel == "MC|Brand":
            client_brand = mc_string.read(self)
            packet = OutgoingPluginMessage(self.connection, "MC|Brand", mc_string("claspymc").bytes())
            packet.send()

class OutgoingPluginMessage(OutgoingPacket):

    packet_id = 0x18
    def __init__(self, conn, channel, data):
        super().__init__(conn)
        self.channel = channel
        self.data = data

    def send(self):
        payload = b''
        payload += mc_string(self.channel).bytes()
        payload += self.data
        self._send(payload)

class Disconnect(OutgoingPacket):

    packet_id = 0x1A
    def __init__(self, conn, reason):
        super().__init__(conn)
        self.reason = mc_string(reason)

    def send(self):
        self._send(self.reason.bytes())
        self.connection.close()

class BasicPlayerUpdate(IncomingPacket):

    packet_id = 0x0F
    def recv(self):
        self.connection.player.on_ground = mc_bool.read(self)

class PlayerPositionUpdate(IncomingPacket):

    packet_id = 0x0C
    def recv(self):
        pos = np.array([0, 0, 0])
        pos[0] = mc_double.read(self)
        pos[1] = mc_double.read(self)
        pos[2] = mc_double.read(self)
        if isinstance(self.connection.player.position, np.array):
            diff = np.linalg.norm(pos - self.connection.player.position)
            if diff > 100:
                raise IllegalData("You moved too quickly!")

        self.connection.player.position = pos
        self.connection.player.on_ground = mc_bool.read(self)

class PlayerLookUpdate(IncomingPacket):

    packet_id = 0x0E
    def recv(self):
        self.connection.player.yaw = mc_float.read(self)
        self.connection.player.pitch = mc_float.read(self)
        self.connection.player.on_ground = mc_bool.read(self)

class PlayerPositionLookUpdate(IncomingPacket):

    packet_id = 0x0D
    def recv(self):
        pos = np.array([0, 0, 0])
        pos[0] = mc_double.read(self)
        pos[1] = mc_double.read(self)
        pos[2] = mc_double.read(self)
        if isinstance(self.connection.player.position, np.array):
            diff = np.linalg.norm(pos - self.connection.player.position)
            if diff > 100:
                raise IllegalData("You moved too quickly!")

        self.connection.player.position = pos
        self.connection.player.yaw = mc_float.read(self)
        self.connection.player.pitch = mc_float.read(self)
        self.connection.player.on_ground = mc_bool.read(self)

class ChunkData(OutgoingPacket):

    packet_id = 0x20
    def __init__(self, conn, chunk):
        super().__init__(conn)
        self.chunk = chunk  # chunk is an NBTFile

    def send(self):
        payload = b''
        payload += mc_int(self.chunk["Level"]["xPos"].value).bytes()
        payload += mc_int(self.chunk["Level"]["yPos"].value).bytes()
        n = 1 << (len(self.chunk["Level"]["Sections"]) + 1)
        payload += mc_varint(~n & (n - 1)).bytes()
        sections = b''
