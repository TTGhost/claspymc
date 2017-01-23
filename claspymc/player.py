#!/usr/bin/env python3

import os
import json
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

import numpy as np

from .net import IllegalData
from .util import data_filename, cache, UUID_NAMESPACE
from .types import Gamemode, Dimension, Difficulty
from .entity import PlayerEntity
from .packet import \
    ServerDifficulty, SpawnPosition, OutgoingPlayerAbilities, \
    OutgoingPlayerPositionLook, ChunkData

__author__ = 'Thomas Bell'

HAS_JOINED_URL = "https://sessionserver.mojang.com/session/minecraft/hasJoined?username={}&serverId={}"

class Player:

    def __init__(self, conn, username, resolve_uuid=False):
        self.connection = conn
        self.server = conn.server
        self.username = username
        self.config = conn.config
        self.uuid = None

        self._resolve_uuid()

        self.entity = self.server.world.get_player(self.uuid)
        self.entity.uuid = self.uuid

        self.locale = None
        self.permission_level = 0
        self.view_distance = 0
        self.chat_mode = 0
        self.chat_colours = False
        self.skin_parts = 0
        self.right_handed = False

        self.teleport_ids = []
        self.is_ready = False

    def spawn(self):
        ServerDifficulty(self.connection).send()
        SpawnPosition(self.connection).send()
        OutgoingPlayerAbilities(self.connection).send()
        OutgoingPlayerPositionLook(self.connection,
                                   self.entity.spawn_position,
                                   self.entity.yaw,
                                   self.entity.pitch).send()
        ChunkData(self.connection,
                  int(self.entity.position.x) >> 4,
                  int(self.entity.position.z) >> 4).send()

    def _resolve_uuid(self):
        user_name = quote(str(self.username))
        try:
            res = cache.fetch("https://api.mojang.com/users/profiles/minecraft/{}".format(user_name))
            self.uuid = uuid.UUID(json.loads(res)["id"])
        except Exception:
            self.uuid = uuid.uuid5(UUID_NAMESPACE, str(self.username))

    def verify(self, login_hash):
        user_name = quote(str(self.username))
        try:
            res = urlopen(HAS_JOINED_URL.format(user_name, login_hash))
            self.uuid = uuid.UUID(json.loads(res)["id"])

        except HTTPError as e:
            if e.code == 204:  # No Content
                raise IllegalData("User is not logged in!")

            else:
                raise

    def __bool__(self):
        return bool(self.connection)
