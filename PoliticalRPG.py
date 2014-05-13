from functools import partial
import os
import logging
import math
logging.getLogger('bacon').addHandler(logging.NullHandler())

import bacon
import tiled
import optparse
import random
import cPickle as pickle

from common import Rect, clamp

font_tiny = bacon.Font(bacon.get_resource_path('res/tinyfont.ttf'), 12)
font_tiny.height = font_tiny.descent - font_tiny.ascent

bacon.window.width = 640
bacon.window.height = 480

map_scale = 4
map_width = bacon.window.width / map_scale
map_height = bacon.window.height / map_scale

ui_width = bacon.window.width
ui_height = bacon.window.height

def map_to_ui(x, y):
    return (x * map_scale, y * map_scale)

def open_res(path, mode = 'rb'):
    return open(bacon.get_resource_path(path), mode)

class Sprite(object):
    effect_dead = False

    def __init__(self, image, x, y):
        self.image = image
        self.x = x
        self.y = y
       
class Slot(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.character = None
        self.sprite = None

class MenuItem(object):
    def __init__(self, name, description, func=None, enabled=True):
        self.name = name
        self.description = description
        self.func = func
        self.enabled = enabled

class Menu(object):
    def __init__(self, world):
        self.world = world
        self.items = []
        self.x = self.y = 0
        self.can_dismiss = True
        self.selected_index = 0

    def layout(self):
        self.width = 0
        self.height = len(self.items) * font_tiny.height
        for item in self.items:
            self.width = max(font_tiny.measure_string(item.name), self.width)

        self.selected_index = 0

    @property
    def selected_item(self):
        return self.items[self.selected_index]

    def on_key_pressed(self, key):
        if key == bacon.Keys.up:
            self.move_selection(-1)
        elif key == bacon.Keys.down:
            self.move_selection(1)
        elif key == bacon.Keys.left or key == bacon.Keys.escape:
            if self.can_dismiss:
                self.world.pop_menu()
        elif key == bacon.Keys.right or key == bacon.Keys.enter:
            if self.selected_item.enabled:
                self.selected_item.func()

    def move_selection(self, dir):
        start = max(0, self.selected_index)
        self.selected_index = (self.selected_index + dir) % len(self.items)

    def draw(self):
        y = self.y
        bacon.push_color()
        for i, item in enumerate(self.items):
            y -= font_tiny.ascent
            if not item.enabled:
                m = 0.7
            else:
                m = 1

            if i == self.selected_index:
                bacon.set_color(m, m, 0, 1)
            else:
                bacon.set_color(m, m, m, 1)
            bacon.draw_string(font_tiny, item.name, self.x, y)
            y += font_tiny.descent
        bacon.pop_color()

        self.draw_status(self.selected_item.description)

    def draw_status(self, msg):
        if self.world.menu_stack[-1] is self:
            bacon.set_color(0, 0, 0, 1)
            bacon.fill_rect(0, ui_height - debug.font.height * 2, ui_width, ui_height)
            bacon.set_color(1, 1, 1, 1)
            bacon.draw_string(debug.font, msg, 0, ui_height - debug.font.height * 2, ui_width, debug.font.height * 2, bacon.Alignment.left, bacon.VerticalAlignment.top) 

class World(object):
    def __init__(self, map):
        self.menu_stack = []
        self.menu_start_x = 0
        self.menu_start_y = ui_height - 16

        self.timeout_func = None
        self.timeout = 0

        self.map = map
        self.tile_size = map.tile_width
        self.sprites = []
        self.camera_x = self.camera_y = 0
        
        self.player_slots = [None] * 4
        self.monster_slots = [None] * 4

        for layer in self.map.layers[:]:
            if 'sprite' in layer.properties:
                self.map.layers.remove(layer)
                for i, image in enumerate(layer.images):
                    if image:
                        x = i % self.map.cols
                        y = i / self.map.cols
                        self.add_sprite(image, x, y)

    def add_sprite(self, image, x, y):
        if hasattr(image, 'properties'):
            if 'player_slot' in image.properties:
                self.player_slots[int(image.properties['player_slot']) - 1] = Slot(x, y)
                return
            elif 'monster_slot' in image.properties:
                self.monster_slots[int(image.properties['monster_slot']) - 1] = Slot(x, y)
                return

        sprite = Sprite(image, x, y)
        self.sprites.append(sprite)

    def get_sprite_at(self, x, y):
        for sprite in self.sprites:
            if sprite.x == x and sprite.y == y:
                return sprite
        return None

    def push_menu(self, menu):
        menu.layout()
        if self.menu_stack:
            menu.x = self.menu_stack[-1].x + self.menu_stack[-1].width
        else:
            menu.x = self.menu_start_x
        menu.y = self.menu_start_y - menu.height
        self.menu_stack.append(menu)

    def pop_menu(self):
        self.menu_stack.pop()

    def pop_all_menus(self):
        del self.menu_stack[:]

    def after(self, timeout, func):
        assert self.timeout_func is None
        self.timeout = timeout
        self.timeout_func = func

    def update(self):
        if self.timeout_func:
            self.timeout -= bacon.timestep
            if self.timeout <= 0:
                f = self.timeout_func
                self.timeout_func = None
                f()

    def draw(self):

        ts = self.tile_size

        viewport = Rect(self.camera_x, 
                        self.camera_y, 
                        self.camera_x + map_width,
                        self.camera_y + map_height)

        bacon.push_transform()
        bacon.scale(map_scale, map_scale)
        bacon.translate(-viewport.x1, -viewport.y1)
        
        self.map.draw(viewport)
        for sprite in self.sprites:
            if sprite.effect_dead:
                bacon.push_transform()
                bacon.translate(sprite.x * ts + 4, sprite.y * ts + 4)
                bacon.rotate(-math.pi / 2)
                bacon.draw_image(sprite.image, -4, -4)
                bacon.pop_transform()
            else:
                bacon.draw_image(sprite.image, sprite.x * ts, sprite.y * ts)

        bacon.pop_transform()

        for menu in self.menu_stack:
            menu.draw()

    def on_key_pressed(self, key):
        if self.timeout_func:
            return

        if self.menu_stack:
            self.menu_stack[-1].on_key_pressed(key)

class MapWorld(World):
     
    input_movement = {
        bacon.Keys.left: (-1, 0),
        bacon.Keys.right: (1, 0),
        bacon.Keys.up: (0, -1),
        bacon.Keys.down: (0, 1),
    }

    def __init__(self, map):
        super(MapWorld, self).__init__(map)

        player_slot = self.player_slots[0]
        self.player_sprite = Sprite(game.player.image, player_slot.x, player_slot.y)
        self.sprites.append(self.player_sprite)

    def update(self):
        self.update_camera()
        
    def update_camera(self):
        ts = self.tile_size

        self.camera_x = self.player_sprite.x * ts - map_width / 2
        self.camera_y = self.player_sprite.y * ts - map_height / 2
        self.camera_x = clamp(self.camera_x, 0, self.map.tile_width * self.map.cols - map_width)
        self.camera_y = clamp(self.camera_y, 0, self.map.tile_height * self.map.rows - map_height)

    def on_key_pressed(self, key):
        super(MapWorld, self).on_key_pressed(key)
        if not self.menu_stack:
            if key in self.input_movement:
                dx, dy = self.input_movement[key]
                self.move(dx, dy)

    def move(self, dx, dy):
        other = self.get_sprite_at(self.player_sprite.x + dx, self.player_sprite.y + dy)
        if other:
            self.on_collide(other)
        else:
            self.player_sprite.x += dx
            self.player_sprite.y += dy
        
    def on_collide(self, other):
        encounter_id = other.image.properties['encounter']
        game.push_world(CombatWorld(tiled.parse('res/combat.tmx'), encounter_id))

class Effect(object):
    id = None
    apply_to_source = False
    function = None
    rounds_min = None
    rounds_max = None
    attribute = None
    value = None

    def _add_value(self, character, value):
        if self.attribute == 'spin':
            character.spin = clamp(character.spin + value, 0, character.max_spin)
        elif self.attribute == 'votes':
            character.votes = clamp(character.votes + value, 0, character.max_votes)
        elif self.attribute == 'wit':
            character.wit = max(0, character.wit + value)
        elif self.attribute == 'cunning':
            character.cunning = max(0, character.cunning + value)
        elif self.attribute == 'charisma':
            character.charisma = max(0, character.charisma + value)
        elif self.attribute == 'flair':
            character.flair = max(0, character.flair + value)
        elif self.attribute == 'resistance':
            character.resistance = max(0, character.resistance + value)
        elif self.attribute == 'money':
            character.resistance = max(0, character.money + value)

    def apply(self, character):
        if self.function == 'reduce':
            self._add_value(character, -self.value)
        elif self.function == 'add':
            self._add_value(character, self.value)
        elif self.function == 'revive':
            character.votes = int(character.max_votes * self.value)
            game.world.set_dead(character, False)
            game.world.add_floater(character, 'Revived!')

    def unapply(self, character):
        if self.function == 'reduce':
            self._add_value(character, self.value)
        elif self.function == 'add':
            self._add_value(character, -self.value)

    def update(self, character):
        if self.function == 'drain':
            self._add_value(character, -self.value)

class ActiveEffect(object):
    def __init__(self, effect, rounds):
        self.effect = effect
        self.rounds = rounds

class ItemAttack(object):
    def __init__(self, attack, quantity=1):
        self.attack = attack
        self.quantity = quantity
       
class Character(object):
    def __init__(self, id, level, ai=True):
        self.id = id
        self.image = game_sprites[id]
        self.level = level
        self.ai = ai
        self.dead = False
        self.data = row = random.choice(game_data.characters[id])
        self.votes = self.max_votes = self.calc_stat(row.votes_base, row.votes_lvl)
        self.spin = self.max_spin = self.calc_stat(row.spin_base, row.spin_lvl)
        self.speed = self.calc_stat(row.speed_base, row.speed_lvl)
        self.wit = self.calc_stat(row.wit_base, row.wit_lvl)
        self.cunning = self.calc_stat(row.cunning_base, row.cunning_lvl)
        self.charisma = self.calc_stat(row.charisma_base, row.charisma_lvl)
        self.flair = self.calc_stat(row.flair_base, row.flair_lvl)
        self.money = 0
        self.resistance = 0
        self.active_effects = []
        self.item_attacks = []
        for attack in row.item_attacks:
            self.add_item_attack(attack)

        if ai:
            self.spin_attacks = row.spin_attacks
        else:
            self.spin_attacks = list(row.spin_attacks)

    def add_item_attack(self, attack):
        for ia in self.item_attacks:
            if ia.attack is attack:
                ia.quantity += 1
                return
        self.item_attacks.append(ItemAttack(attack, 1))

    def remove_item_attack(self, attack):
        for ia in self.item_attacks:
            if ia.attack is attack:
                ia.quantity -= 1
                if ia.quantity == 0:
                    self.item_attacks.remove(ia)
                return

    def calc_stat(self, base, exp):
        return int(base * pow(exp, self.level - 1))
    
    def add_active_effect(self, active_effect):
        for ae in self.active_effects:
            if ae.effect.id == active_effect.effect.id:
                return

        self.active_effects.append(active_effect)
        active_effect.effect.apply(self)
        debug.println('Add effect %s to %s' % (active_effect.effect.id, self.id))
        
        if active_effect.rounds == 0:
            self.remove_active_effect(active_effect)

    def remove_active_effect(self, active_effect):
        if active_effect.rounds != 0:
            active_effect.effect.unapply(self) # unapply is not given to 0-round effects, these are treated as permanent
        self.active_effects.remove(active_effect)
        debug.println('Remove effect %s from %s' % (active_effect.effect.id, self.id))

    def update_active_effects(self):
        for ae in self.active_effects[:]:
            ae.rounds -= 1
            debug.println('Update effect %s on %s' % (ae.effect.id, self.id))
            ae.effect.update(self)
            if ae.rounds <= 0:
                self.remove_active_effect(ae)

    def remove_all_active_effects(self):
        for ae in self.active_effects[:]:
            self.remove_active_effect(ae)

    def has_effect_function(self, function):
        for ae in self.active_effects:
            if ae.effect.function == function:
                return True
        return False
    
    def get_effects_abbrv(self):
        return ' '.join(ae.effect.abbrv for ae in self.active_effects)

class CombatMenuMain(Menu):
    def __init__(self, world):
        super(CombatMenuMain, self).__init__(world)
        character = self.world.current_character

        self.items.append(MenuItem('Offense>', 'Launch a political attack', self.on_offense))
        self.items.append(MenuItem('Defense', game_data.attacks['DEFENSE'].description, self.on_defense))
        self.items.append(MenuItem('Spin>', 'Run spin to get control of the situation', self.on_spin, enabled=bool(character.spin_attacks)))
        self.items.append(MenuItem('Items>', 'Use an item from your briefcase', self.on_items, enabled=bool(character.item_attacks)))
        self.can_dismiss = False

    def on_offense(self):
        self.world.push_menu(CombatOffenseMenu(self.world, self.world.current_character.data.standard_attacks))

    def on_defense(self):
        self.world.action_attack(game_data.attacks['DEFENSE'], [])

    def on_spin(self):
        self.world.push_menu(CombatOffenseMenu(self.world, self.world.current_character.spin_attacks))

    def on_items(self):
        self.world.push_menu(CombatOffenseMenu(self.world, self.world.current_character.item_attacks))

class CombatOffenseMenu(Menu):
    def __init__(self, world, attacks):
        super(CombatOffenseMenu, self).__init__(world)
        for attack in attacks:
            if isinstance(attack, ItemAttack):
                quantity = attack.quantity
                attack = attack.attack
            else:
                quantity = 1

            if quantity > 1:
                name = '%s (x%d)' % (attack.name, quantity)
            else:
                name = attack.name

            enabled = world.current_character.spin >= attack.spin_cost
            if attack.target_type == 'DeadFriendly' and not [slot for slot in self.world.player_slots if slot.character and slot.character.dead]:
                enabled = False

            self.items.append(MenuItem(name, attack.description, partial(self.select, attack), enabled=enabled))

    def select(self, attack):
        if attack.target_type == 'None':
            self.world.action_attack(attack, [])
        else:
            self.world.push_menu(CombatTargetMenu(self.world, attack.target_type, attack.target_count, partial(self.choose_target, attack)))

    def choose_target(self, attack, targets):
        self.world.action_attack(attack, targets)
        
class CombatTargetMenu(Menu):
    def __init__(self, world, target_type, target_count, func):
        super(CombatTargetMenu, self).__init__(world)
        self.target_type = target_type
        self.target_count = target_count
        self.func = func
        self.can_dismiss = True
        self.width = 0
        self.height = 0

        if target_type == 'AllEnemy':
            self.slots = [slot for slot in self.world.monster_slots if slot.character and not slot.character.dead]
        elif target_type == 'AllFriendly':
            self.slots = [slot for slot in self.world.player_slots if slot.character and not slot.character.dead]
        elif target_type == 'DeadFriendly':
            self.slots = [slot for slot in self.world.player_slots if slot.character and slot.character.dead]
        elif target_type == 'All':
            self.slots = [slot for slot in self.world.slots if slot.character and not slot.character.dead]
        else:
            assert False

        self.slots.sort(key=lambda slot: slot.x)
        self.target_count = min(self.target_count, len(self.slots))

    @property
    def selected_slots(self):
        return self.slots[self.selected_index:self.selected_index+self.target_count]

    def layout(self):
        pass

    def on_key_pressed(self, key):
        if key == bacon.Keys.left:
            self.selected_index = (self.selected_index - 1) % (len(self.slots) - self.target_count + 1)
        elif key == bacon.Keys.right:
            self.selected_index = (self.selected_index + 1) % (len(self.slots) - self.target_count + 1)
        elif key == bacon.Keys.escape:
            if self.can_dismiss:
                self.world.pop_menu()
        elif key == bacon.Keys.enter:
            self.func([slot.character for slot in self.selected_slots])

    def draw(self):
        for i in range(self.target_count):
            slot = self.slots[self.selected_index + i]
            debug.draw_string('>', slot.x * self.world.tile_size * map_scale, slot.y * self.world.tile_size * map_scale + 16)
        self.draw_status('Choose target')
        
class Floater(object):
    def __init__(self, text, x, y):
        self.text = text
        self.x = x
        self.y = y
        self.timeout = 1.0

class CombatWorld(World):
    def __init__(self, map, encounter_id):
        super(CombatWorld, self).__init__(map)

        self.menu_start_y = ui_height - 100

        self.floaters = []
        self.active_attack = None
        self.active_targets = None

        self.characters = []
        self.fill_slot(self.player_slots[0], game.player)
        
        encounter = game_data.encounters[encounter_id]
        if encounter.monster1:
            self.fill_slot(self.monster_slots[0], Character(encounter.monster1, encounter.monster1_lvl))
        if encounter.monster2:
            self.fill_slot(self.monster_slots[1], Character(encounter.monster2, encounter.monster2_lvl))
        if encounter.monster3:
            self.fill_slot(self.monster_slots[2], Character(encounter.monster3, encounter.monster3_lvl))
        if encounter.monster4:
            self.fill_slot(self.monster_slots[3], Character(encounter.monster4, encounter.monster4_lvl))

        self.slots = self.player_slots + self.monster_slots
        self.begin_round()

    @property
    def current_character(self):
        return self.characters[self.current_character_index]

    def fill_slot(self, slot, character):
        slot.character = character
        slot.sprite = Sprite(character.image, slot.x, slot.y)
        self.sprites.append(slot.sprite)
        self.characters.append(character)

    def get_slot(self, character):
        for slot in self.slots:
            if slot.character is character:
                return slot
        return None

    def begin_round(self):
        self.characters.sort(key=lambda c:c.speed, reverse=True)
        self.current_character_index = 0
        while self.current_character_index < len(self.characters) and self.current_character.dead:
                self.current_character_index += 1
        self.begin_turn()

    def begin_turn(self):
        if self.current_character_index >= len(self.characters):
            self.begin_round()
            return

        # Check if character misses turn after effects
        miss_turn = self.current_character.has_effect_function('miss_turn')

        # Update character effects
        self.current_character.update_active_effects()

        # Miss turn, do AI or show UI
        if miss_turn:
            debug.println('%s misses turn' % self.current_character.id)
            self.after(2, self.end_turn)
        elif self.current_character.ai:
            self.after(0.5, self.ai)
        else:
            self.push_menu(CombatMenuMain(self))

    def end_turn(self):
        # End attack
        self.active_attack = None
        self.active_targets = None

        # Check end condition
        win = True
        lose = True
        for character in self.characters:
            if not character.dead:
                if character.ai:
                    win = False
                else:
                    lose = False
        
        if win:
            self.win()
        elif lose:
            self.lose()
        else:
            # Next character's turn
            self.current_character_index += 1
            while self.current_character_index < len(self.characters) and self.current_character.dead:
                self.current_character_index += 1
            self.begin_turn()

    def win(self):
        for character in self.characters:
            character.remove_all_active_effects()
        game.pop_world()

    def lose(self):
        for character in self.characters:
            character.remove_all_active_effects()
        game.pop_world() # TODO

    def ai(self):
        source = self.current_character

        # Look for a character to revive
        # TODO

        # List of all possible attacks
        attacks = list(source.data.standard_attacks)

        # Add spin attacks we can afford
        attacks += [a for a in source.spin_attacks if a.spin_cost <= source.spin]

        # Add item attacks (TODO only if applicable)
        attacks += [ia.attack for ia in source.item_attacks if ia.attack.spin_cost <= source.spin]

        # Random choice of attack
        attack = random.choice(attacks)

        # Find applicable targets
        target_type = attack.target_type
        if target_type == 'AllEnemy':
            slots = [slot for slot in self.player_slots if slot.character and not slot.character.dead]
        elif target_type == 'AllFriendly':
            slots = [slot for slot in self.monster_slots if slot.character and not slot.character.dead]
        elif target_type == 'DeadFriendly':
            slots = [slot for slot in self.monster_slots if slot.character and slot.character.dead]
        elif target_type == 'All':
            slots = [slot for slot in self.slots if slot.character and not slot.character.dead]
        elif target_type == 'None':
            slots = [self.get_slot(source)]
        else:
            assert False, 'Unsupported target type'

        # Choose target(s)
        slots.sort(key=lambda slot: slot.x)
        target_count = min(attack.target_count, len(slots))
        max_slot_index = len(slots) - target_count + 1
        slot_index = random.randrange(0, max_slot_index)
        targets = [slot.character for slot in slots[slot_index:slot_index + target_count]]

        self.action_attack(attack, targets)

    def action_attack(self, attack, targets):
        self.pop_all_menus()

        self.active_attack = attack
        self.active_targets = targets
        self.after(1, self.action_attack_step2)

    def action_attack_step2(self):
        source = self.current_character
        attack = self.active_attack
        targets = self.active_targets
        
        if not attack.underlying_stat:
            base_stat = 0
        elif attack.underlying_stat == 'Cunning':
            base_stat = max(source.cunning, 0)
        elif attack.underlying_stat == 'Wit':
            base_stat = max(source.wit, 0)
        elif attack.underlying_stat == 'Money':
            assert False # TODO
        else:
            assert False
        
        # Consume spin
        if attack.spin_cost:
            debug.println('%s consumed %d spin, has %d remaining' % (source.id, attack.spin_cost, source.spin))
            source.spin = max(0, source.spin - attack.spin_cost)

        # Consume item
        if (not attack in source.spin_attacks) and (not attack in source.data.standard_attacks):
            debug.println('%s consumed item %s' % (source.id, attack.name))
            source.remove_item_attack(attack)

        # Apply effects to source
        critical_fail_effect = None
        for effect in attack.effects:
            if effect.id == 'Critical Fail':
                critical_fail_effect = effect
            else:
                rounds = random.randrange(effect.rounds_min, effect.rounds_max + 1)
                if effect.apply_to_source:
                    source.add_active_effect(ActiveEffect(effect, rounds))

        # Attack targets
        critical_fail = True
        for target in targets:
            # Immunity
            if attack in target.data.immunities:
                self.add_floater(target, 'Immune')
                debug.println('%s is immune to %s' % (target.id, attack.name))
                continue

            # Crit
            modifiers = 0
            if attack.crit_chance_max:
                crit_chance = random.randrange(attack.crit_chance_min, attack.crit_chance_max + 1)
                crit_success = random.randrange(0, 100) <= crit_chance
            else:
                crit_success = False

            # Damage
            if crit_success:
                damage = base_stat * (attack.crit_base_damage + modifiers)
            else:
                damage = base_stat * (random.randrange(attack.base_damage_min, attack.base_damage_max + 1) + modifiers)
        
            # Cheat damage
            if debug.massive_damage and not source.ai:
                damage *= 100

            tried_damage = True
            if damage > 0:
                # Charisma
                damage = max(0, damage - target.charisma)

                # Resistance and weakness
                if attack in target.data.resistance:
                    self.add_floater(target, 'Resist', 1)
                    debug.println('%s is resistant to %s' % (target.id, attack.name))
                    damage -= damage * 0.3
                elif attack in target.data.weaknesses:
                    self.add_floater(target, 'Weak', 1)
                    debug.println('%s is weak to %s' % (target.id, attack.name))
                    damage += damage * 0.3

                # Global resistance (defense)
                if target.resistance:
                    self.add_floater(target, 'Defends', 1)
                    debug.println('%s defends' % target.id)
                damage -= damage * min(1, target.resistance)
                
            if not tried_damage or damage == 0:
                critical_fail = False

            # Apply damage
            damage = int(damage)
            self.apply_damage(target, damage)

            if damage == 0:
                self.add_floater(target, '0')

            # Apply target effects
            for effect in attack.effects:
                rounds = random.randrange(effect.rounds_min, effect.rounds_max + 1)
                if not effect.apply_to_source:
                    target.add_active_effect(ActiveEffect(effect, rounds))

            # Award spin for damage dealt unless this was a spin action
            if not source.ai and not attack.spin_cost:
                self.award_spin(source, max(0, damage))

            debug.println('%s attacks %s with %s for %d' % (source.id, target.id, attack.name, damage))

        # Critical fail effect
        if critical_fail and critical_fail_effect:
            rounds = random.randrange(effect.rounds_min, critical_fail_effect.rounds_max + 1)
            if effect.apply_to_source:
                source.add_active_effect(ActiveEffect(critical_fail_effect, rounds))
                self.add_floater(source, 'Critical fail')

        self.after(2, self.end_turn)

    def apply_damage(self, target, damage):
        target.votes -= damage
        target.votes = clamp(target.votes, 0, target.max_votes)

        if damage > 0:
            self.add_floater(target, '%d' % damage)
        elif damage < 0:
            self.add_floater(target, '+%d' % -damage)

        if target.votes == 0:
            target.votes = 0
            self.set_dead(target, True)
            
    def set_dead(self, character, dead):
        character.dead = dead
        self.get_slot(character).sprite.effect_dead = dead

    def award_spin(self, target, damage):
        target.spin += 1 # TODO AMANDA
        target.spin = min(target.spin, target.max_spin)
        
    def add_floater(self, character, text, offset=0):
        slot = self.get_slot(character)
        self.floaters.append(Floater(text, slot.x * self.tile_size * map_scale, (slot.y - offset) * self.tile_size * map_scale))

    def draw(self):
        super(CombatWorld, self).draw()

        if self.active_attack:
            bacon.draw_string(debug.font, self.active_attack.name, ui_width / 2, 40, None, None, bacon.Alignment.center)

        for floater in self.floaters[:]:
            floater.timeout -= bacon.timestep
            if floater.timeout < 0.5:
                floater.y -= bacon.timestep * 80
            if floater.timeout < 0:
                self.floaters.remove(floater)
            else:
                debug.draw_string(floater.text, floater.x, int(floater.y))

        for i, slot in enumerate(self.player_slots):
            character = slot.character
            x = i * ui_width / 4
            y = ui_height - 80
            if character:
                if character is self.current_character:
                    bacon.push_color()
                    bacon.set_color(0.7, 0.7, 0.7, 1)
                    bacon.fill_rect(x, y + debug.font.ascent, x + ui_width / 4, y + debug.font.height * 3)
                    bacon.pop_color()

                dy = debug.font.height
                debug.draw_string(character.data.name, x, y)
                debug.draw_string('Votes: %d/%d' % (character.votes, character.max_votes), x, y + dy)
                debug.draw_string('Spin:  %d/%d' % (character.spin, character.max_spin), x, y + dy * 2)
                debug.draw_string(character.get_effects_abbrv(), x, y + dy * 3) 

        i = -1
        for slot in self.slots:
            if slot.character:
                if slot.character is self.current_character:
                    x = slot.x * self.tile_size * map_scale
                    y = slot.y * self.tile_size * map_scale
                    debug.draw_string('^', x, y)

                i += 1
                if i == debug.show_slot_stats:
                    c = slot.character
                    x = slot.x * self.tile_size * map_scale
                    y = slot.y * self.tile_size * map_scale + 8 * map_scale
                    dy = debug.font.height
                    debug.draw_string(c.id, x, y)
                    debug.draw_string('level=%d' % c.level, x, y + dy)
                    debug.draw_string('votes=%d' % c.votes, x, y + dy * 2)
                    debug.draw_string('spin=%d' % c.spin, x, y + dy * 3)
                    debug.draw_string('speed=%d' % c.speed, x, y + dy * 4)
                    debug.draw_string('wit=%d' % c.wit, x, y + dy * 5)
                    debug.draw_string('cunning=%d' % c.cunning, x, y + dy * 6)
                    debug.draw_string('charisma=%d' % c.charisma, x, y + dy * 7)
                    debug.draw_string('flair=%d' % c.flair, x, y + dy * 8)
                    y += dy * 8
                    for e in c.active_effects:
                        y += dy 
                        debug.draw_string('+%s for %d rounds' % (e.effect.id, e.rounds), x, y)

class Debug(object):
    def __init__(self):
        self.font = font_tiny
        self.show_slot_stats = -1
        self.massive_damage = False
        self.message = None
        self.message_timeout = 0

    def on_key_pressed(self, key):
        if key == bacon.Keys.k or key == bacon.Keys.j:
            self.show_slot_stats += 1 if key == bacon.Keys.k else -1
            self.println('show_slot_stats = %d' % self.show_slot_stats)
        elif key == bacon.Keys.f1:
            self.massive_damage = not self.massive_damage
            self.println('massive_damage = %s' % self.massive_damage)
        elif key == bacon.Keys.numpad_add:
            if isinstance(game.world, CombatWorld):
                game.world.apply_damage(game.world.current_character, -10)
        elif key == bacon.Keys.numpad_sub:
            if isinstance(game.world, CombatWorld):
                game.world.apply_damage(game.world.current_character, 10)

    def println(self, msg):
        print msg
        self.message = msg
        self.message_timeout = 1.0

    def draw(self):
        self.message_timeout -= bacon.timestep
        if self.message and self.message_timeout > 0:
            self.draw_string(self.message, 0, ui_height)

    def draw_string(self, text, x, y):
        bacon.push_color()
        w = self.font.measure_string(text)
        bacon.set_color(0, 0, 0, 1)
        bacon.fill_rect(x, y + self.font.ascent, x + w, y + self.font.descent)
        bacon.set_color(1, 1, 1, 1)
        bacon.draw_string(self.font, text, x, y)
        bacon.pop_color()
        
debug = Debug()


def load_sprites(path):
    sprites = tiled.parse_tileset(path)
    sprite_images = {}
    for image in sprites.images:
        if not hasattr(image, 'properties'):
            continue
        if 'character' in image.properties:
            sprite_images[image.properties['character']] = image
    return sprite_images

class Game(bacon.Game):
    def __init__(self):
        self.player = Character('Player', 1)
        self.player.ai = False
        self.world = None
        self.world_stack = []

    def push_world(self, world):
        self.world_stack.append(self.world)
        self.world = world

    def pop_world(self):
        self.world = self.world_stack.pop()

    def on_tick(self):
        bacon.clear(0, 0, 0, 1)
        self.world.update()
        self.world.draw()

        debug.draw()

    def on_key(self, key, pressed):
        if pressed:
            self.world.on_key_pressed(key)
            debug.on_key_pressed(key)

class TableRow(object):
    pass

def parse_table(table, columns, cls=TableRow, index_unique=False, index_multi=False):
    headers = table[0]
    column_map = []
    column_count = 0
    for name, header in columns.items():
        index = headers.index(header)
        if index != -1:
            column_map.append((index, name))
            column_count = max(column_count, index + 1)
        else:
            logging.warn('Unmapped column "%s"' % header)

    if index_unique or index_multi:
        obj_table = {}
    else:
        obj_table = []

    for row in table[1:]:
        if len(row) < column_count:
            row.extend([''] * (column_count - len(row)))

        if row[0] == '':
            continue

        obj_row = cls()
        for i, name in column_map:
            setattr(obj_row, name, row[i])

        if index_multi:
            key = row[0]
            if key not in obj_table:
                obj_table[key] = []
            obj_table[key].append(obj_row)
        elif index_unique:
            key = row[0]
            obj_table[key] = obj_row
        else:
            obj_table.append(obj_row)

    return obj_table

class GameData(object):
    pass

def convert_idlist_to_objlist(value, index):
    result = []
    for id in value.split(','):
        id = id.strip()
        if id:
            result.append(index[id])
    return result

def main():
    parser = optparse.OptionParser()
    parser.add_option('--import-ods')
    options, args = parser.parse_args()

    global game_data
    if options.import_ods:
        import odsimport
        combat_db = odsimport.import_ods(os.path.join(options.import_ods, 'Combat.ods'))
        game_data = GameData()
        
        game_data.effects = parse_table(combat_db['Effects'], dict(
            id = 'ID',
            abbrv = 'Abbrev',
            apply_to_source = 'Apply To Source',
            function = 'Function',
            rounds_min = 'Number Rounds Base',
            rounds_max = 'Number Rounds Max',
            attribute = 'Attribute Effected',
            value = 'Value',
        ), index_unique=True, cls=Effect)

        game_data.attacks = parse_table(combat_db['Attacks'], dict(
            id = 'ID',
            name = 'Attack Name',
            description = 'Description',
            spin_cost = 'Spin Cost',
            target_type = 'Target Type',
            target_count = 'Target Count',
            underlying_stat = 'Underlying Stat',
            effects = 'Special Effects',
            base_damage_min = 'Base Damage',
            base_damage_max = 'Max Base Damage',
            crit_base_damage = 'Crit Base Damage',
            crit_chance_min = 'Chance To Crit Base (%)',
            crit_chance_max = 'Chance To Crit Max (%)',
        ), index_unique=True)

        for attack in game_data.attacks.values():
            attack.target_count = int(attack.target_count)
            attack.effects = convert_idlist_to_objlist(attack.effects, game_data.effects)
            attack.spin_cost = attack.spin_cost if attack.spin_cost else 0

        game_data.standard_attacks = parse_table(combat_db['StandardAttacks'], dict(
            group = 'AttackGroup',
            attack = 'Attack',
        ), index_multi=True)

        for attacks in game_data.standard_attacks.values():
            for i, row in enumerate(attacks):
                attacks[i] = game_data.attacks[row.attack]

        game_data.characters = parse_table(combat_db['Characters'], dict(
            id = 'ID',
            name = 'Name',
            votes_base = 'Votes',
            votes_lvl = 'Votes Lvl',
            spin_base = 'SP',
            spin_lvl = 'SP Lvl',
            speed_base = 'Spd',
            speed_lvl = 'Spd Lvl',
            wit_base = 'Wit',
            wit_lvl = 'Wit Lvl',
            cunning_base = 'Cun',
            cunning_lvl = 'Cun Lvl',
            charisma_base = 'Cha',
            charisma_lvl = 'Cha Lvl',
            flair_base = 'Flr',
            flair_lvl = 'Flr Lvl',
            attack_group = 'AttackGroup',
            immunities = 'Immunities',
            resistance = 'Resistance',
            weaknesses = 'Weaknesses',
            item_attacks = 'Items',
        ), index_multi=True)

        # Parse characters
        for characters in game_data.characters.values():
            for character in characters:
                character.immunities = convert_idlist_to_objlist(character.immunities, game_data.attacks)
                character.resistance = convert_idlist_to_objlist(character.resistance, game_data.attacks)
                character.weaknesses = convert_idlist_to_objlist(character.weaknesses, game_data.attacks)
                attacks = game_data.standard_attacks[character.attack_group]
                character.spin_attacks = [attack for attack in attacks if attack.spin_cost]
                character.standard_attacks = [attack for attack in attacks if not attack.spin_cost]
                character.item_attacks = convert_idlist_to_objlist(character.item_attacks, game_data.attacks)

        game_data.encounters = parse_table(combat_db['Encounters'], dict(
            id = 'ID',
            monster1 = 'Monster 1',
            monster1_lvl = 'Monster 1 Lvl',
            monster2 = 'Monster 2',
            monster2_lvl = 'Monster 2 Lvl',
            monster3 = 'Monster 3',
            monster3_lvl = 'Monster 3 Lvl',
            monster4 = 'Monster 4',
            monster4_lvl = 'Monster 4 Lvl',
            xp = 'XP',
            drops = 'Drops'
        ), index_unique=True)
        pickle.dump(game_data, open_res('res/game_data.bin', 'wb'))
    else:
        game_data = pickle.load(open_res('res/game_data.bin', 'rb'))

    global game_sprites
    game_sprites = load_sprites('res/sprites.tsx')

    global game
    game = Game()
    game.world = MapWorld(tiled.parse('res/map.tmx'))

    bacon.run(game)

if __name__ == '__main__':
    import traceback
    try:
        main()
    except:
        traceback.print_exc()