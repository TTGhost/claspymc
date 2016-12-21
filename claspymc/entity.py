#!/usr/bin/env python3

from .types import mc_slot, mc_vec3f

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
        self.entity_id = next(entity_id)
        self.flags = 0
        self.air = 10
        self.name = ""
        self.name_visible = False
        self.silent = False

class Fireball(Entity):
    pass

class Hanging(Entity):
    pass

class AreaEffectCloud(Entity):

    def __init__(self):
        super().__init__()
        self.radius = 0
        self.colour = 0
        self.point = False
        self.particle_id = next(particle_id)

class Arrow(Entity):

    def __init__(self):
        super().__init__()
        self.critical = False

class TippedArrow(Arrow):

    def __init__(self):
        super().__init__()
        self.colour = 0

class Boat(Entity):

    def __init__(self):
        super().__init__()
        self.last_hit_time = 0
        self.direction = 0
        self.damage = 0.0
        self.type = 0

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
        self.rotation = 0

class Item(Entity):

    def __init__(self):
        super().__init__()
        self.item = mc_slot()

class Living(Entity):

    def __init__(self):
        super().__init__()
        self.health = 0.0
        self.potion_colour = 0
        self.potion_ambient = False
        self.arrows = 0

class PlayerEntity(Entity):

    def __init__(self):
        super().__init__()
        self.additional_health = 0.0
        self.score = 0
        self.skin_flags = 0
        self.main_hand = 0

class ArmorStand(Entity):

    def __init__(self):
        super().__init__()
        self.status = 0
        self.head_rot = mc_vec3f((0, 0, 0))
        self.body_rot = mc_vec3f((0, 0, 0))
        self.left_arm_rot = mc_vec3f((0, 0, 0))
        self.right_arm_rot = mc_vec3f((0, 0, 0))
        self.left_leg_rot = mc_vec3f((0, 0, 0))
        self.right_leg_rot = mc_vec3f((0, 0, 0))

class Insentient(Entity):

    def __init__(self):
        super().__init__()
        self.status = 0

class Ambient(Insentient):
    pass

class Bat(Ambient):

    def __init__(self):
        super().__init__()
        self.hanging = 0

class Creature(Insentient):
    pass

class Ageable(Creature):

    def __init__(self):
        super().__init__()
        self.baby = False

class Animal(Ageable):
    pass


