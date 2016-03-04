#!/usr/bin/env python3

import os
import json
import uuid
import numpy as np
from nbt import nbt
from urllib.parse import quote

from util import *
from entity import PlayerEntity

__author__ = 'Thomas Bell'

NAMESPACE = uuid.UUID('a71dca7e-c0f6-4399-935f-a818651f6a36')

class Player:

    def __init__(self, conn, username):
        self.connection = conn
        self.username = username
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
            res = cache.get("https://api.mojang.com/users/profiles/minecraft/{}".format(user_name))
            self.uuid = json.loads(res)["id"].replace("-", "")
        except:
            self.uuid = str(uuid.uuid5(NAMESPACE, str(self.username)))



    def __bool__(self):
        return bool(self.connection)
