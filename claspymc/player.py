#!/usr/bin/env python3

import os
import json
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from nbt import nbt
import numpy as np

from .net import IllegalData
from .util import data_filename, cache
from .types import Gamemode, Dimension, Difficulty
from .entity import PlayerEntity
from .packet import \
    ServerDifficulty, SpawnPosition, OutgoingPlayerAbilities, \
    OutgoingPlayerPositionLook

__author__ = 'Thomas Bell'

NAMESPACE = uuid.UUID('a71dca7e-c0f6-4399-935f-a818651f6a36')
HAS_JOINED_URL = "https://sessionserver.mojang.com/session/minecraft/hasJoined?username={}&serverId={}"

class Player:

    def __init__(self, conn, username, resolve_uuid=False):
        self.connection = conn
        self.server = conn.server
        self.username = username
        self.config = conn.config
        self.uuid = None

        if not self.config.get("online", False) and resolve_uuid:
            self._resolve_uuid()

        self.nbt = nbt.NBTFile()
        self.entity = PlayerEntity()
        self.filename = data_filename(self.connection.server, "{}.dat".format(self.uuid))
        if os.path.isfile(self.filename):
            self.nbt.parse_file(self.filename)

        self.gamemode = Gamemode.SURVIVAL
        self.dimension = Dimension.OVERWORLD
        self.difficulty = self.config.get("difficulty", Difficulty.EASY)

        self.on_ground = False
        self.position = np.array([0, 63, 0])
        self.spawn_position = np.array([0, 63, 0])
        self.yaw = 0.0
        self.pitch = 0.0

        self.locale = None
        self.permission_level = 0
        self.abilities = 0
        self.view_distance = 0
        self.chat_mode = 0
        self.chat_colours = False
        self.skin_parts = 0
        self.right_handed = False
        self.flying_speed = 0.05
        self.fov_modifier = 0.10

        self.teleport_ids = []
        self.is_ready = False

    def spawn(self):
        ServerDifficulty(self.connection).send()
        SpawnPosition(self.connection).send()
        OutgoingPlayerAbilities(self.connection).send()
        OutgoingPlayerPositionLook(self.connection,
                                   self.spawn_position,
                                   self.yaw,
                                   self.pitch).send()

    def _resolve_uuid(self):
        user_name = quote(str(self.username))
        try:
            res = cache.fetch("https://api.mojang.com/users/profiles/minecraft/{}".format(user_name))
            self.uuid = uuid.UUID(json.loads(res)["id"])
        except Exception:
            self.uuid = uuid.uuid5(NAMESPACE, str(self.username))

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
