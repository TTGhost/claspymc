#!/usr/bin/env python3

import json
import random
import zlib
from io import BytesIO

import numpy as np

from .net import \
    safe_recv, safe_send, \
    ProtocolError, IllegalData
from .util import print_hex_dump
from .types import \
    mc_varint, mc_string, mc_nettype, \
    mc_ushort, mc_long, mc_bytes, \
    mc_ubyte, mc_int, mc_bool, \
    mc_sbyte, mc_double, mc_float, \
    mc_vec3f, mc_pos, States, Gamemode, nbt_to_bytes

class IncomingPacket:

    PLAY_PACKET_MAP = {}

    def __init__(self, conn, buffer):
        self.server = conn.server
        self.sock = conn.sock
        self.connection = conn
        self.config = conn.config
        self.player = conn.player

        # self.buffer = BytesIO(safe_recv(self.sock, self.length))
        self.buffer = buffer

    def read(self, length=None):
        return self.buffer.read(length)

    def recv(self):
        raise NotImplementedError("incoming packet recv() not implemented")

    @staticmethod
    def from_connection(conn):
        packet_length = mc_varint.recv(conn.sock)

        if conn.compression < 0:
            packet_id = mc_varint.recv(conn.sock)
            length = packet_length - len(packet_id)
            buffer = BytesIO(safe_recv(conn.sock, length))

        else:
            length = mc_varint.recv(conn.sock)
            if length < conn.compression:
                raise ProtocolError("packet too small for compression")

            compress_length = packet_length - len(length)
            buffer = BytesIO(zlib.decompress(safe_recv(conn.sock, compress_length)))
            packet_id = mc_varint.read(buffer)

        if packet_id != IncomingKeepAlive.packet_id or conn.state != States.PLAY:
            print("RECV PACKET (length={}, id={}, state={})".format(length, packet_id, conn.state))
            print_hex_dump(buffer.read())
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
            cls = IncomingPacket.PLAY_PACKET_MAP.get(packet_id, None)
            if cls is not None and type(cls) == type:
                return cls(conn, buffer)

        return UnknownPacket(conn, buffer)


class OutgoingPacket:

    packet_id = -1
    def __init__(self, conn):
        self.server = conn.server
        self.sock = conn.sock
        self.connection = conn
        self.config = conn.config
        self.player = conn.player

    def _send(self, payload):
        if type(payload) is str:
            payload = mc_string(payload).bytes()
        elif isinstance(payload, mc_nettype):
            payload = payload.bytes()

        orig_payload = payload

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

        if pid != OutgoingKeepAlive.packet_id:
            print("SENT PACKET (length={}, id={}, state={})".format(length, pid, self.connection.state))
            print_hex_dump(orig_payload)

    def send(self):
        raise NotImplementedError("outgoing packet send() not implemented")

class UnknownPacket(IncomingPacket):

    def recv(self):
        # raise ProtocolError("unknown packet")
        print("UNHANDLED")

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

        self.connection.assign_player(username)

        if self.config.get("online", False):
            res = EncryptionRequest(self.connection)
            res.send()

        else:
            self.connection.join_game()

class EncryptionRequest(OutgoingPacket):

    packet_id = 1
    def send(self):
        print("making encryption request")

        public_key = self.connection.crypto.get_encrypted_key_info()
        verify_token = self.connection.crypto.verify_token

        payload = mc_string("").bytes()
        payload += mc_bytes(public_key).bytes()
        payload += mc_bytes(verify_token).bytes()
        self._send(payload)

class EncryptionResponse(IncomingPacket):

    packet_id = 1
    def recv(self):
        shared_secret = bytes(mc_bytes.read(self))
        verify_token = bytes(mc_bytes.read(self))

        if verify_token != self.connection.crypto.verify_token:
            raise IllegalData("Verify tokens do not match!")

        if len(shared_secret) != 16:
            raise IllegalData("Invalid shared secret!")

        self.connection.crypto.init_aes(shared_secret)

        login_hash = self.connection.crypto.generate_login_hash(shared_secret)
        self.connection.player.verify(login_hash)

        self.connection.join_game()

class LoginSuccess(OutgoingPacket):

    packet_id = 2
    def send(self):
        payload = mc_string(self.connection.player.uuid).bytes()
        payload += mc_string(self.connection.player.username).bytes()
        self._send(payload)

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
    def send(self):
        print("join packet")
        payload = b''
        payload += mc_int(self.player.entity.entity_id).bytes()
        payload += mc_ubyte(self.player.entity.gamemode).bytes()
        payload += mc_sbyte(self.player.entity.dimension).bytes()
        payload += mc_ubyte(self.server.world.level.difficulty).bytes()
        payload += mc_ubyte(self.config.get("players", {}).get("max", 10)).bytes()
        payload += mc_string("default").bytes()
        payload += mc_bool(False).bytes()
        self._send(payload)

class ClientStatus(IncomingPacket):

    RESPAWN = 0
    REQUEST_STATS = 1
    OPEN_INVENTORY = 2

    packet_id = 0x03
    def recv(self):
        action_id = mc_varint.read(self)

class ClientSettings(IncomingPacket):

    packet_id = 0x04
    def recv(self):
        self.player.locale = mc_string.read(self)
        self.player.view_distance = mc_ubyte.read(self)
        self.player.chat_mode = mc_varint.read(self)
        self.player.chat_colours = mc_bool.read(self)
        self.player.skin_parts = mc_ubyte.read(self)
        self.player.right_handed = bool(mc_varint.read(self))

class IncomingPluginMessage(IncomingPacket):

    packet_id = 0x09
    def recv(self):
        channel = mc_string.read(self)

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

class ServerDifficulty(OutgoingPacket):

    packet_id = 0x0D
    def send(self):
        self._send(mc_ubyte(self.server.world.level.difficulty).bytes())

class SpawnPosition(OutgoingPacket):

    packet_id = 0x43
    def send(self):
        self._send(mc_pos(self.server.world.level.spawn_position).bytes())

class OutgoingPlayerAbilities(OutgoingPacket):

    packet_id = 0x2B
    def send(self):
        payload = b''
        abilities = 0
        if self.player.entity.abilities.invulnerable:
            abilities |= 0x01
        if self.player.entity.abilities.is_flying:
            abilities |= 0x02
        if self.player.entity.abilities.can_fly:
            abilities |= 0x04
        if self.player.entity.gamemode == Gamemode.CREATIVE:
            abilities |= 0x08

        payload += mc_sbyte(abilities).bytes()
        payload += mc_float(self.player.entity.abilities.fly_speed).bytes()
        payload += mc_float(self.player.entity.abilities.walk_speed).bytes()
        self._send(payload)

class BasicPlayerUpdate(IncomingPacket):

    packet_id = 0x0F
    def recv(self):
        self.connection.player.entity.on_ground = mc_bool.read(self)

class PlayerPositionUpdate(IncomingPacket):

    packet_id = 0x0C
    def recv(self):
        pos = np.array([0, 0, 0])
        pos[0] = mc_double.read(self)
        pos[1] = mc_double.read(self)
        pos[2] = mc_double.read(self)
        if isinstance(self.player.entity.position, np.array):
            diff = np.linalg.norm(pos - self.connection.player.position)
            if diff > 100:
                raise IllegalData("You moved too quickly!")

        self.player.entity.position = mc_vec3f(pos)
        self.player.entity.on_ground = mc_bool.read(self)

class PlayerLookUpdate(IncomingPacket):

    packet_id = 0x0E
    def recv(self):
        self.player.entity.yaw = mc_float.read(self)
        self.player.entity.pitch = mc_float.read(self)
        self.player.entity.on_ground = mc_bool.read(self)

class IncomingPlayerPositionLook(IncomingPacket):

    packet_id = 0x0D
    def recv(self):
        pos = np.array([0.0, 0.0, 0.0])
        pos[0] = mc_double.read(self)
        pos[1] = mc_double.read(self)
        pos[2] = mc_double.read(self)
        if isinstance(self.player.entity.position, np.ndarray):
            diff = np.linalg.norm(pos - self.connection.player.position)
            if diff > 100:
                raise IllegalData("You moved too quickly!")

        self.player.entity.position = pos
        self.player.entity.yaw = mc_float.read(self)
        self.player.entity.pitch = mc_float.read(self)
        self.player.entity.on_ground = mc_bool.read(self)

class OutgoingPlayerPositionLook(OutgoingPacket):

    X_RELATIVE = 0x01
    Y_RELATIVE = 0x02
    Z_RELATIVE = 0x04
    PITCH_RELATIVE = 0x08
    YAW_RELATIVE = 0x10

    packet_id = 0x2E
    def __init__(self, conn, pos=None, yaw=None, pitch=None, flags=0):
        super().__init__(conn)
        self.pos = pos
        self.yaw = yaw
        self.pitch = pitch
        self.flags = flags
        if self.flags & (self.X_RELATIVE | self.Y_RELATIVE | self.Z_RELATIVE)\
                and self.pos is None:
            raise ValueError("If position update is relative, new pos must be specified.")

        if self.flags & self.PITCH_RELATIVE and self.pitch is None:
            raise ValueError("If pitch is relative, new pitch must be specified.")

        if self.flags & self.YAW_RELATIVE and self.yaw is None:
            raise ValueError("if yaw is relative, new yaw must be specified.")

    def send(self):
        payload = b''
        last_pos = mc_vec3f(self.player.entity.position)
        last_pitch = self.player.entity.pitch
        last_yaw = self.player.entity.yaw

        pos = mc_vec3f(self.pos if self.pos is not None else last_pos)
        pitch = self.pitch if self.pitch is not None else last_pitch
        yaw = self.yaw if self.pitch is not None else last_yaw

        if self.flags & self.X_RELATIVE:
            pos.x -= last_pos.x
        if self.flags & self.Y_RELATIVE:
            pos.y -= last_pos.y
        if self.flags & self.Z_RELATIVE:
            pos.z -= last_pos.z
        if self.flags & self.PITCH_RELATIVE:
            pitch -= last_pitch
        if self.flags & self.YAW_RELATIVE:
            yaw -= last_yaw

        payload += mc_double(pos.x).bytes()
        payload += mc_double(pos.y).bytes()
        payload += mc_double(pos.z).bytes()
        payload += mc_float(yaw).bytes()
        payload += mc_float(pitch).bytes()
        payload += mc_sbyte(self.flags).bytes()

        teleport_id = random.randint(1, 2**24-1)
        self.player.teleport_ids.append(teleport_id)
        payload += mc_varint(teleport_id).bytes()

        self._send(payload)

class TeleportConfirm(IncomingPacket):

    packet_id = 0x00
    def recv(self):
        teleport_id = int(mc_varint.read(self))
        if teleport_id in self.player.teleport_ids:
            self.player.teleport_ids.remove(int(teleport_id))

class ChunkData(OutgoingPacket):

    packet_id = 0x20
    def __init__(self, conn, x, z):
        super().__init__(conn)
        self.x = x
        self.z = z
        self.chunk = self.server.world.get_chunk(x, z)

    def send(self):
        payload = b''
        payload += mc_int(self.x).bytes()
        payload += mc_int(self.z).bytes()
        payload += mc_bool(True).bytes()
        bitmask = 0
        biomes = self.chunk.biomes.bytes()
        size = len(biomes)
        sections = [b'' for i in range(0, 256, 16)]
        print(self.chunk.sections)
        for section in self.chunk.sections:
            bitmask |= (1 << section.y_index)
            s_bytes = section.bytes()
            size += len(s_bytes)
            sections[section.y_index] = s_bytes

        payload += mc_varint(bitmask).bytes()
        payload += mc_varint(size).bytes()
        payload += b''.join(sections)
        payload += biomes

        entities = b''
        for entity in self.chunk.tile_entities:
            entities += nbt_to_bytes(entity.to_nbt())

        # hacky workaround (vanilla client complains of 1 byte extra, commenting this out
        # makes it work)
        #payload += mc_varint(len(self.chunk.tile_entities)).bytes()
        #payload += entities
        self._send(payload)


IncomingPacket.PLAY_PACKET_MAP = {
    0x00: TeleportConfirm,
    # 0x01: TabComplete,
    # 0x02: IncomingChatMessage,
    0x03: ClientStatus,
    0x04: ClientSettings,
    # 0x05: ConfirmTransaction,
    # 0x06: EnchantItem,
    # 0x07: ClickWindow,
    # 0x08: CloseWindow,
    0x09: IncomingPluginMessage,
    # 0x0A: UseEntity,
    0x0B: IncomingKeepAlive,
    # 0x0C: IncomingPlayerPosition,
    0x0D: IncomingPlayerPositionLook,
    # 0x0E: IncomingPlayerLook,
    # 0x0F: PlayerOnGround,
    # 0x10: IncomingVehicleMove,
    # 0x11: SteerBoat,
    # 0x12: IncomingPlayerAbilities,
    # 0x13: PlayerDigging,
    # 0x14: EntityAction,
    # 0x15: PlayerInput,
    # 0x16: ResourcePackStatus
    # 0x17: IncomingHeldItemChange,
    # 0x18: CreativeInventoryAction,
    # 0x19: UpdateSign,
    # 0x1A: IncomingAnimation,
    # 0x1B: SpectatePlayer,
    # 0x1C: BlockPlacement,
    # 0x1D: UseItem
}
