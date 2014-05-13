from functools import partial
import os
import logging
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
    def __init__(self, image, x, y):
        self.image = image
        self.x = x
        self.y = y
       
class Slot(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.content = None

class MenuItem(object):
    def __init__(self, name, description, func=None):
        self.name = name
        self.description = description
        self.func = func

class Menu(object):
    def __init__(self, world):
        self.world = world
        self.items = []
        self.selected_index = 0
        self.x = self.y = 0
        self.can_dismiss = True

    def layout(self):
        self.width = 0
        self.height = len(self.items) * font_tiny.height
        for item in self.items:
            self.width = max(font_tiny.measure_string(item.name), self.width)

    @property
    def selected_item(self):
        return self.items[self.selected_index]

    def on_key_pressed(self, key):
        if key == bacon.Keys.up:
            self.selected_index = (self.selected_index - 1) % len(self.items)
        elif key == bacon.Keys.down:
            self.selected_index = (self.selected_index + 1) % len(self.items)
        elif key == bacon.Keys.left or key == bacon.Keys.escape:
            if self.can_dismiss:
                self.world.pop_menu()
        elif key == bacon.Keys.right or key == bacon.Keys.enter:
            self.selected_item.func()

    def draw(self):
        y = self.y
        bacon.push_color()
        for i, item in enumerate(self.items):
            y -= font_tiny.ascent
            if i == self.selected_index:
                bacon.set_color(1, 1, 0, 1)
            else:
                bacon.set_color(1, 1, 1, 1)
            bacon.draw_string(font_tiny, item.name, self.x, y)
            y += font_tiny.descent
        bacon.pop_color()

        self.draw_status(self.selected_item.description)

    def draw_status(self, msg):
        if self.world.menu_stack[-1] is self:
            debug.draw_string(msg, 0, ui_height)

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
            menu.y = self.menu_stack[-1].y
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

class Character(object):
    def __init__(self, id, level):
        self.id = id
        self.image = game_sprites[id]
        self.level = level
        self.ai = True
        row = random.choice(game_data.characters[id])
        self.votes = self.calc_stat(row.votes_base, row.votes_lvl)
        self.spin = self.calc_stat(row.spin_base, row.spin_lvl)
        self.speed = self.calc_stat(row.speed_base, row.speed_lvl)
        self.wit = self.calc_stat(row.wit_base, row.wit_lvl)
        self.cunning = self.calc_stat(row.cunning_base, row.cunning_lvl)
        self.charisma = self.calc_stat(row.charisma_base, row.charisma_lvl)
        self.flair = self.calc_stat(row.flair_base, row.flair_lvl)
        self.money = 0
        
    def calc_stat(self, base, exp):
        return int(base * pow(exp, self.level - 1))

class CombatMenuMain(Menu):
    def __init__(self, world):
        super(CombatMenuMain, self).__init__(world)
        self.items.append(MenuItem('Offense>', 'Launch a political attack', self.offense))
        self.items.append(MenuItem('Defense', 'Gather strength; -20% to incoming attacks', self.defense))
        self.items.append(MenuItem('Spin>', 'Run spin to get control of the situation', self.spin))
        self.items.append(MenuItem('Campaign>', 'Run a campaign to get an edge on your opponents', self.campaign))
        self.can_dismiss = False

    def offense(self):
        self.world.push_menu(CombatOffenseMenu(self.world))

    def defense(self):
        self.world.pop_menu()
        self.world.end_turn()

    def spin(self):
        self.world.pop_menu()
        self.world.end_turn()

    def campaign(self):
        self.world.pop_menu()
        self.world.end_turn()

class CombatOffenseMenu(Menu):
    def __init__(self, world):
        super(CombatOffenseMenu, self).__init__(world)
        for attack in game_data.attacks:
            self.items.append(MenuItem(attack.name, attack.description, partial(self.select, attack)))

    def select(self, attack):
        self.world.push_menu(CombatTargetMenu(self.world, partial(self.choose_target, attack)))

    def choose_target(self, attack, target):
        self.world.action_attack(attack, target)

class CombatTargetMenu(Menu):
    def __init__(self, world, func):
        super(CombatTargetMenu, self).__init__(world)
        self.func = func
        self.can_dismiss = True
        self.width = 0
        self.height = 0

        self.slots = [slot for slot in self.world.monster_slots if slot.content]

    @property
    def selected_slot(self):
        return self.slots[self.selected_index]

    def layout(self):
        pass

    def on_key_pressed(self, key):
        if key == bacon.Keys.left:
            self.selected_index = (self.selected_index - 1) % len(self.slots)
        elif key == bacon.Keys.right:
            self.selected_index = (self.selected_index + 1) % len(self.slots)
        elif key == bacon.Keys.up or key == bacon.Keys.escape:
            if self.can_dismiss:
                self.world.pop_menu()
        elif key == bacon.Keys.down or key == bacon.Keys.enter:
            self.func(self.selected_slot.content)

    def draw(self):
        debug.draw_string('>', self.selected_slot.x * self.world.tile_size * map_scale, self.selected_slot.y * self.world.tile_size * map_scale)
        self.draw_status('Choose target')

class CombatWorld(World):
    def __init__(self, map, encounter_id):
        super(CombatWorld, self).__init__(map)

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
        slot.content = character
        self.sprites.append(Sprite(character.image, slot.x, slot.y))
        self.characters.append(character)

    def begin_round(self):
        self.characters.sort(key=lambda c:c.speed, reverse=True)
        self.current_character_index = 0
        self.begin_turn()

    def begin_turn(self):
        if self.current_character_index >= len(self.characters):
            self.begin_round()
            return

        if self.current_character.ai:
            self.ai(self.current_character)
        else:
            self.push_menu(CombatMenuMain(self))

    def end_turn(self):
        self.current_character_index += 1
        self.begin_turn()

    def ai(self, character):
        self.after(0.5, self.end_turn)

    def action_attack(self, attack, target):
        debug.println('%s attacks %s with %s' % (self.current_character.id, target.id, attack.name))
        self.pop_all_menus()
        self.after(1, self.end_turn)

    def draw(self):
        super(CombatWorld, self).draw()

        i = -1
        for slot in self.slots:
            if slot.content:
                if slot.content is self.current_character:
                    x = slot.x * self.tile_size * map_scale
                    y = slot.y * self.tile_size * map_scale
                    debug.draw_string('^', x, y)

                i += 1
                if i == debug.show_slot_stats:
                    c = slot.content
                    x = slot.x * self.tile_size * map_scale
                    y = slot.y * self.tile_size * map_scale
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

class Debug(object):
    def __init__(self):
        self.font = font_tiny
        self.show_slot_stats = -1
        self.message = None
        self.message_timeout = 0

    def on_key_pressed(self, key):
        if key == bacon.Keys.k or key == bacon.Keys.j:
            self.show_slot_stats += 1 if key == bacon.Keys.k else -1
            self.println('show_slot_stats = %d' % self.show_slot_stats)

    def println(self, msg):
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

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('--import-ods')
    options, args = parser.parse_args()

    if options.import_ods:
        import odsimport
        combat_db = odsimport.import_ods(os.path.join(options.import_ods, 'Combat.ods'))
        game_data = GameData()
        game_data.attacks = parse_table(combat_db['Attacks'], dict(
            name = 'Attack Name',
            description = 'Description',
            stat = 'Underlying Stat',
            effects = 'Special Effects',
            base_damage_min = 'Base Damage',
            base_damage_max = 'Max Base Damage',
            crit_base_damage = 'Crit Base Damage',
            crit_chance_min = 'Chance To Crit Base (%)',
            crit_chance_max = 'Chance To Crit Max (%)',
        ))
        game_data.characters = parse_table(combat_db['Characters'], dict(
            id = 'ID',
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
        ), index_multi=True)
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
        ), index_unique=True)
        pickle.dump(game_data, open_res('res/game_data.bin', 'wb'))
    else:
        game_data = pickle.load(open_res('res/game_data.bin', 'rb'))

    game_sprites = load_sprites('res/sprites.tsx')

    game = Game()
    game.world = MapWorld(tiled.parse('res/map.tmx'))

    bacon.run(game)