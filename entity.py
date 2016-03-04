#!/usr/bin/env python3

from util import *

__author__ = 'thomas'

def _running_id():
    i = 0
    while True:
        yield i
        i += 1

entity_id = _running_id()
particle_id = _running_id()

class Entity:

    def __init__(self):
        self.entity_id = mc_int(next(entity_id))
        self.flags = mc_ubyte(0)
        self.air = mc_varint(10)
        self.name = mc_string("")
        self.name_visible = False
        self.silent = False

class Fireball(Entity):
    pass

class Hanging(Entity):
    pass

class AreaEffectCloud(Entity):

    def __init__(self):
        super().__init__()
        self.radius = mc_float(0)
        self.colour = mc_varint(0)
        self.point = False
        self.particle_id = mc_varint(next(particle_id))

class Arrow(Entity):

    def __init__(self):
        super().__init__()
        self.critical = False

class TippedArrow(Arrow):

    def __init__(self):
        super().__init__()
        self.colour = mc_varint(0)

class Boat(Entity):

    def __init__(self):
        super().__init__()
        self.last_hit_time = mc_varint(0)
        self.direction = mc_varint(0)
        self.damage = mc_float(0)
        self.type = mc_varint(0)

class EnderCrystal(Entity):

    def __init__(self):
        super().__init__()
        self.beam_target = None
        self.show_bottom = False

class WitherSkull(Fireball):

    def __init__(self):
        super().__init__()
        self.invulnerable = False

class Fireworks(Entity):

    def __init__(self):
        super().__init__()
        self.firework_info = mc_slot()

class ItemFrame(Hanging):

    def __init__(self):
        super().__init__()
        self.item = mc_slot()
        self.rotation = mc_varint(0)

class Item(Entity):

    def __init__(self):
        super().__init__()
        self.item = mc_slot()

class Living(Entity):

    def __init__(self):
        super().__init__()
        self.health = mc_float(0)
        self.potion_colour = mc_varint(0)
        self.potion_ambient = False
        self.arrows = mc_varint(0)

class PlayerEntity(Entity):

    def __init__(self):
        super().__init__()
        self.additional_health = mc_float(0)
        self.score = mc_varint(0)
        self.skin_flags = mc_ubyte(0)
        self.main_hand = mc_ubyte(0)

class ArmorStand(Entity):

    def __init__(self):
        super().__init__()
        self.status = mc_ubyte(0)
        self.head_rot = mc_vec3f((0, 0, 0))
        self.body_rot = mc_vec3f((0, 0, 0))
        self.left_arm_rot = mc_vec3f((0, 0, 0))
        self.right_arm_rot = mc_vec3f((0, 0, 0))
        self.left_leg_rot = mc_vec3f((0, 0, 0))
        self.right_leg_rot = mc_vec3f((0, 0, 0))

class Insentient(Entity):

    def __init__(self):
        super().__init__()
        self.status = mc_ubyte(0)

class Ambient(Insentient):
    pass

class Bat(Ambient):

    def __init__(self):
        super().__init__()
        self.hanging = mc_ubyte(0)

class Creature(Insentient):
    pass

class Ageable(Creature):

    def __init__(self):
        super().__init__()
        self.baby = False

class Animal(Ageable):
    pass


