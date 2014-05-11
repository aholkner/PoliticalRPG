import os.path
import base64
import gzip
import struct
import xml.etree.cElementTree as ET
import zlib

import bacon
import tilemap

class Tileset(object):
    def __init__(self, firstgid, images):
        self.firstgid = firstgid
        self.images = images

def parse_tileset_images(elem, base_dir):
    spacing = int(elem.get('spacing') or 0)
    margin = int(elem.get('margin') or 0)
    tile_width = int(elem.get('tilewidth'))
    tile_height = int(elem.get('tileheight'))
    image = None
    for child in elem:
        if child.tag == 'image':
            filename = child.get('source')
            image = bacon.Image(os.path.join(base_dir, filename), sample_nearest=True)
    
    images = []
    for y in range(margin, image.height - margin, spacing + tile_height):
        for x in range(margin, image.width - margin, spacing + tile_width):
            images.append(image.get_region(x, y, x + tile_width, y + tile_height))

    return images

def parse_tile(image, elem):
    for child in elem:
        if child.tag == 'properties':
            for prop in child:
                if prop.tag == 'property':
                    name = prop.get('name')
                    value = prop.get('value')
                    if not hasattr(image, 'properties'):
                        image.properties = {}
                    image.properties[name] = value

def parse_tileset(elem, base_dir):
    firstgid = int(elem.get('firstgid'))
    source = elem.get('source')
    if source:
        tree = ET.parse(os.path.join(base_dir, source))
        elem = tree.getroot()
    
    images = parse_tileset_images(elem, base_dir)
    for child in elem:
        if child.tag == 'tile':
            id = int(child.get('id'))
            parse_tile(images[id], child)

    return Tileset(firstgid, images)

def parse_layer(tm, elem, tilesets):
    name = elem.get('name')
    cols = int(elem.get('width'))
    rows = int(elem.get('height'))
    layer = tilemap.TilemapLayer(name, cols, rows)
    tm.layers.append(layer)

    tx = 0
    ty = 0
    tiles = []
    def add_tile(gid):
        matching_tileset = None
        for tileset in tilesets:
            if gid < tileset.firstgid:
                break
            matching_tileset = tileset

        if matching_tileset:
            image = matching_tileset.images[gid - matching_tileset.firstgid]
            layer.images[ty * tm.cols + tx] = image

    for child in elem:
        if child.tag == 'properties':
            for property in child:
                if property.tag == 'property':
                    name = property.get('name')
                    value = property.get('value')
                    layer.properties[name] = value
                    if name == 'Y':
                        layer.offset_y = -tm.tile_height * int(value)
                        ty += int(value)
        elif child.tag == 'data':
            encoding = child.get('encoding')
            if encoding == 'base64':
                data = base64.b64decode(child.text)
                compression = child.get('compression')
                if compression == 'gzip':
                    data = gzip.decompress(data)
                elif compression == 'zlib':
                    data = zlib.decompress(data)
                for gid in struct.unpack('%dI' % (len(data) / 4), data):
                    add_tile(gid)
                    tx += 1
                    if tx >= cols:
                        tx = 0
                        ty += 1
            else:
                for tile in child:
                    if tile.tag == 'tile':
                        add_tile(int(tile.get('gid')))
                        tx += 1
                        if tx >= cols:
                            tx = 0
                            ty += 1

    if layer.name == 'Collision' or layer.name == 'Water':
        if layer.name == 'Collision':
            tm.layers.remove(layer)
        for i in range(len(layer.images)):
            if layer.images[i]:
                try:
                    collision_type = layer.images[i].properties['Collision']
                    if collision_type == 'All':
                        tm.tiles[i].walkable = False
                    elif collision_type == 'Animal':
                        tm.tiles[i].walkable_animal = False
                    elif collision_type == 'Villager':
                        tm.tiles[i].walkable_villager = False
                    elif collision_type == 'Entrance':
                        tm.tiles[i].walkable_entrance = False
                        tm.tiles[i].entrance_owner = layer.images[i].properties['Entrance']
                except KeyError:
                    pass
                except AttributeError:
                    pass

def parse_object_group(tm, elem):
    layer = tilemap.TilemapObjectLayer(elem.get('name'))
    tm.object_layers.append(layer)
    for object in elem:
        if object.tag == 'object':
            name = object.get('name')
            type = object.get('type')
            x = int(object.get('x'))
            y = int(object.get('y'))
            width = int(object.get('width', 0))
            height = int(object.get('height', 0))
            tilemap_object = tilemap.TilemapObject(name, type, x, y, width, height)
            layer.objects.append(tilemap_object)
            for child in object:
                if child.tag == 'properties':
                    for property in child:
                        if property.tag == 'property':
                            name = property.get('name')
                            value = property.get('value')
                            tilemap_object.properties[name] = value

def parse(tmx_file):
    tmx_file = bacon.get_resource_path(tmx_file)
    base_dir = os.path.dirname(tmx_file)

    tree = ET.parse(tmx_file)
    elem = tree.getroot()

    orientation = elem.get('orientation')
    cols = int(elem.get('width'))
    rows = int(elem.get('height'))
    tile_width = int(elem.get('tilewidth'))
    tile_height = int(elem.get('tileheight'))

    tm = tilemap.Tilemap(tile_width, tile_height, cols, rows)
    tm.tilesets = []
    layers = []
    object_layers = []

    for child in elem:
        if child.tag == 'tileset':
            tm.tilesets.append(parse_tileset(child, base_dir))
        elif child.tag == 'layer':
            parse_layer(tm, child, tm.tilesets)
        elif child.tag == 'objectgroup':
            parse_object_group(tm, child)
        
                    
    return tm
