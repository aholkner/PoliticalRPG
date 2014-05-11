import os
import logging
logging.getLogger('bacon').addHandler(logging.NullHandler())

import bacon
import tiled
from common import Rect, clamp

def open_res(path, mode = 'rb'):
    return open(bacon.get_resource_path(path), mode)

class Spritesheet(object):
    def __init__(self, path):
        lines = list(open_res(path, 'rt'))
        self.image_size = ts = int(lines[0].strip())
        self.image = bacon.Image(lines[1].strip(), sample_nearest = True)
        self.images = {}
        for y, line in enumerate(lines[2:]):
            line = line.strip()
            for x, name in enumerate(line.split(',')):
                self.images[name] = self.image.get_region(x * ts, y * ts, (x + 1) * ts, (y + 1) * ts)

class Sprite(object):
    def __init__(self, image, x, y):
        self.image = image
        self.x = x
        self.y = y
        
input_movement = {
    bacon.Keys.left: (-1, 0),
    bacon.Keys.right: (1, 0),
    bacon.Keys.up: (0, -1),
    bacon.Keys.down: (0, 1),
}

class World(object):
    def __init__(self, map):
        self.map = map
        self.scale = 4
        self.tile_size = map.tile_width
        self.sprites = []
        self.camera_x = self.camera_y = 0
        self.player_sprite = None

        for layer in self.map.layers[:]:
            if 'sprite' in layer.properties:
                self.map.layers.remove(layer)
                for i, image in enumerate(layer.images):
                    if image:
                        x = i % self.map.rows
                        y = i / self.map.rows
                        self.add_sprite(image, x, y)

    def add_sprite(self, image, x, y):
        sprite = Sprite(image, x, y)
        self.sprites.append(sprite)

        if hasattr(image, 'properties') and 'player' in image.properties:
            self.player_sprite = sprite

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
    def __init__(self, map):
        super(MapWorld, self).__init__(map)

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
        if key in input_movement:
            dx, dy = input_movement[key]
            self.move(dx, dy)

    def move(self, dx, dy):
        other = self.get_sprite_at(self.player_sprite.x + dx, self.player_sprite.y + dy)
        if other:
            self.on_collide(other)
        else:
            self.player_sprite.x += dx
            self.player_sprite.y += dy
        
    def on_collide(self, other):
        game.push_world(MapWorld(tiled.parse('res/combat.tmx')))

bacon.window.width = 512
bacon.window.height = 512

spritesheet = Spritesheet('res/spritesheet.txt')

class Game(bacon.Game):
    def __init__(self):
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