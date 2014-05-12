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

bacon.window.width = 512
bacon.window.height = 448

map_scale = 4
map_width = bacon.window.width / map_scale
map_height = bacon.window.height / map_scale

ui_scale = 2
ui_width = bacon.window.width / ui_scale
ui_height = bacon.window.height / ui_scale

def map_to_ui(x, y):
    return (x / ui_scale * map_scale, y / ui_scale * map_scale)

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

class Menu(object):
    def __init__(self, x, y):
        self.items = [attack.name for attack in game_data.attacks]
        self.selected_index = 0
        self.x = x
        self.y = y

    def on_key_pressed(self, key):
        if key == bacon.Keys.up:
            self.selected_index = (self.selected_index - 1) % len(self.items)
        elif key == bacon.Keys.down:
            self.selected_index = (self.selected_index + 1) % len(self.items)

    def draw(self):
        y = self.y
        bacon.push_color()
        for i, item in enumerate(self.items):
            if i == self.selected_index:
                bacon.set_color(1, 1, 0, 1)
            else:
                bacon.set_color(1, 1, 1, 1)
            bacon.draw_string(font_tiny, item, self.x, y)
            y += font_tiny.descent - font_tiny.ascent
        bacon.pop_color()

class World(object):
    def __init__(self, map):
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

    def update(self):
        pass

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

    def on_key_pressed(self, key):
        pass

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
        row = random.choice(game_data.characters[id])
        self.votes = self.calc_stat(row.votes_base, row.votes_lvl)
        self.spin = self.calc_stat(row.spin_base, row.spin_lvl)
        self.speed = self.calc_stat(row.speed_base, row.speed_lvl)
        self.wit = self.calc_stat(row.wit_base, row.wit_lvl)
        self.cunning = self.calc_stat(row.cunning_base, row.cunning_lvl)
        self.charisma = self.calc_stat(row.charisma_base, row.charisma_lvl)
        self.flair = self.calc_stat(row.flair_base, row.flair_lvl)
        
    def calc_stat(self, base, exp):
        return int(base * pow(exp, self.level - 1))

class CombatWorld(World):
    def __init__(self, map, encounter_id):
        super(CombatWorld, self).__init__(map)
        self.menu = Menu(2, 128)

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

    def fill_slot(self, slot, character):
        slot.content = character
        self.sprites.append(Sprite(character.image, slot.x, slot.y))

    def on_key_pressed(self, key):
        self.menu.on_key_pressed(key)

    def draw(self):
        super(CombatWorld, self).draw()
        self.menu.draw()

        i = -1
        for slot in self.slots:
            if slot.content:
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
            self.draw_string(self.message, 0, bacon.window.height - self.font.height)

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