#!/usr/bin/env python3

from .types import \
    mc_comp, mc_field, mc_ubyte, \
    mc_ushort, mc_string, mc_bool, \
    mc_list_field

class Slot(mc_comp):

    count = mc_field("Count", mc_ubyte)
    slot = mc_field("Slot", mc_ubyte, optional=True)
    damage = mc_field("Damage", mc_ushort)
    id = mc_field("id", mc_string)
    add = mc_field("tag", mc_comp)
