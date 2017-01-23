#!/usr/bin/env python3

import sys
import uuid
import struct
from io import BytesIO
from enum import IntEnum

from nbt import nbt

from .net import safe_recv, safe_send, ProtocolError

__author__ = 'Thomas Bell'

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

def nbt_to_bytes(tag):
    buf = BytesIO()
    tag._render_buffer(buf)
    buf.seek(0)
    return buf.read()

class States(IntEnum):
    HANDSHAKING = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3

class Dimension(IntEnum):
    NETHER = -1
    OVERWORLD = 0
    END = 1

class Difficulty(IntEnum):
    PEACEFUL = 0
    EASY = 1
    NORMAL = 2
    HARD = 3

class Gamemode(IntEnum):
    SURVIVAL = 0
    CREATIVE = 1
    ADVENTURE = 2
    SPECTATOR = 3
    HARDCORE = 0x08

class PlayerFlags(IntEnum):
    INVULNERABLE = 0x01
    FLYING = 0x02
    ALLOW_FLYING = 0x04
    CREATIVE_MODE = 0x08

class ChatMode(IntEnum):
    ENABLED = 0
    COMMANDS_ONLY = 1
    HIDDEN = 2

class DisplayedSkinParts(IntEnum):
    CAPE = 0x01
    JACKET = 0x02
    LEFT_SLEEVE = 0x04
    RIGHT_SLEEVE = 0x08
    LEFT_PANT_LEG = 0x10
    RIGHT_PANT_LEG = 0x20
    HAT = 0x40

class mc_nettype:

    format = None

    @classmethod
    def recv(cls, sock):
        if not cls.format:
            raise NotImplementedError("format undefined for mc_type subclass {}".format(cls.__name__))

        buf = safe_recv(sock, struct.calcsize(cls.format))

        (res,) = struct.unpack(cls.format, buf)

        return cls(res)

    @classmethod
    def read(cls, fp):
        if not cls.format:
            raise NotImplementedError("format undefined for mc_type subclass {}".format(cls.__name__))

        buf = fp.read(struct.calcsize(cls.format))

        (res,) = struct.unpack(cls.format, buf)

        return cls(res)

    def __bytes__(self):
        if not self.format:
            raise NotImplementedError("format undefined for mc_type subclass {}".format(type(self).__name__))

        try:
            return struct.pack(self.format, self)
        except struct.error:
            raise ProtocolError("invalid value for mc_type ({})".format(type(self).__name__))

    def bytes(self):
        return bytes(self)

    def send(self, sock):
        safe_send(sock, self.bytes())

class mc_nbttype:

    nbt_type = type(None)
    _default = None

    @classmethod
    def get_default(cls):
        if cls._default is not None:
            return cls(cls._default)
        else:
            return cls()

    @classmethod
    def from_nbt(cls, tag):
        if not isinstance(tag, cls.nbt_type):
            raise ValueError("invalid type for {}: {} instead of {}".format(
                cls.__name__, type(tag).__name__, cls.nbt_type.__name__))

        return cls(tag.value)

    def to_nbt(self):
        if self.nbt_type is type(None):
            raise NotImplementedError("to_nbt not implemented for mc_nbt subclass {}".format(type(self).__name__))

        return self.nbt_type(self)

class mc_varnum(mc_nettype, int):

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
        for i, e in enumerate(buf):
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

class mc_string(mc_nettype, mc_nbttype, str):

    nbt_type = nbt.TAG_String

    @classmethod
    def read(cls, fp):
        length = mc_varint.read(fp)

        try:
            s = fp.read(length).decode("utf8")
        except UnicodeDecodeError as e:
            print(e, file=sys.stderr)
            raise ProtocolError(e)

        return cls(s)

    @classmethod
    def recv(cls, sock):
        length = mc_varint.recv(sock)

        try:
            s = safe_recv(sock, length).decode("utf8")
        except UnicodeDecodeError as e:
            print(e, file=sys.stderr)
            raise ProtocolError(e)

        return cls(s)

    def bytes(self):
        res = self.encode("utf8")
        return bytes(mc_varint(len(res))) + res

class mc_bytes(mc_nettype, mc_nbttype, bytes):

    nbt_type = nbt.TAG_Byte_Array

    @classmethod
    def read(cls, fp):
        length = mc_varint.read(fp)
        array = fp.read(length)

        return cls(array)

    @classmethod
    def recv(cls, sock):
        length = mc_varint.recv(sock)
        array = safe_recv(sock, length)

        return cls(array)

    def bytes(self):
        return bytes(mc_varint(len(self))) + self

class mc_byte_array(mc_nbttype, bytes):

    nbt_type = nbt.TAG_Byte_Array

    def bytes(self):
        return self

class mc_pos(mc_nettype, list):

    @classmethod
    def read(cls, fp):
        n = mc_long.read(fp)

        x = unsigned_to_signed(n >> 38, 26)
        y = unsigned_to_signed(n >> 26, 12)
        z = unsigned_to_signed(n, 26)

        return cls((x, y, z))

    @classmethod
    def recv(cls, sock):
        n = mc_long.recv(sock)

        x = unsigned_to_signed(n >> 38, 26)
        y = unsigned_to_signed(n >> 26, 12)
        z = unsigned_to_signed(n, 26)

        return cls((x, y, z))

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

        return struct.pack("!Q", n)

class mc_vec3f(mc_nettype, mc_nbttype, list):

    nbt_type = nbt.TAG_List
    _default = (0.0, 0.0, 0.0)

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

    @classmethod
    def from_nbt(cls, tag_list):
        if not isinstance(tag_list, nbt.TAG_List) or \
                        tag_list.tagID != nbt.TAG_DOUBLE or \
                        len(tag_list) != 3:
            raise ValueError("mc_vec3f NBT representation must be a TAG_List of 3 TAG_Doubles")

        x = tag_list[0].value
        y = tag_list[1].value
        z = tag_list[2].value
        return cls((x, y, z))

    def to_nbt(self):
        result = nbt.TAG_List(nbt.TAG_Double)
        result.append(nbt.TAG_Double(self.x))
        result.append(nbt.TAG_Double(self.y))
        result.append(nbt.TAG_Double(self.z))
        return result

class mc_float(mc_nettype, mc_nbttype, float):
    format = "!f"
    nbt_type = nbt.TAG_Float

class mc_double(mc_nettype, mc_nbttype, float):  # heh
    format = "!d"
    nbt_type = nbt.TAG_Double

class mc_long(mc_nettype, mc_nbttype, int):
    format = "!q"
    nbt_type = nbt.TAG_Long

class mc_int(mc_nettype, mc_nbttype, int):
    format = "!i"
    nbt_type = nbt.TAG_Int

class mc_ushort(mc_nettype, mc_nbttype, int):
    format = "!H"
    nbt_type = nbt.TAG_Short

class mc_sshort(mc_nettype, mc_nbttype, int):
    format = "!h"
    nbt_type = nbt.TAG_Short

class mc_ubyte(mc_nettype, mc_nbttype, int):
    format = "!B"
    nbt_type = nbt.TAG_Byte

class mc_sbyte(mc_nettype, mc_nbttype, int):
    format = "!b"
    nbt_type = nbt.TAG_Byte

class mc_bool(mc_nettype, mc_nbttype, int):
    format = "!?"
    nbt_type = nbt.TAG_Byte

class mc_list(mc_nbttype, list):

    nbt_type = nbt.TAG_List
    _default = nbt.TAG_Compound

    def __init__(self, item_type):
        super().__init__()
        self.item_type = item_type

    @classmethod
    def from_nbt(cls, tag, sub_type=None):
        if not isinstance(tag, cls.nbt_type):
            raise ValueError("invalid type for {}: {} instead of {}".format(
                cls.__name__, type(tag).__name__, cls.nbt_type.__name__))

        if sub_type is not None and not issubclass(sub_type, mc_nbttype):
            raise ValueError("sub_type must be a subclass of mc_nbt")

        try:
            item_type = nbt.TAGLIST[tag.tagID]
        except KeyError:
            raise ValueError("invalid list value type for {}: {}".format(
                cls.__name__, tag.tagID))

        result = cls(item_type)
        for item in tag:
            if sub_type is not None:
                result.append(sub_type.from_nbt(item))
            else:
                result.append(item)

        return result

    def to_nbt(self):
        items = []
        for item in self:
            if isinstance(item, mc_nbttype):
                items.append(item.to_nbt())
            else:
                items.append(item)

        result = self.nbt_type(self.item_type)
        for item in items:
            result.append(item)

        return result

class mc_field:

    def __init__(self, nbt_key, container_cls, *, optional=False):
        if not issubclass(container_cls, mc_nbttype):
            raise ValueError("mc_field container_cls must be a subclass of mc_nbttype")

        self.key = nbt_key
        self.container = container_cls
        self.recursive = False
        self.optional = optional

    def get_new(self):
        return self.container.get_default()

    def __get__(self, instance, owner):
        if self.key in instance._values:
            return instance._values[self.key]
        else:
            return self.get_new()

    def __set__(self, instance, value):
        if not isinstance(value, self.container):
            value = self.container(value)
        instance._values[self.key] = value

    def from_nbt(self, tag):
        return self.container.from_nbt(tag)

    def from_nbt_recursive(self, tag, cls):
        return self.from_nbt(tag)

class mc_list_field(mc_field):

    def __init__(self, nbt_key, item_cls=None, *, recursive=False, length=None, optional=False):
        super().__init__(nbt_key, mc_list)
        if recursive:
            item_cls = mc_comp

        if not issubclass(item_cls, mc_nbttype):
            raise ValueError("mc_field item_cls must be a subclass of mc_nbttype")

        self.item_type = item_cls
        self.default = mc_list(item_cls)
        self.recursive = recursive
        self.length = length
        self.optional = optional

    def get_new(self):
        result = mc_list(self.item_type)
        if self.length is not None:
            for i in range(self.length):
                result.append(self.item_type.get_default())

        return result

    def from_nbt(self, tag):
        return self.container.from_nbt(tag, sub_type=self.item_type)

    def __set__(self, instance, value):
        if not isinstance(value, mc_list):
            result = mc_list(self.item_type)
            try:
                for item in value:
                    if not isinstance(item, self.item_type):
                        item = self.item_type(item)
                    result.append(item)
            except (TypeError, ValueError):
                pass

            instance._values[self.key] = result
        else:
            instance._values[self.key] = value

    def from_nbt_recursive(self, tag, cls):
        return self.container.from_nbt(tag, sub_type=cls)

class mc_uuid_field:  # pseudo field

    def __init__(self, most_field, least_field):
        self.most_field = most_field
        self.least_field = least_field

    def __get__(self, instance, owner):
        most = self.most_field.__get__(instance, owner)
        least = self.least_field.__get__(instance, owner)
        return uuid.UUID(int=((most << 64) | least))

    def __set__(self, instance, value):
        n = value.int
        most = (n >> 64)
        least = n & ((1 << 64) - 1)
        self.most_field.__set__(instance, most)
        self.least_field.__set__(instance, least)

class mc_list_item_field:  # pseudo field

    def __init__(self, list_field, index):
        self.list_field = list_field
        self.index = index

    def __get__(self, instance, owner):
        return self.list_field.__get__(instance, owner)[self.index]

    def __set__(self, instance, value):
        if not isinstance(value, self.list_field.item_type):
            value = self.list_field.item_type(value)

        array = self.list_field.__get__(instance, type(instance))
        array[self.index] = value
        self.list_field.__set__(instance, array)

class mc_split_pos_field:  # pseudo field

    def __init__(self, x, y, z):
        self.x_field = x
        self.y_field = y
        self.z_field = z

    def __get__(self, instance, owner):
        x = self.x_field.__get__(instance, owner)
        y = self.y_field.__get__(instance, owner)
        z = self.z_field.__get__(instance, owner)
        return mc_vec3f((x, y, z))

    def __set__(self, instance, value):
        if isinstance(value, mc_pos):
            value = mc_vec3f((value.x, value.y, value.z))

        if not isinstance(value, mc_vec3f):
            value = mc_vec3f(value)

        self.x_field.__set__(instance, value.x)
        self.y_field.__set__(instance, value.y)
        self.z_field.__set__(instance, value.z)

class mc_comp_meta(type):

    def __new__(cls, name, bases, namespace, **kwargs):
        result = type.__new__(cls, name, bases, namespace)
        result._fields = [v for v in namespace.values() if isinstance(v, mc_field)]

        return result

class mc_comp(mc_nbttype, metaclass=mc_comp_meta):

    nbt_type = nbt.TAG_Compound

    def __init__(self):
        self.nbt = None

        self._keys = {}
        self._values = {}
        for field in self._fields:
            self._keys[field.key] = field
            if not field.optional:
                self._values[field.key] = field.get_new()

    @classmethod
    def from_nbt(cls, tag):
        if not isinstance(tag, cls.nbt_type):
            raise ValueError("invalid type for {}: {} instead of {}".format(
                cls.__name__, type(tag).__name__, cls.nbt_type.__name__))

        result = cls()
        result.nbt = tag
        for nbt_key, field in result._keys.items():
            if nbt_key in tag:
                if field.recursive:
                    field.__set__(result, field.from_nbt_recursive(tag[nbt_key], cls))
                else:
                    field.__set__(result, field.from_nbt(tag[nbt_key]))

        return result

    def to_nbt(self):
        result = self.nbt if self.nbt is not None else self.nbt_type()
        for nbt_key, value in self._values.items():
            result[nbt_key] = value.to_nbt()

        return result

class mc_chunk_section(mc_nettype):

    def __init__(self, nbt_section):
        self.nbt = nbt_section

    def __bytes__(self):
        pass
