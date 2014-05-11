import os
import logging
logging.getLogger('bacon').addHandler(logging.NullHandler())

import bacon
import tiled
from common import Rect, clamp

debug_font = bacon.Font(None, 12)

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

class Menu(object):
    def __init__(self, x, y):
        self.items = ['Attack', 'Mug', 'Magic', 'Items']
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
            bacon.draw_string(debug_font, item, self.x, y)
            y += 16
        bacon.pop_color()

class World(object):
    def __init__(self, map):
        self.map = map
        self.scale = 4
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
                        x = i % self.map.rows
                        y = i / self.map.rows
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

        # Viewport in scaled space
        viewport = Rect(self.camera_x, 
                        self.camera_y, 
                        self.camera_x + bacon.window.width / self.scale,
                        self.camera_y + bacon.window.height / self.scale)

        bacon.push_transform()
        bacon.scale(self.scale, self.scale)
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
        self.player_sprite = Sprite(game.player_image, player_slot.x, player_slot.y)
        self.sprites.append(self.player_sprite)

    def update(self):
        self.update_camera()
        
    def update_camera(self):
        ts = self.tile_size

        # Viewport in scaled space
        window_width = bacon.window.width / self.scale
        window_height = bacon.window.height / self.scale
        self.camera_x = self.player_sprite.x * ts - window_width / 2
        self.camera_y = self.player_sprite.y * ts - window_height / 2
        self.camera_x = clamp(self.camera_x, 0, self.map.tile_width * self.map.cols - window_width)
        self.camera_y = clamp(self.camera_y, 0, self.map.tile_height * self.map.rows - window_height)

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
        game.push_world(CombatWorld(tiled.parse('res/combat.tmx'), [other.image]))

class CombatWorld(World):
    def __init__(self, map, monsters):
        super(CombatWorld, self).__init__(map)
        self.menu = Menu(16, 256)

        player_slot = self.player_slots[0]
        self.player_sprite = Sprite(game.player_image, player_slot.x, player_slot.y)
        self.sprites.append(self.player_sprite)

        for i, monster in enumerate(monsters):
            monster_slot = self.monster_slots[i]
            self.sprites.append(Sprite(monster, monster_slot.x, monster_slot.y))

    def on_key_pressed(self, key):
        self.menu.on_key_pressed(key)

    def draw(self):
        super(CombatWorld, self).draw()
        self.menu.draw()


bacon.window.width = 512
bacon.window.height = 512

sprites = tiled.parse_tileset('res/sprites.tsx')

class Game(bacon.Game):
    def __init__(self):
        self.player_image = sprites.images[0]
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

    def on_key(self, key, pressed):
        if pressed:
            self.world.on_key_pressed(key)

game = Game()
game.world = MapWorld(tiled.parse('res/map.tmx'))

bacon.run(game)