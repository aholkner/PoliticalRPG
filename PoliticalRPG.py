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
        if key in input_movement:
            dx, dy = input_movement[key]
            self.move(dx, dy)

    def move(self, dx, dy):
        player.x += dx
        player.y += dy
        
    def update_camera(self):
        ts = self.tile_size

        # Viewport in scaled space
        window_width = bacon.window.width / self.scale
        window_height = bacon.window.height / self.scale
        self.camera_x = player.x * ts - window_width / 2
        self.camera_y = player.y * ts - window_height / 2
        self.camera_x = clamp(self.camera_x, 0, self.map.tile_width * self.map.cols - window_width)
        self.camera_y = clamp(self.camera_y, 0, self.map.tile_height * self.map.rows - window_height)

bacon.window.width = 256
bacon.window.height = 256

map = tiled.parse('res/map.tmx')
spritesheet = Spritesheet('res/spritesheet.txt')
player = Sprite(spritesheet.images['player'], 1, 1)
world = World(map)
world.sprites.append(player)

class Game(bacon.Game):
    def on_tick(self):
        bacon.clear(0, 0, 0, 1)
        world.update_camera()
        world.draw()

    def on_key(self, key, pressed):
        if pressed:
            world.on_key_pressed(key)

bacon.run(Game())