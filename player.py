#!/usr/bin/env python3

import os
import json
import uuid
import numpy as np
from nbt import nbt
from urllib.request import urlopen
from urllib.parse import quote
from urllib.error import URLError, HTTPError

from util import *
from entity import PlayerEntity

__author__ = 'Thomas Bell'

NAMESPACE = uuid.UUID('a71dca7e-c0f6-4399-935f-a818651f6a36')
HAS_JOINED_URL = "https://sessionserver.mojang.com/session/minecraft/hasJoined?username={}&serverId={}"

class Player:

    def __init__(self, conn, username):
        self.connection = conn
        self.username = username
        self.config = conn.config
        self.uuid = None

        if not self.config.get("online", False):
            self._resolve_uuid()

        self.nbt = nbt.NBTFile()
        self.entity = PlayerEntity()
        self.filename = data_filename(self.connection.server, "{}.dat".format(self.uuid))
        if os.path.isfile(self.filename):
            self.nbt.parse_file(self.filename)

        self.gamemode = mc_ubyte(0)
        self.dimension = mc_sbyte(0)
        self.difficulty = mc_ubyte(0)

        self.on_ground = False
        self.position = np.array([0, 0, 0])
        self.yaw = mc_float(0)

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
            print("doing a thing...")
            res = urlopen(HAS_JOINED_URL.format(user_name, login_hash))
            print("response: {}".format(res))
            self.uuid = uuid.UUID(json.loads(res)["id"])

        except HTTPError as e:
            if e.code == 204:  # No Content
                raise IllegalData("User is not logged in!")

            else:
                print(e)
                raise

    def __bool__(self):
        return bool(self.connection)
