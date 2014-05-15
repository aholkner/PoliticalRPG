from math import floor
import bisect
import heapq

import bacon
from common import Rect

class Tile(object):
    path_cost = 1
    path_parent = None

    walkable_animal = True
    walkable_villager = True
    walkable_entrance = True
    entrance_owner = None
    _walkable = True

    def __init__(self, tx, ty, rect, walkable=True, accept_items=True):
        self.tx = tx
        self.ty = ty
        self.rect = rect
        if not walkable:
            self._walkable = walkable
        self.accept_items = accept_items
        self.can_target = True
        self.items = []

    def __lt__(self, other):
        return (self.tx, self.ty) < (other.tx, other.ty)

    def is_walkable(self):
        return self._walkable and all(item.walkable for item in self.items)
    def set_walkable(self, walkable):
        self._walkable = walkable
    walkable = property(is_walkable, set_walkable)

    def add_item(self, item):
        self.items.append(item)
        item.x = self.rect.center_x
        item.y = self.rect.center_y

    def remove_item(self, item):
        try:
            self.items.remove(item)
        except ValueError:
            pass

class TilemapObject(object):
    def __init__(self, name, type, x, y, width=0, height=0):
        self.name = name
        self.type = type
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.image = None
        self.properties = {}

class TilemapObjectLayer(object):
    def __init__(self, name):
        self.name = name
        self.objects = []

class TilemapLayer(object):
    def __init__(self, name, cols, rows):
        self.name = name
        self.images = [None] * (cols * rows)
        self.properties = {}
        self.offset_y = 0

class TilemapScanline(object):
    def __init__(self):
        self.sprites = []

class Tilemap(object):
    def __init__(self, tile_width, tile_height, cols, rows):
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.cols = cols
        self.rows = rows
        self.layers = []
        self.object_layers = []
        self.scanlines = [TilemapScanline() for row in range(rows)]
        self.sprite_layer_index = 6

        self.tiles = []
        y = 0
        for row in range(rows):
            x = 0
            for col in range(cols):
                self.tiles.append(Tile(col, row, Rect(x, y, x + tile_width, y + tile_height)))
                x += tile_width
            y += tile_height

        # default tile
        self.tiles.append(Tile(-1, -1, Rect(0, 0, 0, 0), walkable=False, accept_items=False))
        self.tiles[-1].can_target = False

    def add_sprite(self, sprite):
        scan = int(floor(sprite.y / self.tile_height))
        sprite._scanline = scan
        bisect.insort(self.scanlines[scan].sprites, sprite)

    def remove_sprite(self, sprite):
        try:
            oldscan = sprite._scanline
            self.scanlines[oldscan].sprites.remove(sprite)
        except:
            pass

    def update_sprite_position(self, sprite):
        oldscan = sprite._scanline
        scan = int(floor(sprite.y / self.tile_height))
        if scan != oldscan:
            self.scanlines[oldscan].sprites.remove(sprite)
            bisect.insort(self.scanlines[scan].sprites, sprite)
            sprite._scanline = scan

    def get_tile_index(self, x, y):
        tx = floor(x / self.tile_width)
        ty = floor(y / self.tile_height)
        if (tx < 0 or tx >= self.cols or
            ty < 0 or ty >= self.rows):
            return len(self.tiles) - 1
        return int(ty * self.cols + tx)

    def get_tile_at(self, x, y):
        return self.tiles[self.get_tile_index(x, y)]

    def get_tile_rect(self, x, y):
        tx = floor(x / self.tile_width)
        ty = floor(y / self.tile_height)
        x = tx * self.tile_width
        y = ty * self.tile_height
        return Rect(x, y, x + self.tile_width, y + self.tile_height)

    def get_bounds(self):
        return Rect(0, 0, self.cols * self.tile_width, self.rows * self.tile_height)

    def draw(self, rect):
        tx1 = max(0, int(floor(rect.x1 / self.tile_width)))
        ty1 = max(0, int(floor(rect.y1 / self.tile_height)))
        tx2 = min(self.cols, int(floor(rect.x2 / self.tile_width)) + 1)
        ty2 = min(self.rows, int(floor(rect.y2 / self.tile_height)) + 5)
        sprite_layer_index = self.sprite_layer_index
        for ty in range(ty1, ty2):
            ti = ty * self.cols + tx1

            # Draw ground tiles
            for tx in range(tx1, tx2):
                tile = self.tiles[ti]
                r = tile.rect
                for layer in self.layers[:sprite_layer_index]:
                    image = layer.images[ti]
                    if image:
                        bacon.draw_image(image, r.x1, r.y1, r.x2, r.y2)
                ti += 1

            # Draw sorted scanline sprites
            scanline = self.scanlines[ty]
            for sprite in scanline.sprites:
                sprite_rect = sprite.rect
                if sprite_rect.x2 >= rect.x1 and sprite_rect.x1 <= rect.x2:
                    sprite.draw()

            # Overlay tiles
            ti = ty * self.cols + tx1
            for tx in range(tx1, tx2):
                tile = self.tiles[ti]
                r = tile.rect
                for layer in self.layers[sprite_layer_index:]:
                    image = layer.images[ti]
                    if image:
                        bacon.draw_image(image, r.x1, r.y1 + layer.offset_y, r.x2, r.y2 + layer.offset_y)
                ti += 1

    def get_path(self, start_tile, arrived_func, heuristic_func, max_size):
        # http://stackoverflow.com/questions/4159331/python-speed-up-an-a-star-pathfinding-algorithm
        
        def retrace(c):
            path = [c]
            while c.path_parent is not None:
                c = c.path_parent
                path.append(c)
            path.reverse()
            return path
        
        def candidates(tile):
            tx = tile.tx
            ty = tile.ty
            i = ty * self.cols + tx
            left = right = up = down = None
            if tx > 0:
                left = self.tiles[i - 1]
                yield left
            if tx < self.cols - 1:
                right = self.tiles[i + 1]
                yield right
            if ty > 0:
                up = self.tiles[i - self.cols]
                yield up
            if ty < self.rows - 1:
                down = self.tiles[i + self.cols]
                yield down
            if left and left.walkable:
                if up and up.walkable:
                    yield self.tiles[i - self.cols - 1]
                if down and down.walkable:
                    yield self.tiles[i + self.cols - 1]
            if right and right.walkable:
                if up and up.walkable:
                    yield self.tiles[i - self.cols + 1]
                if down and down.walkable:
                    yield self.tiles[i + self.cols + 1]

        closed = set()
        open_set = set()
        open = []
        open.append((0, start_tile))
        start_tile.path_parent = None
        while open and max_size >= 0:
            max_size -= 1
            score, current = heapq.heappop(open)
            if arrived_func(current):
                return retrace(current)
            
            closed.add(current)
            for tile in candidates(current):
                if tile not in closed and tile not in open_set:
                    g = heuristic_func(tile)
                    open_set.add(tile)
                    heapq.heappush(open, (score + g + 1, tile))
                    tile.path_parent = current
        return []
