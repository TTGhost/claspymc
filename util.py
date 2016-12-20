#!/usr/bin/env python3

import os
import sys
import struct
import socket
import appdirs
from nbt import nbt
from io import BytesIO
from enum import IntEnum

from version import APP_NAME, APP_AUTHOR, APP_VERSION
from ecache import Cache

cache = Cache((APP_NAME, APP_AUTHOR), "{}/{}".format(APP_NAME, APP_VERSION))

DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
def data_filename(server, filename):
    return os.path.join(server.config.get("data_dir", DATA_DIR), filename)

class States(IntEnum):
    HANDSHAKING = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3

class ProtocolError(Exception):
    pass

class IllegalData(ProtocolError):
    pass

def unsigned_to_signed(n, width):
    m = (1 << (width - 1))
    k = m - 1
    if n & m:
        return (n & k) - m
    else:
        return n & k

def signed_to_unsigned(n, width):
    m = (1 << width) - 1
    return n & m

def safe_recv(sock, buflen):
    buf = bytearray()
    if buflen == 0:
        return buf

    try:
        while len(buf) < buflen:
            new_data = sock.recv(buflen - len(buf))
            if not new_data:
                break

            buf += new_data

    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)

    if len(buf) < buflen:
        raise ProtocolError("connection closed")

    return buf

def safe_send(sock, buf):
    if type(buf) is str:
        buf = buf.encode("utf8")

    try:
        sock.sendall(buf)
    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)

def print_hex_dump(contents):
    for pos in range(0x0000, len(contents), 16):
        row = contents[pos:pos+16]
        print("| {:04x} | {: <47} | {: <16} |".format(
            pos,
            ' '.join('{:02x}'.format(x) for x in row),
            ''.join((chr(x) if (0x20 <= x < 0x7f) else '.') for x in row)
        ))

class mc_type:

    @staticmethod
    def _recv_unpack(fmt):
        @classmethod
        def recv(cls, sock):
            buf = safe_recv(sock, struct.calcsize(fmt))

            (res,) = struct.unpack(fmt, buf)

            return cls(res)

        return recv

    @staticmethod
    def _read_unpack(fmt):
        @classmethod
        def read(cls, fp):
            buf = fp.read(struct.calcsize(fmt))

            (res,) = struct.unpack(fmt, buf)

            return cls(res)

        return read

    @staticmethod
    def _bytes_pack(fmt):
        def __bytes__(self):
            try:
                return struct.pack(fmt, self)
            except struct.error:
                raise ProtocolError("invalid value for mc_type ({})".format(self.__class__.__name__))

        return __bytes__

    def bytes(self):
        return bytes(self)

    def send(self, sock):
        safe_send(sock, self.bytes())

class mc_varnum(mc_type, int):

    _width = None

    @classmethod
    def from_bytes(cls, buf):
        if not cls._width:
            raise NotImplementedError("{}._length not defined".format(cls.__name__))

        if len(buf) >= 32:
            raise ProtocolError("{} too long".format(cls.__name__))

        n = 0
        for e in buf[::-1]:
            n = (n << 7) | (e & 0x7f)

        return cls(unsigned_to_signed(n, cls._width))

    @classmethod
    def read(cls, fp):
        buf = fp.read(1)
        while buf[0] & 0x80 and len(buf) < 32:
            nxt = fp.read(1)
            if not nxt:
                break
            buf = nxt + buf

        return cls.from_bytes(buf)

    @classmethod
    def recv(cls, sock):
        buf = safe_recv(sock, 1)
        while buf[0] & 0x80 and len(buf) < 32:
            buf = safe_recv(sock, 1) + buf

        return cls.from_bytes(buf)

    def __bytes__(self):
        x = type(self)(signed_to_unsigned(self, self._width))
        length = len(x)
        buf = bytearray(length)
        for i,e in enumerate(buf):
            buf[i] = (x >> (7*i)) & 0x7f
            if i < length-1:
                buf[i] |= 0x80

        return bytes(buf)

    def __len__(self):
        length = 1
        while self >= (1 << (7*length)):
            length += 1

        return length

class mc_varint(mc_varnum):
    _width = 32

class mc_varlong(mc_varnum):
    _width = 64

class mc_string(mc_type, str):

    @staticmethod
    def read(fp):
        length = mc_varint.read(fp)

        try:
            s = fp.read(length).decode("utf8")
        except UnicodeDecodeError as e:
            print(e, file=sys.stderr)
            raise ProtocolError(e)

        return mc_string(s)

    @staticmethod
    def recv(sock):
        length = mc_varint.recv(sock)

        try:
            s = safe_recv(sock, length).decode("utf8")
        except UnicodeDecodeError as e:
            print(e, file=sys.stderr)
            raise ProtocolError(e)

        return mc_string(s)

    def bytes(self):
        res = self.encode("utf8")
        return bytes(mc_varint(len(res))) + res

class mc_bytes(mc_type, bytes):

    @staticmethod
    def read(fp):
        length = mc_varint.read(fp)
        array = fp.read(length)

        return mc_bytes(array)

    @staticmethod
    def recv(sock):
        length = mc_varint.recv(sock)
        array = safe_recv(sock, length)

        return mc_bytes(array)

    def bytes(self):
        return bytes(mc_varint(len(self))) + bytes(self)

class mc_pos(mc_type, list):

    @staticmethod
    def read(fp):
        n = mc_long.read(fp)

        x = unsigned_to_signed(n >> 38, 26)
        y = unsigned_to_signed(n >> 26, 12)
        z = unsigned_to_signed(n, 26)

        return mc_pos((x, y, z))

    @staticmethod
    def recv(sock):
        n = mc_long.recv(sock)

        x = unsigned_to_signed(n >> 38, 26)
        y = unsigned_to_signed(n >> 26, 12)
        z = unsigned_to_signed(n, 26)

        return mc_pos((x, y, z))

    @property
    def x(self): return self[0]
    @x.setter
    def x(self, v): self[0] = v

    @property
    def y(self): return self[1]
    @y.setter
    def y(self, v): self[1] = v

    @property
    def z(self): return self[2]
    @z.setter
    def z(self, v): self[2] = v

    def __bytes__(self):
        n = 0

        n |= (self.x & 0x3FFFFFF) << 38
        n |= (self.y & 0xFFF) << 26
        n |= (self.z & 0x3FFFFFF)

        return struct.pack("!Q")

class mc_vec3f(mc_type, tuple):
    pass

class mc_float(mc_type, float):
    read = mc_type._read_unpack("!f")
    recv = mc_type._recv_unpack("!f")
    __bytes__ = mc_type._bytes_pack("!f")

class mc_double(mc_type, float):  # heh
    read = mc_type._read_unpack("!d")
    recv = mc_type._recv_unpack("!d")
    __bytes__ = mc_type._bytes_pack("!d")

class mc_long(mc_type, int):
    read = mc_type._read_unpack("!q")
    recv = mc_type._recv_unpack("!q")
    __bytes__ = mc_type._bytes_pack("!q")

class mc_int(mc_type, int):
    read = mc_type._read_unpack("!i")
    recv = mc_type._recv_unpack("!i")
    __bytes__ = mc_type._bytes_pack("!i")

class mc_ushort(mc_type, int):
    read = mc_type._read_unpack("!H")
    recv = mc_type._recv_unpack("!H")
    __bytes__ = mc_type._bytes_pack("!H")

class mc_sshort(mc_type, int):
    read = mc_type._read_unpack("!h")
    recv = mc_type._recv_unpack("!h")
    __bytes__ = mc_type._bytes_pack("!h")

class mc_ubyte(mc_type, int):
    read = mc_type._read_unpack("!B")
    recv = mc_type._recv_unpack("!B")
    __bytes__ = mc_type._bytes_pack("!B")

class mc_sbyte(mc_type, int):
    read = mc_type._read_unpack("!b")
    recv = mc_type._recv_unpack("!b")
    __bytes__ = mc_type._bytes_pack("!b")

class mc_bool(mc_type, int):
    read = mc_type._read_unpack("!?")
    recv = mc_type._recv_unpack("!?")
    __bytes__ = mc_type._bytes_pack("!?")

class mc_slot(mc_type):

    id = mc_sshort(-1)
    count = mc_ubyte(0)
    damage = mc_ushort(0)
    nbt = None
    def __init__(self, item_id=mc_sshort(-1), count=mc_ubyte(0), damage=mc_ushort(0), buffer=None):
        self.id = item_id
        self.count = count
        self.damage = damage
        if buffer:
            self.nbt = nbt.TAG_Compound(buffer)

    def __bytes__(self):
        payload = b''
        payload += mc_sshort(self.id).bytes()
        if self.id == -1:
            return payload
        payload += mc_ubyte(self.count).bytes()
        payload += mc_ushort(0).bytes()
        if not self.nbt:
            payload += b'\x00'
            return payload
        else:
            payload += b'\x01'
            buf = BytesIO()
            self.nbt._render_buffer(buf)
            buf.seek(0)
            payload += buf.read()
            return payload

class mc_chunk_section(mc_type):

    def __init__(self, nbt_section):
        self.nbt = nbt_section

    def __bytes__(self):
        pass

