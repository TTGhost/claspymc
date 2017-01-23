#!/usr/bin/env python3

import os
import os.path
from pathlib import Path
from math import ceil

from nbt import chunk, nbt, region, world

from .entity import Entity, PlayerEntity
from .types import \
    mc_comp, mc_int, mc_bool, \
    mc_string, mc_long, mc_double, \
    mc_ubyte, mc_list, mc_field, \
    mc_list_field, mc_split_pos_field, \
    mc_byte_array, mc_varint, mc_vec3f

class LevelData(mc_comp):

    version = mc_field("version", mc_int)
    name = mc_field("LevelName", mc_string)
    seed = mc_field("RandomSpeed", mc_long)
    features = mc_field("MapFeatures", mc_bool)
    last_played = mc_field("LastPlayed", mc_long)
    allow_commands = mc_field("allowCommands", mc_bool)
    gamemode = mc_field("GameType", mc_int)
    difficulty = mc_field("Difficulty", mc_ubyte)
    time = mc_field("Time", mc_long)
    day_time = mc_field("DayTime", mc_long)
    _spawn_x = mc_field("SpawnX", mc_int)
    _spawn_y = mc_field("SpawnY", mc_int)
    _spawn_z = mc_field("SpawnZ", mc_int)
    spawn_position = mc_split_pos_field(_spawn_x, _spawn_y, _spawn_z)
    raining = mc_field("raining", mc_bool)
    rain_time = mc_field("rainTime", mc_int)
    thundering = mc_field("thundering", mc_bool)
    thunder_time = mc_field("thunderTime", mc_int)
    clear_time = mc_field("clearWeatherTime", mc_int)

class LevelContainer(mc_comp):

    data = mc_field("Data", LevelData)

class Section(mc_comp):

    y_index = mc_field("Y", mc_ubyte)
    blocks = mc_field("Blocks", mc_byte_array)
    add = mc_field("Add", mc_byte_array, optional=True)
    data = mc_field("Data", mc_byte_array)
    block_light = mc_field("BlockLight", mc_byte_array)
    sky_light = mc_field("SkyLight", mc_byte_array)

    BITS_PER_BLOCK = 13
    INDICES_PER_SECTION = 4096
    TOTAL_BITS = INDICES_PER_SECTION * BITS_PER_BLOCK
    DATA_LENGTH = ceil(TOTAL_BITS / 8)

    def bytes(self):
        payload = b''
        payload += mc_ubyte(self.BITS_PER_BLOCK).bytes()
        payload += mc_varint(0).bytes()

        s_blocks = self.blocks
        s_add = None
        if hasattr(self, "nbt") and self.nbt.get("Add", None) is not None:
            s_add = self.add

        s_data = self.data
        data = bytearray(self.DATA_LENGTH)
        for i, offset in enumerate(range(0, self.TOTAL_BITS, self.BITS_PER_BLOCK)):
            data_idx = offset >> 3  # 8 bits per byte
            data_off = offset & 0x07
            add_idx = i >> 1  # 2 blocks per byte
            item = s_blocks[i]

            if i & 1:  # odd
                if s_add:
                    item |= (s_add[add_idx] >> 4) << 8
                item = (item << 4) | (s_data[add_idx] >> 4)

            else:  # even
                if s_add:
                    item |= (s_add[add_idx] & 0x0F) << 8
                item = (item << 4) | (s_data[add_idx] & 0x0F)

            item &= ((1 << self.BITS_PER_BLOCK) - 1)
            item <<= data_off
            while item != 0:
                data[data_idx] = item & 0xFF
                item >>= 8
                data_idx += 1

        payload += mc_varint(len(data)).bytes()
        payload += bytes(data)
        payload += self.block_light.bytes()
        payload += self.sky_light.bytes()
        return payload


class Chunk(mc_comp):

    x = mc_field("xPos", mc_int)
    z = mc_field("zPos", mc_int)
    last_update = mc_field("LastUpdate", mc_long)
    light_populated = mc_field("LightPopulated", mc_bool)
    terrain_populated = mc_field("TerrainPopulated", mc_bool)
    inhabited_time = mc_field("InhabitedTime", mc_long)
    biomes = mc_field("Biomes", mc_byte_array)
    sections = mc_list_field("Sections", Section)
    entities = mc_list_field("Entities", Entity)
    tile_entities = mc_list_field("TileEntities", mc_comp)
    tile_ticks = mc_list_field("TileTicks", mc_comp, optional=True)

class ChunkContainer(mc_comp):

    version = mc_field("DataVersion", mc_int)
    level = mc_field("Level", Chunk)

class MCWorld:

    def __init__(self, path):
        if not os.path.isdir(path):
            raise NotADirectoryError("MCWorld base path must exist and be a directory.")

        self.base = Path(path)
        if not self.base.is_dir():
            raise ValueError("MCWorld base path must exist and be a directory.")

        try:
            self.level_nbt = nbt.NBTFile(str(self.base / "level.dat"))
        except OSError:
            raise ValueError("MCWorld level.dat is not an NBT file.")

        self.level_container = LevelContainer.from_nbt(self.level_nbt)
        self.level = self.level_container.data
        self.regions = {}
        self.chunks = {}

    def get_region(self, x, z, dimension=0):
        if (dimension, x, z) in self.regions:
            return self.regions[(dimension, x, z)]

        path = self.base
        if dimension != 0:
            path /= "DIM{}".format(dimension)
        path /= "region"
        path /= "r.{}.{}.mca".format(x, z)

        file = region.RegionFile(path)
        self.regions[(dimension, x, z)] = file
        return file

    def get_chunk(self, x, z, dimension=0):
        if (dimension, x, z) in self.chunks:
            return self.chunks[(dimension, x, z)].level

        reg = self.get_region(x >> 5, z >> 5, dimension=dimension)
        root = reg.get_nbt(x & 0x1f, z & 0x1f)
        container = ChunkContainer.from_nbt(root)
        self.chunks[(dimension, x, z)] = container
        return container.level

    def get_player(self, uuid):
        path = self.base / "playerdata" / "{}.dat".format(uuid)
        try:
            file = nbt.NBTFile(str(path))
        except FileNotFoundError:
            return PlayerEntity()

        result = PlayerEntity.from_nbt(file)
        if result.position == mc_vec3f.get_default():
            result.position = mc_vec3f(self.level.spawn_position)
            result.spawn_position = mc_vec3f(self.level.spawn_position)

        return result

