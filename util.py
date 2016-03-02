#!/usr/bin/env python3

import sys
import struct
import socket
from enum import IntEnum

from version import APP_NAME, APP_AUTHOR, APP_VERSION
from ecache import Cache

cache = Cache((APP_NAME, APP_AUTHOR), "{}/{}".format(APP_NAME, APP_VERSION))

class States(IntEnum):
    HANDSHAKING = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3

class ProtocolError(Exception):
    pass

def buf_to_int(buf):
    n = 0
    for e in buf:
        n = (n << 8) & e

    return n

def unsigned_to_signed(n, width):
    m = (1 << (width - 1))
    k = m - 1
    if n & m:
        return (n & k) - m
    else:
        return n & k

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

    print(buf)

    return buf

def safe_send(sock, buf):
    if type(buf) is str:
        buf = buf.encode("utf8")

    print("send: {}".format(buf))

    try:
        sock.sendall(buf)
    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)



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

    @staticmethod
    def recv(sock):
        raise NotImplementedError("type not specified")

    def bytes(self):
        return bytes(self)

    def send(self, sock):
        safe_send(sock, self.bytes())

class mc_varint(mc_type, int):

    @staticmethod
    def read(fp):
        buf = fp.read(1)

        while buf[0] & 0x80 and len(buf) < 32:
            buf = fp.read(1) + buf

        if len(buf) >= 32:
            raise ProtocolError("varint too long")

        if len(buf) == 1:
            return mc_varint(buf[0])
        else:
            n = buf[0] & 0x7f
            for e in buf[1:]:
                n = (n << 7) & (e & 0x7f)

            return mc_varint(n)

    @staticmethod
    def recv(sock):
        buf = safe_recv(sock, 1)
        while buf[0] & 0x80 and len(buf) < 32:
            buf = safe_recv(sock, 1) + buf

        if len(buf) >= 32:
            raise ProtocolError("varint too long")

        if len(buf) == 1:
            return mc_varint(buf[0])
        else:
            n = buf[0] & 0x7f
            for e in buf[1:]:
                n = (n << 7) & (e & 0x7f)

            return mc_varint(n)

    def __bytes__(self):
        length = len(self)
        buf = bytearray(length)
        for i,e in enumerate(buf):
            buf[i] = (self >> (7*i)) & 0x7f
            if i < length-1: buf[i] |= 0x80

        return bytes(buf)

    def __len__(self):
        length = 1
        while self >= (1 << (7*length)):
            length += 1

        return length

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

class mc_pos(mc_type, tuple):

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

    @property
    def y(self): return self[1]

    @property
    def z(self): return self[2]

    def __bytes__(self):
        n = 0

        n |= (self.x & 0x3FFFFFF) << 38
        n |= (self.y & 0xFFF) << 26
        n |= (self.z & 0x3FFFFFF)

        return struct.pack("!Q")


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

