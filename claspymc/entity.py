#!/usr/bin/env python3

import uuid

from .item import Slot
from .types import \
    mc_vec3f, mc_float, mc_ubyte, \
    mc_sshort, mc_bool, mc_int, \
    mc_long, mc_double, mc_string, \
    mc_comp, mc_field, mc_list_field, \
    mc_uuid_field, mc_list_item_field, \
    mc_split_pos_field

__author__ = 'thomas'

def _running_id():
    i = 0
    while True:
        yield i
        i += 1

entity_id = _running_id()
particle_id = _running_id()

class Entity(mc_comp):

    id = mc_field("id", mc_string)
    position = mc_field("Pos", mc_vec3f)
    velocity = mc_field("Motion", mc_vec3f)
    _rotation = mc_list_field("Rotation", mc_float, length=2)
    yaw = mc_list_item_field(_rotation, 0)
    pitch = mc_list_item_field(_rotation, 1)
    fall_distance = mc_field("FallDistance", mc_float)
    fire = mc_field("Fire", mc_sshort)
    air = mc_field("Air", mc_sshort)
    on_ground = mc_field("OnGround", mc_bool)
    invulnerable = mc_field("Invulnerable", mc_bool)
    portal_cooldown = mc_field("PortalCooldown", mc_int)
    _uuid_most = mc_field("UUIDMost", mc_long)
    _uuid_least = mc_field("UUIDLeast", mc_long)
    uuid = mc_uuid_field(_uuid_most, _uuid_least)
    custom_name = mc_field("CustomName", mc_string, optional=True)
    custom_name_visible = mc_field("CustomNameVisible", mc_bool, optional=True)
    silent = mc_field("Silent", mc_bool)
    glowing = mc_field("Glowing", mc_bool)
    passengers = mc_list_field("Passengers", recursive=True)
    tags = mc_list_field("Tags", mc_string)

    def __init__(self):
        super().__init__()
        self.entity_id = next(entity_id)
        self.fire = mc_sshort(-20)
        self.air = mc_sshort(300)
        self.uuid = uuid.uuid4()

class MobAttributeModifier(mc_comp):

    name = mc_field("Name", mc_string)
    amount = mc_field("Amount", mc_double)
    operation = mc_field("Operation", mc_int)
    _uuid_most = mc_field("UUIDMost", mc_long)
    _uuid_least = mc_field("UUIDLeast", mc_long)
    uuid = mc_uuid_field(_uuid_most, _uuid_least)

class MobAttribute(mc_comp):

    name = mc_field("Name", mc_string)
    base_value = mc_field("Base", mc_double)
    modifiers = mc_list_field("Modifiers", MobAttributeModifier)

class MobEffect(mc_comp):

    id = mc_field("Id", mc_ubyte)
    amplifier = mc_field("Amplifier", mc_ubyte)
    duration = mc_field("Duration", mc_int)
    ambient = mc_field("Ambient", mc_bool)
    show_particles = mc_field("ShowParticles", mc_bool)

class Mob(Entity):

    health = mc_field("Health", mc_float)
    absorption = mc_field("AbsorptionAmount", mc_float)
    hurt_time = mc_field("HurtTime", mc_sshort)
    hurt_timestamp = mc_field("HurtByTimestamp", mc_int)
    death_time = mc_field("DeathTime", mc_sshort)
    is_fall_flying = mc_field("FallFlying", mc_bool)
    attributes = mc_list_field("Attributes", MobAttribute)
    active_effects = mc_list_field("ActiveEffects", MobEffect)

class PlayerAbilities(mc_comp):

    walk_speed = mc_field("walkSpeed", mc_float)
    fly_speed = mc_field("flySpeed", mc_float)
    can_fly = mc_field("mayfly", mc_bool)
    is_flying = mc_field("flying", mc_bool)
    invulnerable = mc_field("invulnerable", mc_bool)
    can_build = mc_field("mayBuild", mc_bool)
    instant_build = mc_field("instabuild", mc_bool)

    def __init__(self):
        super().__init__()
        self.walk_speed = mc_float(0.1)
        self.fly_speed = mc_float(0.05)
        self.can_build = mc_bool(True)

class PlayerEntity(Mob):

    version = mc_field("DataVersion", mc_int)
    dimension = mc_field("Dimension", mc_int)
    gamemode = mc_field("playerGameType", mc_int)
    score = mc_field("Score", mc_int)
    selected_slot = mc_field("SelectedItemSlot", mc_int)
    selected_item = mc_field("SelectedItem", Slot)
    _spawn_x = mc_field("SpawnX", mc_int, optional=True)
    _spawn_y = mc_field("SpawnY", mc_int, optional=True)
    _spawn_z = mc_field("SpawnZ", mc_int, optional=True)
    spawn_position = mc_split_pos_field(_spawn_x, _spawn_y, _spawn_z)
    spawn_forced = mc_field("SpawnForced", mc_bool)
    food_level = mc_field("foodLevel", mc_int)
    food_exhaustion = mc_field("foodExhaustionLevel", mc_float)
    food_saturation = mc_field("foodSaturationLevel", mc_float)
    food_tick_timer = mc_field("foodTickTimer", mc_int)
    xp_level = mc_field("XpLevel", mc_int)
    xp_percent = mc_field("XpP", mc_float)
    xp_total = mc_field("XpTotal", mc_int)
    inventory = mc_list_field("Inventory", Slot)
    ender_items = mc_list_field("EnderItems", Slot)
    abilities = mc_field("abilities", PlayerAbilities)



