import logging
logging.basicConfig()

from functools import partial
import os
import logging
import math
from math import ceil

import appdirs
import bacon
import tiled
import optparse
import random
import cPickle as pickle

from common import Rect, clamp

font_tiny = bacon.Font(bacon.get_resource_path('res/tinyfont.ttf'), 12)
font_tiny.height = font_tiny.descent - font_tiny.ascent

tiled.Tileset.get_cached_image(bacon.get_resource_path('res/combat-tiles.png'))
end_image = tiled.Tileset.get_cached_image(bacon.get_resource_path('res/end.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/props.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/sprites.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/tiles_act1.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/tiles_act2.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/tiles_act2p2.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/tiles_act3.png'))
tiled.Tileset.get_cached_image(bacon.get_resource_path('res/tiles_basement.png'))
title_image = tiled.Tileset.get_cached_image(bacon.get_resource_path('res/title.png'))
ui_image = tiled.Tileset.get_cached_image(bacon.get_resource_path('res/ui.png'))

bacon.window.width = 640
bacon.window.height = 480
bacon.window.title = 'Goodnight, Mr President'

map_scale = 4
map_width = bacon.window.width / map_scale
map_height = bacon.window.height / map_scale

ui_scale = 4

ui_width = bacon.window.width
ui_height = bacon.window.height

def weighted_choice(seq, weight_key):
    total = sum(weight_key(c) for c in seq)
    r = random.uniform(0, total)
    upto = 0
    for c in seq:
        w = weight_key(c)
        if upto + w > r:
            return c
        upto += w
    return seq[-1]

def map_to_ui(x, y):
    return (x * map_scale, y * map_scale)

def open_res(path, mode='rb'):
    return open(bacon.get_resource_path(path), mode)

class Sprite(object):
    name = '??'
    effect_dead = False
    script_index = 0
    properties = {}

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

class UI(object):
    def __init__(self):
        self.ts = 4
        self.font = font_tiny
        self.image = ui_image
        self.stat_border = self.get_border_tiles(0)
        self.stat_border_disabled = self.get_border_tiles(3)
        self.stat_border_active = self.get_border_tiles(6)
        self.speech_border = self.get_border_tiles(9)
        self.white_border = self.get_border_tiles(48)
        self.menu_border = self.get_border_tiles(51)
        self.speech_point = self.get_tile_2x(6)
        self.menu_up_image = self.get_tile_2x(19)
        self.menu_down_image = self.get_tile_2x(20)
        self.combat_selected_arrow = self.get_tile_2x(7)
        self.combat_target_arrow = self.get_tile_2x(14)
        self.floater_border_red = self.get_border_tiles(96)
        self.floater_border_green = self.get_border_tiles(99)
        self.floater_border_grey = self.get_border_tiles(102)
        self.attack_border = self.get_border_tiles(105)
        self.info_border = self.get_border_tiles(108)
        self.info_arrow = self.get_tile_2x(15)
        self.health_background_image = self.get_tile(58)
        self.health_image = self.get_tile(59)

    def get_border_tiles(self, index):
        return [self.get_tile(index + i) for i in [0, 1, 2, 16, 17, 18, 32, 33, 34]]

    def get_tile(self, i):
        ts = self.ts
        x = i % 16
        y = i / 16
        return self.image.get_region(x * ts, y * ts, (x + 1) * ts, (y + 1) * ts)

    def get_tile_2x(self, i):
        ts = self.ts * 2
        x = i % 8
        y = i / 8
        return self.image.get_region(x * ts, y * ts, (x + 1) * ts, (y + 1) * ts)

    def align_rect(self, rect):
        tx = ceil(rect.width / self.ts)
        ty = ceil(rect.height / self.ts)
        return Rect(rect.x1, rect.y1, rect.x1 + tx * self.ts, rect.y1 + ty * self.ts)

    def get_ui_rect(self, rect):
        return Rect(rect.x1 / ui_scale, rect.y1 / ui_scale, rect.x2 / ui_scale, rect.y2 / ui_scale)

    def draw_box(self, rect, border_tiles=None):
        # 0 1 2
        # 3 4 5
        # 6 7 8

        if not border_tiles:
            border_tiles = self.white_border
        ts = self.ts

        bacon.push_transform()
        bacon.scale(ui_scale, ui_scale)
        x1 = rect.x1 / ui_scale
        y1 = rect.y1 / ui_scale
        x2 = rect.x2 / ui_scale
        y2 = rect.y2 / ui_scale

        # corners
        bacon.draw_image(border_tiles[0], x1 - ts, y1 - ts)
        bacon.draw_image(border_tiles[2], x2, y1 - ts)
        bacon.draw_image(border_tiles[6], x1 - ts, y2)
        bacon.draw_image(border_tiles[8], x2, y2)

        # top/bottom
        bacon.draw_image(border_tiles[1], x1, y1 - ts, x2, y1)
        bacon.draw_image(border_tiles[7], x1, y2, x2, y2 + ts)

        # left/right
        bacon.draw_image(border_tiles[3], x1 - ts, y1, x1, y2)
        bacon.draw_image(border_tiles[5], x2, y1, x2 + ts, y2)

        # fill
        bacon.draw_image(border_tiles[4], x1, y1, x2, y2)

        bacon.pop_transform()

    def draw_image(self, image, x, y):
        bacon.draw_image(image, x, y, x + image.width * ui_scale, y + image.height * ui_scale)

    def draw_speech_box(self, text, speaker_x, speaker_y):
        width = min(self.font.measure_string(text), ui_width / 2)
        x1 = max(0, min(speaker_x, ui_width - width - 16))
        x2 = x1 + width
        y2 = speaker_y - 28

        style = bacon.Style(self.font)
        run = bacon.GlyphRun(style, text)
        glyph_layout = bacon.GlyphLayout([run], x1, y2, width, None, bacon.Alignment.left, bacon.VerticalAlignment.bottom)
        if glyph_layout.content_width < 48:
            glyph_layout = bacon.GlyphLayout([run], x1, y2, 48, None, bacon.Alignment.center, bacon.VerticalAlignment.bottom)
        y1 = y2 - glyph_layout.content_height - 8 # HACK workaround
        x2 = x1 + max(glyph_layout.content_width, 48)

        self.draw_box(Rect(x1, y1, x2, y2), self.speech_border)
        self.draw_image(self.speech_point, speaker_x + 16, y2)

        bacon.set_color(0, 0, 0, 1)
        bacon.draw_glyph_layout(glyph_layout)
        bacon.set_color(1, 1, 1, 1)

    def draw_info_box(self, text, speaker_x, speaker_y):
        width = min(self.font.measure_string(text), 250, ui_width - speaker_x - 16)
        x1 = speaker_x
        x2 = x1 + width
        y1 = speaker_y

        style = bacon.Style(self.font)
        run = bacon.GlyphRun(style, text)
        glyph_layout = bacon.GlyphLayout([run], x1, y1, width, None, bacon.Alignment.left, bacon.VerticalAlignment.top)
        if y1 + glyph_layout.content_height > ui_height - 116:
            glyph_layout.y = y1 = ui_height - 116 - glyph_layout.content_height
        y2 = y1 + glyph_layout.content_height
        x2 = x1 + glyph_layout.content_width

        self.draw_box(Rect(x1, y1, x2, y2), self.info_border)
        self.draw_image(self.info_arrow, x1 - 32, speaker_y)
        bacon.draw_glyph_layout(glyph_layout)

    def draw_message_box(self, text):
        width = min(self.font.measure_string(text), ui_width / 3)
        cx = ui_width / 2
        cy = ui_height / 2 - 32

        style = bacon.Style(self.font)
        run = bacon.GlyphRun(style, text)
        glyph_layout = bacon.GlyphLayout([run], cx - width / 2, cy, width, None, bacon.Alignment.center, bacon.VerticalAlignment.center)
        y1 = cy - glyph_layout.content_height / 2
        y2 = cy + glyph_layout.content_height / 2
        x1 = cx - glyph_layout.content_width / 2
        x2 = cx + glyph_layout.content_width / 2

        self.draw_box(Rect(x1, y1, x2, y2))

        bacon.set_color(0, 0, 0, 1)
        bacon.draw_glyph_layout(glyph_layout)
        bacon.set_color(1, 1, 1, 1)

    def draw_text_box(self, text, x, y, border_tiles):
        width = self.font.measure_string(text) + 8
        x1 = x - width / 2
        y1 = y - self.font.height
        x2 = x + width / 2
        y2 = y
        self.draw_box(Rect(x1, y1, x2, y2), border_tiles)
        bacon.draw_string(self.font, text, x1 + 4, y1, vertical_align = bacon.VerticalAlignment.top)

    def draw_combat_selection_box(self, text, x, y):
        width = self.font.measure_string(text) + 8
        x1 = x - width / 2
        y1 = y - self.font.height / 2
        x2 = x1 + width
        y2 = y + self.font.height
        self.draw_box(Rect(x1, y1, x2, y2), self.stat_border_active)
        self.draw_image(self.combat_selected_arrow, x - 8, y1 - 16)
        bacon.draw_string(self.font, text, x1 + 4, y1 + 4, vertical_align=bacon.VerticalAlignment.top)

ui = UI()


class MenuItem(object):
    def __init__(self, name, description, func=None, enabled=True):
        self.name = name
        self.description = description
        self.func = func
        self.enabled = enabled

class Menu(object):
    max_items = 6
    title = None
    align = bacon.Alignment.center
    vertical_align = bacon.VerticalAlignment.center
    x = ui_width / 2
    y = ui_height / 2
    min_width = 200
    enable_info = True
    enable_border = True

    def __init__(self, world):
        self.world = world
        self.items = []
        self.can_dismiss = True
        self.selected_index = 0
        self.scroll_offset = 0

    def layout(self):
        self.width = 0
        self.scrollable = len(self.items) > self.max_items
        self.selected_index = 0

        height = self.visible_item_count * ui.font.height
        width = max(ui.font.measure_string(item.name) for item in self.visible_items)
        width = max(width, self.min_width)

        if self.title:
            height += ui.font.height * 2
            width = max(width, ui.font.measure_string(self.title))
        
        if self.scrollable:
            height += 64

        if self.align == bacon.Alignment.left:
            x1 = self.x
        elif self.align == bacon.Alignment.center:
            x1 = self.x - width / 2

        if self.vertical_align == bacon.VerticalAlignment.top:
            y1 = self.y
        elif self.vertical_align == bacon.VerticalAlignment.center:
            y1 = self.y - height / 2
        elif self.vertical_align == bacon.VerticalAlignment.bottom:
            y1 = self.y - height

        self.x1 = x1
        self.y1 = y1
        self.x2 = x1 + width
        self.y2 = y1 + height
        
    @property
    def selected_item(self):
        return self.items[self.selected_index]

    @property
    def visible_item_count(self):
        return min(self.max_items, len(self.items))

    @property
    def visible_items(self):
        return self.items[self.scroll_offset:self.scroll_offset + self.visible_item_count]

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
                if self.selected_item.func:
                    self.selected_item.func()

    def move_selection(self, dir):
        start = max(0, self.selected_index)
        self.selected_index = (self.selected_index + dir) % len(self.items)
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + self.max_items:
            self.scroll_offset = self.selected_index - self.max_items + 1
        
    def draw(self):
        x1 = self.x1
        y1 = self.y1
        x2 = self.x2
        y2 = self.y2
        align = self.align
        
        if align == bacon.Alignment.left:
            x = self.x1
        elif align == bacon.Alignment.center:
            x = (self.x1 + self.x2) / 2

        if self.enable_border:
            ui.draw_box(Rect(x1, y1, x2, y2), ui.menu_border)

        y = y1
        if self.title:
            bacon.draw_string(ui.font, self.title, x, y, None, None, align, bacon.VerticalAlignment.top)
            y += ui.font.height * 2

        if self.scrollable:
            ui.draw_image(ui.menu_up_image, (x1 + x2) / 2 - 16, y)
            y += 32

        info_y = y2
        for i, item in enumerate(self.items):
            if i < self.scroll_offset:
                continue
            if i - self.scroll_offset >= self.max_items:
                break

            if i == self.selected_index:
                info_y = y

            self.activate_menu_item_color(i == self.selected_index, item.enabled)
            bacon.draw_string(ui.font, item.name, x, y, align = align, vertical_align = bacon.VerticalAlignment.top)
            y += ui.font.height

        bacon.set_color(1, 1, 1, 1)
        if self.scrollable:
            ui.draw_image(ui.menu_down_image, (x1 + x2) / 2 - 16, y)
            y += 32

        if self.enable_info:
            self.draw_status(self.selected_item.description, x2, info_y)

    def draw_status(self, msg, x, y):
        if self.enable_info and self.world.menu_stack[-1] is self and game.world is self.world:
            ui.draw_info_box(msg, x + 20, y - 4)

    def activate_menu_item_color(self, selected, enabled):
        if not enabled:
            m = 0.5
        else:
            m = 1

        if selected:
            bacon.set_color(m, m, m, 1)
        else:
            bacon.set_color(m * 164.0 / 255, m * 186.0 / 255, m * 201.0 / 255, 1)

class World(object):
    active_script = None
    active_script_sprite = None
    map_script_sprite = None
    current_character = None
    quest_name = ''

    def __init__(self, map_id):
        map = tiled.parse('res/' + map_id + '.tmx')
        self.menu_stack = []

        self.timeouts = []

        self.map = map
        self.tile_size = map.tile_width
        self.sprites = []
        self.camera_x = self.camera_y = 0
        
        self.player_slots = [None] * 4
        self.monster_slots = [None] * 4

        self.dialog_sprite = None
        self.dialog_text = None

        for layer in self.map.object_layers:
            for obj in layer.objects:
                if not obj.image:
                    continue
                x = obj.x / self.tile_size
                y = obj.y / self.tile_size
                sprite = self.add_sprite(obj.image, x, y - 1)
                sprite.name = obj.name
                sprite.properties = obj.properties

        for layer in self.map.layers[:]:
            if layer.name == 'Sprites':
                self.map.layers.remove(layer)
                for i, image in enumerate(layer.images):
                    if image:
                        x = i % self.map.cols
                        y = i / self.map.cols
                        self.add_sprite(image, x, y)
                    
    def start(self):
        pass

    def do_dialog(self, sprite, text):
        if text:
            self.dialog_sprite = sprite
            self.dialog_text = text
            if sprite:
                debug.println('%s says %s' % (sprite.name, text))
            else:
                debug.println('message: %s' % text)
            return True
        else:
            return False

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
        return sprite

    def get_sprite_at(self, x, y):
        for sprite in self.sprites:
            if sprite.x == x and sprite.y == y:
                return sprite
        return None

    def push_menu(self, menu):
        menu.layout()
        self.menu_stack.append(menu)

    def pop_menu(self):
        self.menu_stack.pop()

    def pop_all_menus(self):
        del self.menu_stack[:]

    def after(self, timeout, func):
        self.timeouts.append([timeout, func])
        
    def update(self):
        if self.timeouts:
            for timeout in self.timeouts:
                timeout[0] -= bacon.timestep
            for timeout in [timeout for timeout in self.timeouts if timeout[0] <= 0]:
                timeout[1]()
                if timeout in self.timeouts:
                    self.timeouts.remove(timeout)

    def draw_world(self):
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
        self.draw_dialog()

    def draw_dialog(self):
        if self.dialog_text:
            ts = self.tile_size
            
            viewport = Rect(self.camera_x, 
                            self.camera_y, 
                            self.camera_x + map_width,
                            self.camera_y + map_height)

            width = min(ui_width / 2, debug.font.measure_string(self.dialog_text))
            if self.dialog_sprite:
                speaker_x = (self.dialog_sprite.x * ts - viewport.x1) * map_scale
                speaker_y = (self.dialog_sprite.y * ts - viewport.y1) * map_scale
                ui.draw_speech_box(self.dialog_text, speaker_x, speaker_y)
            else:
                ui.draw_message_box(self.dialog_text)

    def draw(self):
        self.draw_world()
        self.draw_menu()
        self.draw_hud()
        self.draw_stats()

    def draw_menu(self):
        for menu in self.menu_stack:
            menu.draw()

    def get_room_name(self):
        return ''

    def get_quest_name(self):
        return self.quest_name

    def draw_hud(self):
        ui.draw_box(Rect(0, 0, ui_width, ui.font.height), ui.stat_border)
        bacon.draw_string(debug.font, self.get_quest_name(), 0, 0, align=bacon.Alignment.left, vertical_align=bacon.VerticalAlignment.top)
        bacon.draw_string(debug.font, self.get_room_name(), ui_width / 2, 0, align=bacon.Alignment.center, vertical_align=bacon.VerticalAlignment.top)
        bacon.draw_string(debug.font, '$%d' % game.money, ui_width, 0, align=bacon.Alignment.right, vertical_align=bacon.VerticalAlignment.top)

    def draw_stats(self):
        margin = 4
        padding = 4
        box_width = ui_width / 4 - margin * 2
        box_height = ui.font.height * 5 + padding * 2
        line_height = ui.font.height

        for i in range(4):
            character = game.allies[i] if i < len(game.allies) else None
            if not character:
                border = ui.stat_border_disabled
            elif character is self.current_character:
                border = ui.stat_border_active
            else:
                border = ui.stat_border

            x = margin + i * (box_width + margin * 2)
            y = ui_height - box_height - margin
            ui.draw_box(Rect(x, y, x + box_width, y + box_height), border)
            
            if character:
                y -= ui.font.ascent
                x += padding
                y += padding
                bacon.set_color(1, 1, 1, 1)
                bacon.draw_string(ui.font, character.data.name, x, y)
                bacon.draw_string(ui.font, 'LVL: %d' % character.level, x, y + line_height)
                bacon.draw_string(ui.font, 'XP: %d/%d' % (character.xp, get_level_row(character.level + 1).xp), x, y + line_height * 2)
                bacon.draw_string(ui.font, 'Votes: %d/%d' % (character.votes, character.max_votes), x, y + line_height * 3)
                bacon.draw_string(ui.font, 'Spin:  %d/%d' % (character.spin, character.max_spin), x, y + line_height * 4)

    def on_dismiss_dialog(self):
        self.continue_script()

    def on_world_key_pressed(self, key):
        pass

    def on_key_pressed(self, key):
        if self.timeouts:
            return

        if self.dialog_text:
            self.dialog_text = None
            self.on_dismiss_dialog()
            return

        if self.menu_stack:
            self.menu_stack[-1].on_key_pressed(key)
            return

        self.on_world_key_pressed(key)

    def on_key_released(self, key):
        pass

    def get_script_sprite(self, param):
        return None
    
    def continue_script(self):
        if not self.active_script:
            return

        script = self.active_script
        sprite = self.active_script_sprite
        done = False
        while not done and sprite.script_index < len(script):
            script_row = script[sprite.script_index]
            done = self.run_script_row(sprite, script_row)
            sprite.script_index += 1

        if sprite.script_index >= len(script):
            self.active_script = None

    def run_script(self, sprite, trigger):
        if trigger not in game_data.script:
            return
        if sprite is None:
            sprite = self.map_script_sprite
        if sprite is None:
            sprite = self.map_script_sprite = Sprite(None, -100, -100)
        self.active_script = game_data.script[trigger]
        self.active_script_sprite = sprite
        self.continue_script()

    def run_script_row(self, sprite, script_row):
        action = script_row.action
        if action.startswith('_'):
            return False

        param = script_row.param
        dialog = script_row.dialog
        if action == 'Say':
            if param:
                sprite = self.get_script_sprite(param)
            self.do_dialog(sprite, dialog)
        elif action == 'PlayerSay':
            self.do_dialog(self.player_sprite, dialog)
        elif action == 'Message':
            self.do_dialog(None, dialog)
        elif action == 'QuestName':
            self.quest_name = dialog
            return False
        elif action == 'Encounter':
            game.push_world(CombatWorld('combat1', param))
        elif action == 'Destroy':
            self.sprites.remove(sprite)
            return False
        elif action == 'GiveItem':
            game.quest_items.append(game_data.quest_items[param])
            return self.do_dialog(None, dialog)
        elif action == 'GiveVotes':
            amount = int(param)
            for ally in game.allies:
                ally.votes = min(ally.votes + amount, ally.max_votes)
            return self.do_dialog(None, dialog)
        elif action == 'GiveSpin':
            amount = int(param)
            for ally in game.allies:
                ally.spin = min(ally.spin + amount, ally.max_spin)
            return self.do_dialog(None, dialog)
        elif action == 'RestoreVotes':
            for ally in game.allies:
                ally.votes = ally.max_votes
            return self.do_dialog(None, dialog)
        elif action == 'RestoreSpin':
            for ally in game.allies:
                ally.spin = ally.max_spin
            return self.do_dialog(None, dialog)
        elif action == 'GiveMoney':
            game.money += int(param)
            return self.do_dialog(None, dialog)
        elif action == 'RequireItem' or action == 'RequireItemMessage' or action == 'RequireItemPlayerSay':
            if param in (item.id for item in game.quest_items) or debug.disable_require:
                return False # satisfied, move to next line immediately
            else:
                if action == 'RequireItemMessage':
                    dialog_sprite = None
                elif action == 'RequireItemPlayerSay':
                    dialog_sprite = self.player_sprite
                else:
                    dialog_sprite = sprite
                self.do_dialog(dialog_sprite, dialog)
                sprite.script_index -= 1
                self.active_script = None
        elif action == 'RequireFlag' or action == 'RequireFlagPlayerSay':
            if param in game.quest_flags  or debug.disable_require:
                return False # satisfied, move to next line immediately
            else:
                self.do_dialog(sprite if action == 'RequireFlag' else self.player_sprite, dialog)
                sprite.script_index -= 1
                self.active_script = None
        elif action == 'SetFlag':
            game.quest_flags.add(param)
            return False
        elif action == 'UnsetFlag':
            if param in game.quest_flags:
                game.quest_flags.remove(param)
            return False
        elif action == 'Increment':
            if param not in game.quest_vars:
                game.quest_vars[param] = 0
            game.quest_vars[param] += 1
            return False
        elif action == 'RequireCount':
            value = 0
            param, required_value = param.split(':')
            param = param.strip()
            required_value = int(required_value)
            if param in game.quest_vars:
                value = game.quest_vars[param]
            if value >= required_value or debug.disable_require:
                return False # satisfied
            else:
                self.do_dialog(sprite, dialog)
                sprite.script_index -= 1
                self.active_script = None
        elif action == 'LearnAttack':
            character = game.player
            attack_id = param
            if ':' in param:
                character_id, attack_id = param.split(':')
                character = game.get_ally(character_id)
                if not character:
                    debug.println('Missing ally: %s' % character_id)
                    return False
            attack = game_data.attacks[attack_id]
            if attack.spin_cost:
                character.spin_attacks.append(game_data.attacks[attack_id])
            else:
                character.standard_attacks.append(game_data.attacks[attack_id])
            return self.do_dialog(None, dialog)
        elif action == 'AddAlly':
            character_id, level = param.split(':')
            game.allies.append(Character(character_id, int(level), game.player.item_attacks, False))
            return self.do_dialog(None, dialog)
        elif action == 'RemoveAlly':
            ally = game.get_ally(param)
            if ally:
                game.allies.remove(ally)
            return self.do_dialog(None, dialog)
        elif action == 'GotoMap':
            game.goto_map(param)
        elif action == 'BeginCombat':
            self.begin_round()
        elif action == 'Shop':
            self.push_menu(ShopMenu(self, param))
            return True
        elif action == 'Label':
            return False
        elif action == 'Reset' or action == 'Jump':
            for i, row in enumerate(self.active_script):
                if row.action == 'Label' and row.param == param:
                    sprite.script_index = i
                    break
            return action == 'Reset'
        elif action == 'Save':
            if game.save(param):
                self.do_dialog(None, 'Game saved.')
            else:
                self.do_dialog(None, 'Error saving game, progress will be lost on exit')
        elif action == 'PlaySound':
            try:
                bacon.Sound(param).play()
            except:
                pass
            return False
        elif action in ('CheatXP', 'CheatCunning', 'CheatWit', 'CheatFlair', 'CheatSpeed', 'CheatCharisma'):
            if ':' in param:
                character_id, value = param.split(':')
                character = game.get_ally(character_id)
                value = int(value)
            else:
                character = game.player
                value = int(param)
            if action == 'CheatXP':
                character.xp = int(value)
                character.level = get_level_for_xp(game.player.xp)
                level_row = get_level_row(character.level)
                character.max_spin = level_row.spin
                character.max_votes = level_row.votes
            elif action == 'CheatCunning':
              character.cunning = value
            elif action == 'CheatWit':
              character.wit = value
            elif action == 'CheatFlair':
              character.flair = value
            elif action == 'CheatSpeed':
              character.speed = value
            elif action == 'CheatCharisma':
                character.charism = value
            return False
        else:
            raise Exception('Unsupported script action "%s"' % action)

        # Return False only if this script row performs no yielding UI
        return True

class MapMenu(Menu):
    def __init__(self, world):
        super(MapMenu, self).__init__(world)

        enable_inventory = game.quest_items or game.player.item_attacks

        self.title = 'Paused'
        self.items.append(MenuItem('Resume', 'Back to the game', self.on_resume))
        self.items.append(MenuItem('Inventory', 'Check your briefcase', self.on_inventory, enabled=enable_inventory))
        self.items.append(MenuItem('Quit', 'Exit the game', self.on_quit))

    def on_resume(self):
        self.world.pop_menu()

    def on_inventory(self):
        self.world.pop_menu()
        self.world.push_menu(InventoryMenu(self.world))

    def on_quit(self):
        bacon.quit()

class InventoryMenu(Menu):
    def __init__(self, world):
        super(InventoryMenu, self).__init__(world)
        self.title = 'Inventory'
        for ia in game.player.item_attacks:
            name = ia.attack.name
            if ia.quantity > 1:
                name = '%s (x%d)' % (name, ia.quantity)
            func = None
            for effect in ia.attack.effects:
                if effect.function == 'add_permanent':
                    func = partial(self.on_consume, ia)
            if func:
                name += ' >'
            self.items.append(MenuItem(name, ia.attack.description, func, enabled=(func is not None)))

        for item in game.quest_items:
            self.items.append(MenuItem(item.name, item.description, enabled=False))

    def on_consume(self, ia):
        self.world.push_menu(InventoryConsumeMenu(self.world, ia))

class InventoryConsumeMenu(Menu):
    def __init__(self, world, ia):
        super(InventoryConsumeMenu, self).__init__(world)
        for ally in game.allies:
            self.items.append(MenuItem(ally.data.name, 'Apply %s to %s' % (ia.attack.name, ally.data.name), partial(self.on_consume, ia, ally)))

    def on_consume(self, ia, ally):
        for effect in ia.attack.effects:
            if effect.function == 'add_permanent':
                effect.apply(ally)
        ally.remove_item_attack(ia.attack)
        self.world.pop_all_menus()

class ShopMenu(Menu):
    def __init__(self, world, shop_id):
        super(ShopMenu, self).__init__(world)
        wares = game_data.shops[shop_id]
        for ware in wares:
            name = '%s ($%d)' % (ware.item_attack.name, ware.price)
            item = MenuItem(name, '', partial(self.on_purchase, ware))
            item.ware = ware
            self.items.append(item)
        self.items.append(MenuItem('Done', 'Leave store', self.on_done))
        self.update_items()

    def update_items(self):
        for item in self.items:
            if hasattr(item, 'ware'):
                count = 0
                for ia in game.player.item_attacks:
                    if ia.attack == item.ware.item_attack:
                        count = ia.quantity
                item.description = '%s (You currently have %d of these).' % (item.ware.item_attack.description, count)
                item.enabled = item.ware.price <= game.money

    def on_purchase(self, ware):
        game.money -= ware.price
        game.player.add_item_attack(ware.item_attack)
        self.update_items()

    def on_done(self):
        self.world.pop_menu()
        self.world.on_dismiss_dialog()

        
def get_tile_collision(tile):
    if not hasattr(tile, 'properties'):
        return ''
    if 'c' not in tile.properties:
        return ''
    c = tile.properties['c']
    if not c:
        c = 'udlr'
    return c

class MapWorld(World):
     
    input_movement = {
        bacon.Keys.left: (-1, 0),
        bacon.Keys.right: (1, 0),
        bacon.Keys.up: (0, -1),
        bacon.Keys.down: (0, 1),
    }

    def __init__(self, map_id):
        super(MapWorld, self).__init__(map_id)
        self.move_timeout = -1

        player_slot = self.player_slots[0]
        if player_slot:
            self.player_sprite = Sprite(game.player.image, player_slot.x, player_slot.y)
            self.player_sprite.name = 'Player'
            self.sprites.append(self.player_sprite)
        else:
            self.player_sprite = None

        self.rooms_layer = None
        for layer in self.map.object_layers:
            if layer.name == 'Rooms':
                self.rooms_layer = layer
                
    def update(self):
        if self.move_timeout > 0:
            self.move_timeout -= bacon.timestep
            if self.move_timeout <= 0:
                dx = dy = 0
                for k, v in self.input_movement.items():
                    if k in bacon.keys:
                        dx += v[0]
                        dy += v[1]
                self.move(dx, dy)
        self.update_camera()
        
    def update_camera(self):
        ts = self.tile_size

        if self.player_sprite:
            self.camera_x = self.player_sprite.x * ts - map_width / 2
            self.camera_y = self.player_sprite.y * ts - map_height / 2 + 2 * ts
            self.camera_x = clamp(self.camera_x, 0, self.map.tile_width * self.map.cols - map_width)
            self.camera_y = clamp(self.camera_y, 0, self.map.tile_height * self.map.rows - map_height)
        else:
            self.camera_x = self.camera_y = 0

    def on_world_key_pressed(self, key):
        if key in self.input_movement:
            dx, dy = self.input_movement[key]
            self.move(dx, dy)
        elif key == bacon.Keys.escape:
            self.push_menu(MapMenu(self))

    def on_key_released(self, key):
        self.move_timeout = -1

    def move(self, dx, dy):
        self.move_timeout = 0.2
        if dx and dy:
            self.move(dx, 0)
            self.move(0, dy)

        other = self.get_sprite_at(self.player_sprite.x + dx, self.player_sprite.y + dy)
        if other:
            self.on_collide(other)
        else:
            x = self.player_sprite.x
            y = self.player_sprite.y
            if x + dx < 0 or x + dx >= self.map.cols or \
                y + dy < 0 or y + dy >= self.map.rows:
                return

            tile_index = self.map.get_tile_index(x * self.tile_size, 
                                                 y * self.tile_size)
            next_tile_index = self.map.get_tile_index((x + dx) * self.tile_size, 
                                                      (y + dy) * self.tile_size)
            for layer in self.map.layers:
                tile = layer.images[tile_index]
                next_tile = layer.images[next_tile_index]

                c = get_tile_collision(tile)
                next_c = get_tile_collision(next_tile)
            
                if not debug.disable_collision:
                    if dx < 0 and ('l' in c or 'r' in next_c):
                        return
                    elif dx > 0 and ('r' in c or 'l' in next_c):
                        return
                    elif dy < 0 and ('u' in c or 'd' in next_c):
                        return
                    elif dy > 0 and ('d' in c or 'u' in next_c):
                        return

            self.player_sprite.x += dx
            self.player_sprite.y += dy
        
    def on_collide(self, other):
        if other.name in game_data.script:
            self.run_script(other, other.name)

    def get_script_sprite(self, param):
        for sprite in self.sprites:
            if sprite.name == param:
                return sprite

    def get_room_name(self):
        if not self.rooms_layer:
            return ''

        x = self.player_sprite.x * self.tile_size
        y = self.player_sprite.y * self.tile_size
        for room in self.rooms_layer.objects:
            if x >= room.x and y >= room.y and \
                x < room.x + room.width and \
                y < room.y + room.height:
                return room.name

        return ''

    
class TitleMenu(Menu):
    def __init__(self, world):
        super(TitleMenu, self).__init__(world)
        self.items.append(MenuItem('New Game', '', self.on_new_game))
        self.items.append(MenuItem('Continue', '', self.on_continue, get_recent_save_filename() is not None))
        self.items.append(MenuItem('Quit', '', self.on_quit))
        self.enable_info = False
        self.can_dismiss = False
        self.y = ui_height - 70

    def on_new_game(self):
        game.goto_map('act1')

    def on_continue(self):
        if not game.load():
            self.world.do_dialog(None, 'Failed to load save game.')

    def on_quit(self):
        bacon.quit()

class TitleWorld(World):
    def __init__(self, map):
        super(TitleWorld, self).__init__(map)
        self.background = title_image
        self.after(2, self.show_menu)
        
    def show_menu(self):
        if not self.menu_stack:
            self.push_menu(TitleMenu(self))
            del self.timeouts[:]

    def on_key_pressed(self, key):
        super(TitleWorld, self).on_key_pressed(key)
        self.show_menu()

    def draw(self):
        bacon.draw_image(self.background, 0, 0, ui_width, ui_height)
        self.draw_menu()
        self.draw_dialog()

class EndWorld(World):
    def __init__(self, map):
        super(EndWorld, self).__init__(map)
        game.play_music('res/wwing2.ogg')
        self.background = end_image

    def draw(self):
        bacon.draw_image(self.background, 0, 0, ui_width, ui_height)
        bacon.set_color(0, 0, 0, 1)

        x = 16
        self.y = 16 - ui.font.ascent
        def out(text):
            bacon.draw_string(ui.font, text, x, self.y); 
            self.y += ui.font.height

        out('Goodnight, Mr President')
        out('')
        out('A game for PyWeek #18 by Amanda Schofield and Alex Holkner')
        
        self.y = ui_height - 11 * ui.font.height
        out('04B-03.ttf')
        out('Yuji Oshimoto')
        out('http://dsg4.com/04/extra/bitmap/')
        out('')
        out('The West Wing Theme Song')
        out('Nick Maynard')
        out('http://nickmaynard.tumblr.com/post/28877574787/attention-all-fans-of-the-west-wing-and-chiptune')
        out('')
        out('Bacon Game Engine')
        out('https://github.com/aholkner/bacon')

        bacon.set_color(1, 1, 1, 1)
        self.draw_dialog()

    def on_world_key_pressed(self, key):
        if key == bacon.Keys.escape:
            bacon.quit()

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
            if isinstance(game.world, CombatWorld):
                game.world.apply_damage(character, -value)
            else:
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
            game.money = max(0, game.money + value)

    def apply(self, character):
        if self.function == 'reduce':
            self._add_value(character, -self.value)
        elif self.function == 'add' or self.function == 'add_permanent':
            self._add_value(character, self.value)
        elif self.function == 'revive':
            character.votes = int(character.max_votes * self.value)
            game.world.set_dead(character, False)
            game.world.add_floater(character, 'Revived!', ui.floater_border_grey)
        elif self.function == 'call_friends':
            character_id, level = self.attribute.split(':')
            game.world.ai_summon(character_id, int(level), self.value)

    def unapply(self, character):
        if self.function == 'reduce':
            self._add_value(character, self.value)
        elif self.function == 'add':
            self._add_value(character, -self.value)

    def update(self, character):
        if self.function == 'drain':
            game.world.add_floater(character, self.id, ui.floater_border_grey, 1) 
            self._add_value(character, -self.value)

class ActiveEffect(object):
    def __init__(self, effect, rounds):
        self.effect = effect
        self.rounds = rounds

class ItemAttack(object):
    def __init__(self, attack, quantity=1):
        self.attack = attack
        self.quantity = quantity

def add_attack_to_itemattack_list(item_attacks, attack):
    for ia in item_attacks:
        if ia.attack is attack:
            ia.quantity += 1
            return
    item_attacks.append(ItemAttack(attack, 1))
       
class Character(object):
    accumulated_spin_damage = 0

    def __init__(self, id, level, item_attacks, ai=True):
        level = int(level)
        self.id = id
        self.image = game_sprites[id]
        self.level = level
        level_row = get_level_row(level)
        self.xp = level_row.xp
        self.ai = ai
        self.dead = False
        self.summoning_sickness = True
        self.data = row = random.choice(game_data.characters[id])
        if ai:
            self.votes = self.max_votes = self.calc_stat(row.votes_base, row.votes_lvl)
            self.spin = self.max_spin = self.calc_stat(row.spin_base, row.spin_lvl)
        else:
            self.votes = self.max_votes = level_row.votes
            self.max_spin = level_row.spin
            self.spin = 0

        self.speed = self.calc_stat(row.speed_base, row.speed_lvl)
        self.wit = self.calc_stat(row.wit_base, row.wit_lvl)
        self.cunning = self.calc_stat(row.cunning_base, row.cunning_lvl)
        self.charisma = self.calc_stat(row.charisma_base, row.charisma_lvl)
        self.flair = self.calc_stat(row.flair_base, row.flair_lvl)
        self.resistance = 0
        self.active_effects = []
        self.item_attacks = item_attacks

        if ai:
            self.spin_attacks = row.spin_attacks
            self.standard_attacks = row.standard_attacks
        else:
            self.spin_attacks = list(row.spin_attacks)
            self.standard_attacks = list(row.standard_attacks)

    def add_item_attack(self, attack):
        add_attack_to_itemattack_list(self.item_attacks, attack)

    def remove_item_attack(self, attack):
        for ia in self.item_attacks:
            if ia.attack is attack:
                ia.quantity -= 1
                if ia.quantity == 0:
                    self.item_attacks.remove(ia)
                return
        
    def calc_stat(self, base, exp):
        return base + (self.level - 1) * exp
    
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
        active_effect.effect.unapply(self)
        self.active_effects.remove(active_effect)
        debug.println('Remove effect %s from %s' % (active_effect.effect.id, self.id))

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

class CombatMenu(Menu):
    min_width = 96

    def layout(self):
        if self.world.menu_stack:
            self.x = self.world.menu_stack[-1].x2
        else:
            self.x = 16
        self.y = ui_height - 116
        self.align = bacon.Alignment.left
        self.vertical_align = bacon.VerticalAlignment.bottom

        super(CombatMenu, self).layout()

class CombatMenuMain(CombatMenu):
    def __init__(self, world):
        super(CombatMenuMain, self).__init__(world)
        character = self.world.current_character

        #workaround for unknown bug
        world.pop_all_menus()

        self.items.append(MenuItem('Offense >', 'Launch a political attack', self.on_offense))
        self.items.append(MenuItem('Defense', game_data.attacks['DEFENSE'].description, self.on_defense))
        self.items.append(MenuItem('Spin >', 'Run spin to get control of the situation', self.on_spin, enabled=bool(character.spin_attacks)))
        self.items.append(MenuItem('Items >', 'Use an item from your briefcase', self.on_items, enabled=bool(character.item_attacks)))
        self.can_dismiss = False

    def on_offense(self):
        self.world.push_menu(CombatOffenseMenu(self.world, self.world.current_character.standard_attacks))

    def on_defense(self):
        self.world.action_attack(game_data.attacks['DEFENSE'], [])

    def on_spin(self):
        self.world.push_menu(CombatOffenseMenu(self.world, self.world.current_character.spin_attacks))

    def on_items(self):
        self.world.push_menu(CombatOffenseMenu(self.world, self.world.current_character.item_attacks))

class CombatOffenseMenu(CombatMenu):
    def __init__(self, world, attacks):
        super(CombatOffenseMenu, self).__init__(world)
        for attack in attacks:
            if isinstance(attack, ItemAttack):
                quantity = attack.quantity
                attack = attack.attack
            else:
                quantity = 1

            name = attack.name
            enabled = True

            if attack.underlying_stat == 'Money':
                name = '%s ($%d)' % (name, world.encounter.bribe_cost)
                enabled = enabled and game.money >= world.encounter.bribe_cost

            if quantity > 1:
                name = '%s (x%d)' % (attack.name, quantity)

            enabled = enabled and world.current_character.spin >= attack.spin_cost
            if attack.target_type == 'DeadFriendly' and not [slot for slot in self.world.player_slots if slot.character and slot.character.dead]:
                enabled = False

            description = attack.description
            if attack.spin_cost:
                description += ' (Uses %d spin).' % attack.spin_cost

            self.items.append(MenuItem(name, description, partial(self.select, attack), enabled=enabled))

    def select(self, attack):
        if attack.target_type == 'None':
            self.world.action_attack(attack, [])
        else:
            self.world.push_menu(CombatTargetMenu(self.world, attack.target_type, attack.target_count, partial(self.choose_target, attack)))

    def choose_target(self, attack, targets):
        self.world.action_attack(attack, targets)
        
class CombatTargetMenu(CombatMenu):
    def __init__(self, world, target_type, target_count, func):
        super(CombatTargetMenu, self).__init__(world)
        self.target_type = target_type
        self.target_count = target_count
        self.func = func
        self.can_dismiss = True
        self.enable_info = False
        self.items = [MenuItem('< Choose Target >', 'Choose target')]

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
        return self.slots[self.selected_index:self.selected_index + self.target_count]

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
            x = slot.x * self.world.tile_size * map_scale
            y = slot.y * self.world.tile_size * map_scale
            ui.draw_image(ui.combat_target_arrow, x + 4, y - 32)
        super(CombatTargetMenu, self).draw()
        
class GameOverMenu(Menu):
    def __init__(self, world):
        super(GameOverMenu, self).__init__(world)
        self.title = 'You are defeated'
        self.can_dismiss = False
        self.items.append(MenuItem('Restart this encounter', 'You failed this time, but next time the dice rolls may be in your favour', self.on_restart_encounter))
        self.items.append(MenuItem('Quit game', 'Exit the game', self.on_quit))

    def on_restart_encounter(self):
        self.world.restart()

    def on_quit(self):
        bacon.quit()

class Floater(object):
    def __init__(self, text, x, y, border):
        self.text = text
        self.x = x
        self.y = y
        self.border = border
        self.timeout = 1.0

class CombatWorld(World):
    def __init__(self, map, encounter_id):
        super(CombatWorld, self).__init__(map)
        self.encounter = encounter = game_data.encounters[encounter_id]
        for ally in game.allies:
            ally.saved_votes = ally.votes
        self.restart_count = 0

    def start(self):
        encounter = self.encounter
        self.quest_name = encounter.name

        self.floaters = []
        self.active_attack = None
        self.active_targets = None
        self.current_character_index = -1

        self.characters = []
        for i, ally in enumerate(game.allies):
            ally.accumulated_spin_damage = 0
            self.fill_slot(self.player_slots[i], ally)
        
        self.ai_item_attacks = list(encounter.item_attacks)
        if encounter.monster1:
            self.fill_slot(self.monster_slots[0], Character(encounter.monster1, encounter.monster1_lvl, self.ai_item_attacks))
        if encounter.monster2:
            self.fill_slot(self.monster_slots[1], Character(encounter.monster2, encounter.monster2_lvl, self.ai_item_attacks))
        if encounter.monster3:
            self.fill_slot(self.monster_slots[2], Character(encounter.monster3, encounter.monster3_lvl, self.ai_item_attacks))
        if encounter.monster4:
            self.fill_slot(self.monster_slots[3], Character(encounter.monster4, encounter.monster4_lvl, self.ai_item_attacks))

        self.slots = self.player_slots + self.monster_slots

        self.run_script(self.player_slots[0].sprite, self.encounter.id)

        if not self.active_script:
            self.begin_round()
            
    def restart(self):
        del self.sprites[:]
        for slot in self.slots:
            slot.character = None
        self.pop_all_menus()
        self.restart_count += 1
        for ally in game.allies:
            ally.dead = False
            if self.restart_count > 1:
                # Extra help after second retry
                ally.votes = ally.max_votes
                ally.spin = ally.max_spin / 2
            else:
                ally.votes = max(ally.max_votes / 2, ally.saved_votes)
                ally.spin = 0

        self.start()

    @property
    def current_character(self):
        if self.current_character_index >= 0:
            return self.characters[self.current_character_index]

    def fill_slot(self, slot, character):
        slot.character = character
        if character.id == 'Lobbyist001' and self.encounter.id == 'P-med-12':
            slot.y = 4
        slot.sprite = Sprite(character.image, slot.x, slot.y)
        self.sprites.append(slot.sprite)
        self.characters.append(character)

    def get_slot(self, character):
        for slot in self.slots:
            if slot.character is character:
                return slot
        return None

    def begin_round(self):
        for character in self.characters:
            character.summoning_sickness = False
        self.characters.sort(key=lambda c:c.speed, reverse=True)
        self.current_character_index = 0
        while self.current_character_index < len(self.characters) and self.current_character.dead:
            self.current_character_index += 1
        self.begin_turn()

    def get_script_sprite(self, param):
        for slot in self.slots:
            if slot.character and slot.character.id == param:
                return slot.sprite
        return None

    def begin_turn(self):
        if self.current_character_index >= len(self.characters):
            self.begin_round()
            return

        # Check if character misses turn after effects
        miss_turn = self.current_character.has_effect_function('miss_turn')

        # Update character effects
        self.begin_turn_apply_effect(self.current_character.active_effects[:], 0, miss_turn)

    def begin_turn_apply_effect(self, effects, effect_index, miss_turn):
        if self.current_character.dead:
            self.end_turn()
            return

        if effect_index >= len(effects):
            self.begin_turn_end_effects(miss_turn)
            return

        ae = effects[effect_index]
        ae.rounds -= 1
        debug.println('Update effect %s on %s' % (ae.effect.id, self.current_character.id))
        ae.effect.update(self.current_character)
        if ae.rounds <= 0:
            self.current_character.remove_active_effect(ae)

        if self.floaters:
            # Queue up next effect if this one generated a floater
            self.after(1, partial(self.begin_turn_apply_effect, effects, effect_index + 1, miss_turn))
        else:
            # Otherwise continue immediately
            self.begin_turn_apply_effect(effects, effect_index + 1, miss_turn)
    
    def begin_turn_end_effects(self, miss_turn):
        if self.current_character.dead:
            self.end_turn()
            return

        # Miss turn, do AI or show UI
        if miss_turn:
            self.active_attack = game_data.attacks['MISSTURN']
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
            while self.current_character_index < len(self.characters) and \
                (self.current_character.dead or self.current_character.summoning_sickness):
                self.current_character_index += 1
            self.begin_turn()

    def win(self):
        if self.active_script:
            self.continue_script()
        else:
            game.push_world(WinCombatWorld(self))

    def reset(self):
        for character in self.characters:
            character.remove_all_active_effects()
            if character.dead:
                character.dead = False
                character.votes = character.max_votes / 2

    def lose(self):
        self.push_menu(GameOverMenu(self))

    def on_dismiss_dialog(self):
        if not self.active_script:
            game.push_world(WinCombatWorld(self))
        super(CombatWorld, self).on_dismiss_dialog()

    def ai(self):
        source = self.current_character

        # List of all possible attacks
        attacks = list(source.standard_attacks)

        # Add spin attacks we can afford
        attacks += [a for a in source.spin_attacks if a.spin_cost <= source.spin]

        # Add item attacks
        attacks += [ia.attack for ia in source.item_attacks if ia.attack.spin_cost <= source.spin]

        # Filter health gain attacks
        health_targets = [slot.character for slot in self.monster_slots if slot.character and not slot.character.dead and slot.character.votes < slot.character.max_votes]
        if health_targets:
            health_gain_max = max(character.max_votes - character.votes for character in health_targets)
        else:
            health_gain_max = 0
        attacks = [attack for attack in attacks if attack.health_benefit <= health_gain_max]

        # Filter revive attacks
        revive_targets = [slot.character for slot in self.monster_slots if slot.character and slot.character.dead]
        if not revive_targets:
            attacks = [attack for attack in attacks if not attack.is_revive]

        # Filter summon attacks
        can_summon = len([slot for slot in self.monster_slots if not slot.character or slot.character.dead]) > 0
        if not can_summon:
            attacks = [attack for attack in attacks if not attack.is_summon]

        # Random choice of attack
        attack = weighted_choice(attacks, lambda a: a.weight)

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

        # Calculate target slots
        slots.sort(key=lambda slot: slot.x)
        target_count = min(attack.target_count, len(slots))
        max_slot_index = len(slots) - target_count + 1
        slot_index = -1

        # Choose slot to revive
        if attack.is_revive:
            for i, slot in enumerate(slots):
                if slot.character.dead:
                    slot_index = i
                    break

        # Choose slot for health benefit
        if slot_index == -1 and attack.health_benefit > 0:
            best_health = 0
            for i, slot in enumerate(slots):
                health = slot.character.max_votes - slot.character.votes
                if health > best_health:
                    best_health = health
                    slot_index = i

        # Choose slot randomly
        if slot_index == -1:
            slot_index = random.randrange(0, max_slot_index)

        targets = [slot.character for slot in slots[slot_index:slot_index + target_count]]

        self.action_attack(attack, targets)

    def ai_summon(self, character_id, level, count):
        did_destroy = False
        for slot in self.monster_slots:
            if slot.character and slot.character.dead:
                self.sprites.remove(slot.sprite)
                slot.character = None
                did_destroy = True
        
        if did_destroy:
            self.after(0.5, partial(self.ai_summon2, character_id, level, count))
        else:
            self.ai_summon2(character_id, level, count)

    def ai_summon2(self, character_id, level, count):
        for i, slot in enumerate(self.monster_slots):
            if not slot.character:
                self.fill_slot(slot, Character(character_id, level, self.ai_item_attacks))
                count -= 1
                if count == 0:
                    return

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
            base_stat = max(source.cunning, 0)
            game.money = max(0, game.money - self.encounter.bribe_cost)
            debug.println('%s consumed %d money, has %d remaining' % (source.id, self.encounter.bribe_cost, game.money))
        else:
            assert False
        
        # Health attacks (negative damage) need negative base_stat
        if attack.base_damage_min < 0:
            base_stat = -base_stat

        # Consume spin
        if attack.spin_cost:
            source.spin = max(0, source.spin - attack.spin_cost)
            debug.println('%s consumed %d spin, has %d remaining' % (source.id, attack.spin_cost, source.spin))

        # Consume item
        if (not attack in source.spin_attacks) and (not attack in source.standard_attacks):
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
        total_damage = 0
        for target in targets:
            floater_offset = 1
            # Immunity
            if attack in target.data.immunities:
                self.add_floater(target, 'Immune', ui.floater_border_grey)
                debug.println('%s is immune to %s' % (target.id, attack.name))
                continue

            # Crit
            modifiers = 0
            if attack.crit_chance_max:
                crit_chance = random.randrange(attack.crit_chance_min, attack.crit_chance_max + 1)
                crit_success = random.randrange(0, 100) <= crit_chance + source.flair
                debug.println('crit_chance = %s, crit_success = %s, flair = %s' % (crit_chance, crit_success, source.flair))
            else:
                crit_success = False
                debug.println('no crit chance calculated')

            # Damage
            if crit_success:
                self.add_floater(target, 'Critical Hit!', ui.floater_border_grey, floater_offset)
                floater_offset += 1
                debug.println('Critical hit')
                damage = base_stat + (attack.crit_base_damage + modifiers)
            else:
                damage = base_stat + (random.randrange(attack.base_damage_min, attack.base_damage_max + 1) + modifiers)
        
            # Cheat damage
            if debug.massive_damage and not source.ai:
                damage *= 100

            if damage > 0:
                # Charisma
                damage = max(0, damage - target.charisma)

                # Resistance and weakness
                if attack in target.data.resistance:
                    self.add_floater(target, 'Resist', ui.floater_border_grey, floater_offset)
                    floater_offset += 1
                    debug.println('%s is resistant to %s' % (target.id, attack.name))
                    damage -= damage * 0.3
                elif attack in target.data.weaknesses:
                    self.add_floater(target, 'Weakness', ui.floater_border_grey, floater_offset)
                    floater_offset += 1
                    debug.println('%s is weak to %s' % (target.id, attack.name))
                    damage += damage * 0.3

                # Global resistance (defense)
                if target.resistance:
                    self.add_floater(target, 'Defends', ui.floater_border_grey, floater_offset)
                    floater_offset += 1
                    debug.println('%s defends' % target.id)
                damage -= damage * min(1, target.resistance)
                
            tried_damage = attack.base_damage_min != 0 or attack.base_damage_max != 0 or attack.crit_base_damage != 0
            if not tried_damage or damage != 0:
                critical_fail = False

            # Apply damage
            damage = int(damage)
            if tried_damage:
                self.apply_damage(target, damage)

            # Apply target effects
            for effect in attack.effects:
                rounds = random.randrange(effect.rounds_min, effect.rounds_max + 1)
                if not effect.apply_to_source:
                    target.add_active_effect(ActiveEffect(effect, rounds))

            debug.println('%s attacks %s with %s for %d' % (source.id, target.id, attack.name, damage))

            if damage > 0:
                total_damage += damage

        # Award spin for total damage
        if attack.spin_cost == 0:
            self.award_spin(source, max(0, total_damage))

        # Critical fail effect
        if critical_fail and critical_fail_effect:
            debug.println('Critical fail')
            rounds = random.randrange(effect.rounds_min, critical_fail_effect.rounds_max + 1)
            if effect.apply_to_source:
                source.add_active_effect(ActiveEffect(critical_fail_effect, rounds))
                self.add_floater(source, 'Critical fail', ui.floater_border_grey)

        if self.floaters:
            self.after(2, self.end_turn)
        else:
            self.after(1, self.end_turn)

    def apply_damage(self, target, damage):
        target.votes -= damage
        target.votes = int(clamp(target.votes, 0, target.max_votes))

        if damage >= 0:
            self.add_floater(target, '%d' % damage, ui.floater_border_red)
        elif damage < 0:
            self.add_floater(target, '%d' % -damage, ui.floater_border_green)
            
        if target.votes == 0:
            target.votes = 0
            self.set_dead(target, True)
            
    def set_dead(self, character, dead):
        character.dead = dead
        self.get_slot(character).sprite.effect_dead = dead

    def award_spin(self, target, damage):
        bonus = (damage + target.accumulated_spin_damage + max(target.wit, 0)) / 5
        if bonus <= 0:
            target.accumulated_spin_damage += damage
        else:
            target.accumulated_spin_damage = 0

        debug.println('Awarded %d spin; %d left over damage for next time' % (bonus, target.accumulated_spin_damage))
        target.spin = min(target.spin + bonus, target.max_spin)
        
    def add_floater(self, character, text, border, offset=0):
        slot = self.get_slot(character)
        self.floaters.append(Floater(text, slot.x * self.tile_size * map_scale + 16, slot.y * self.tile_size * map_scale - offset * 28 - 16, border))

    def draw(self):
        self.draw_world()

        i = -1
        for slot in self.slots:
            if slot.character:
                x = slot.x * self.tile_size * map_scale
                y = slot.y * self.tile_size * map_scale

                bar_width = int(clamp(slot.character.votes * 32 / slot.character.max_votes, 0, 32))
                bacon.draw_image(ui.health_background_image, x, y - 12, x + 32, y - 8)
                bacon.draw_image(ui.health_image, x, y - 12, x + bar_width, y - 8)

                x += 12
                y += 56

                aes = slot.character.active_effects
                aes = [ae for ae in aes if ae.effect.abbrv]
                if aes:
                    ae = aes[int(game.time / 2) % len(aes)]
                    ui.draw_text_box(ae.effect.abbrv, x + 4, y + 4, ui.floater_border_grey)
                    y += 24

        for slot in self.slots:
            if slot.character:
                x = slot.x * self.tile_size * map_scale + 12
                y = slot.y * self.tile_size * map_scale + 56

                aes = slot.character.active_effects
                aes = [ae for ae in aes if ae.effect.abbrv]
                if aes:
                    y += 24

                if slot.character is self.current_character:
                    ui.draw_combat_selection_box(slot.character.data.name, x, y)
                    
                i += 1
                if i == debug.show_slot_stats:
                    c = slot.character
                    x = slot.x * self.tile_size * map_scale
                    y = slot.y * self.tile_size * map_scale + 24 * map_scale
                    dy = debug.font.height
                    debug.draw_string(c.id, x, y)
                    debug.draw_string('xp=%d' % c.xp, x, y + dy)
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
                    for ia in c.item_attacks:
                        y += dy
                        debug.draw_string('%s (x%d)' % (ia.attack.id, ia.quantity), x, y)
                         
        if self.active_attack:
            ui.draw_text_box(self.active_attack.name, ui_width / 2, 64, ui.attack_border)

        for floater in self.floaters[:]:
            floater.timeout -= bacon.timestep
            if floater.timeout < 0.5:
                floater.y -= bacon.timestep * 80
            if floater.timeout < 0:
                self.floaters.remove(floater)
            else:
                ui.draw_text_box(floater.text, floater.x, int(floater.y), floater.border)
               
        self.draw_menu()
        self.draw_hud()
        self.draw_stats()

class WinCombatWorld(World):
    def __init__(self, combat_world):
        super(WinCombatWorld, self).__init__('ui_win_combat')
        self.combat_world = combat_world
        self.characters = list(game.allies)
        self.queued_dialogs = []

        # Actually award results
        encounter = self.combat_world.encounter
        for ia in encounter.item_attack_drops:
            for i in range(ia.quantity):
                add_attack_to_itemattack_list(game.player.item_attacks, ia.attack)
        
        # Generate XP per character
        per_character_xp = encounter.xp / len(self.characters)
        game.money += encounter.money
        for character in self.characters:
            if get_level_for_xp(character.xp + per_character_xp) != character.level:
                self.queued_dialogs.append(LevelUpWorld(character, self.combat_world, per_character_xp))
            else:
                character.xp += per_character_xp
        
    def draw(self):
        encounter = self.combat_world.encounter
        self.combat_world.draw()

        width = ui_width / 2
        height = ui.font.height * 3
        if encounter.money:
            height  += ui.font.height
        if encounter.item_attack_drops:
            height += ui.font.height * (len(encounter.item_attack_drops) + 2)
        
        cx = ui_width / 2
        cy = ui_height / 2
        x1 = cx - width / 2
        y1 = cy - height / 2
        x2 = cx + width / 2
        y2 = cy + height / 2

        # Background
        ui.draw_box(Rect(x1, y1, x2, y2), ui.white_border)

        y = y1

        # Title
        ui.draw_box(Rect(x1, y1, x2, y1 + ui.font.height), ui.floater_border_red)
        bacon.draw_string(ui.font, 'Victory!', cx, y, align = bacon.Alignment.center, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height + 16

        # XP
        bacon.set_color(0, 0, 0, 1)
        bacon.draw_string(ui.font, 'XP Reward: %d' % encounter.xp, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        if encounter.money:
            y += ui.font.height
            bacon.draw_string(ui.font, 'Kickback: $%d' % encounter.money, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height * 2

        if encounter.item_attack_drops:
            bacon.draw_string(ui.font, 'Loot:', x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
            y += ui.font.height

            for ia in encounter.item_attack_drops:
                if ia.quantity == 1:
                    name = ia.attack.name
                else:
                    name = '%s (x%d)' % (ia.attack.name, ia.quantity)
                bacon.draw_string(ui.font, name, x1 + 32, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
                y += ui.font.height

        bacon.set_color(1, 1, 1, 1)

    def on_world_key_pressed(self, key):
        self.next()

    def on_level_up_world_dismissed(self):
        self.next()

    def next(self):
        if self.queued_dialogs:
            game.push_world(self.queued_dialogs.pop(0))
        else:
            self.dismiss()

    def dismiss(self):
        self.combat_world.reset()
        game.pop_world()
        game.pop_world()
        game.world.continue_script()

class AssignSkillPointsMenu(Menu):
    def __init__(self, world):
        super(AssignSkillPointsMenu, self).__init__(world)
        self.can_dismiss = False
        self.enable_border = False
        self.cunning_item = MenuItem('Cunning', 'Effectiveness of standard attacks')
        self.wit_item = MenuItem('Wit', 'Effectiveness of spin attacks')
        self.charisma_item = MenuItem('Charisma', 'Defense against opponent\'s attacks')
        self.flair_item = MenuItem('Flair', 'Chance of critical attack')
        self.speed_item = MenuItem('Speed', 'Determines order in battle')
        self.done_item = MenuItem('Done', 'Finish assigning skill points', self.on_done, False)
        self.items.append(self.cunning_item)
        self.items.append(self.wit_item)
        self.items.append(self.charisma_item)
        self.items.append(self.flair_item)
        self.items.append(self.speed_item)
        self.items.append(self.done_item)
        for item in self.items:
            item.skill_points_added = 0

        self.format_menu_items()

    def on_key_pressed(self, key):
        if self.selected_item is self.done_item:
            super(AssignSkillPointsMenu, self).on_key_pressed(key)
            return

        if key == bacon.Keys.up:
            self.move_selection(-1)
        elif key == bacon.Keys.down:
            self.move_selection(1)
        elif key in (bacon.Keys.left, bacon.Keys.minus, bacon.Keys.numpad_sub):
            self.alter_selection(-1)
        elif key in (bacon.Keys.right, bacon.Keys.enter, bacon.Keys.plus, bacon.Keys.numpad_add):
            self.alter_selection(1)

    def alter_selection(self, amount):
        if amount > 0 and self.world.skill_points == 0:
            return
        elif amount < 0 and self.selected_item.skill_points_added == 0:
            return

        self.selected_item.skill_points_added += amount
        self.world.skill_points -= amount
        self.format_menu_items()

    def format_menu_items(self):
        self.cunning_item.name = '< Cunning: %d +%d >' % (self.world.character.cunning, self.cunning_item.skill_points_added)
        self.wit_item.name = '< Wit: %d +%d >' % (self.world.character.wit, self.wit_item.skill_points_added)
        self.charisma_item.name = '< Charisma: %d +%d >' % (self.world.character.charisma, self.charisma_item.skill_points_added)
        self.flair_item.name = '< Flair: %d +%d >' % (self.world.character.flair, self.flair_item.skill_points_added)
        self.speed_item.name = '< Speed: %d +%d >' % (self.world.character.speed, self.speed_item.skill_points_added)
        self.cunning_item.enabled = self.cunning_item.skill_points_added > 0 or self.world.skill_points > 0
        self.wit_item.enabled = self.wit_item.skill_points_added > 0 or self.world.skill_points > 0
        self.charisma_item.enabled = self.charisma_item.skill_points_added > 0 or self.world.skill_points > 0
        self.flair_item.enabled = self.flair_item.skill_points_added > 0 or self.world.skill_points > 0
        self.speed_item.enabled = self.speed_item.skill_points_added > 0 or self.world.skill_points > 0
        self.done_item.enabled = self.world.skill_points == 0

    def on_done(self):
        self.world.character.cunning += self.cunning_item.skill_points_added
        self.world.character.wit += self.wit_item.skill_points_added
        self.world.character.charisma += self.charisma_item.skill_points_added
        self.world.character.flair += self.flair_item.skill_points_added
        self.world.character.speed += self.speed_item.skill_points_added
        self.world.dismiss()

    def activate_menu_item_color(self, selected, enabled):
        if enabled:
            if selected:
                m = 1
            else:
                m = 0
            bacon.set_color(m * 202.0 / 255, m * 72.0 / 255, m * 79.0 / 255, 1)
        else:
            if selected:
                m = 0.5
            else:
                m = 0.7
            bacon.set_color(m, m, m, 1)

class LevelUpWorld(World):
    def __init__(self, character, combat_world, add_xp):
        super(LevelUpWorld, self).__init__('ui_levelup')
        self.add_xp = add_xp
        self.character = character
        self.combat_world = combat_world

    def start(self):
        self.character.xp += self.add_xp
        level = get_level_for_xp(self.character.xp)
        level_row = get_level_row(level)
        self.character.level = level
        self.character.max_spin = level_row.spin
        self.character.max_votes = level_row.votes
        self.skill_points = level_row.skill_points
        self.push_menu(AssignSkillPointsMenu(self))
        self.layout()
        
    def layout(self):
        menu = self.menu_stack[-1]
        menu_height = menu.y2 - menu.y1

        width = ui_width / 2
        height = ui.font.height * 9 + menu_height
        
        cx = ui_width / 2
        cy = ui_height / 2
        x1 = cx - width / 2
        y1 = cy - height / 2
        x2 = cx + width / 2
        y2 = cy + height / 2
        
        menu.y1 = y1 + ui.font.height * 9
        menu.y2 = menu.y1 + menu_height

        self.width = width
        self.height = height
        self.cx = cx
        self.cy = cy
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def dismiss(self):
        game.pop_world()
        game.world.on_level_up_world_dismissed()

    def draw(self):
        self.combat_world.draw()
        width = self.width
        height = self.height
        cx = self.cx
        cy = self.cy
        x1 = self.x1
        y1 = self.y1
        x2 = self.x2
        y2 = self.y2
        character = self.character

        # Background
        ui.draw_box(Rect(x1, y1, x2, y2), ui.white_border)

        y = y1

        # Title
        ui.draw_box(Rect(x1, y1, x2, y1 + ui.font.height), ui.floater_border_red)
        bacon.draw_string(ui.font, 'LEVEL UP %s!' % character.data.name, cx, y, align = bacon.Alignment.center, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height + 16

        # XP
        bacon.set_color(0, 0, 0, 1)
        bacon.draw_string(ui.font, 'XP: %d' % character.xp, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height
        bacon.draw_string(ui.font, 'Level: %d' % character.level, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height
        bacon.draw_string(ui.font, 'Max Votes: %d' % character.max_votes, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height
        bacon.draw_string(ui.font, 'Max Spin: %d' % character.max_spin, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height * 2
        bacon.draw_string(ui.font, 'Skill Points to Assign: %d' % self.skill_points, x1, y, align = bacon.Alignment.left, vertical_align = bacon.VerticalAlignment.top)
        y += ui.font.height
        bacon.set_color(1, 1, 1, 1)

        self.draw_menu()

class Debug(object):
    def __init__(self):
        self.enabled = False
        self.font = font_tiny
        self.show_slot_stats = -1
        self.massive_damage = False
        self.message = None
        self.message_timeout = 0
        self.disable_collision = False
        self.disable_require = False

    def on_key_pressed(self, key):
        if not self.enabled:
            return

        if key == bacon.Keys.k or key == bacon.Keys.j:
            self.show_slot_stats += 1 if key == bacon.Keys.k else -1
            self.println('show_slot_stats = %d' % self.show_slot_stats)
        elif key == bacon.Keys.f1:
            self.massive_damage = not self.massive_damage
            self.println('massive_damage = %s' % self.massive_damage)
        elif key == bacon.Keys.f2:
            if isinstance(game.world, CombatWorld):
                game.world.win()
                self.println('cheat win')
        elif key == bacon.Keys.f3:
            game.money += 1000
            self.println('cheat money')
        elif key == bacon.Keys.f4:
            for ally in game.allies:
                ally.spin = ally.max_spin
            self.println('cheat restore spin')
        elif key == bacon.Keys.f5:
            self.disable_collision = not self.disable_collision
            self.println('disable_collision = %s' % self.disable_collision)
        elif key == bacon.Keys.f6:
            for ally in game.allies:
                for attack in game_data.attacks.values():
                    if attack not in ally.standard_attacks:
                        ally.standard_attacks.append(attack)
            self.println('unlock all attacks')
        elif key == bacon.Keys.f7:
            self.disable_require = not self.disable_require
            self.println('disable_require = %s' % self.disable_require)
        elif key == bacon.Keys.numpad_add:
            if isinstance(game.world, CombatWorld):
                game.world.apply_damage(game.world.current_character, -10)
        elif key == bacon.Keys.numpad_sub:
            if isinstance(game.world, CombatWorld):
                game.world.apply_damage(game.world.current_character, 10)

    def println(self, msg):
        if self.enabled:
            print msg

    def draw(self):
        if self.enabled:
            self.message_timeout -= bacon.timestep
            if self.message and self.message_timeout > 0:
                self.draw_string(self.message, 0, ui_height)

    def draw_string(self, text, x, y):
        if self.enabled:
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

def get_level_row(level):
    return game_data.levels[int(level - 1)]

def get_level_for_xp(xp):
    for level in game_data.levels:
        if xp < level.xp:
            return int(level.level - 1)

def get_save_dir():
    return appdirs.user_data_dir('GoodnightMrPresident')

def get_recent_save_filename():
    try:
        dir = get_save_dir()
        files = [file for file in os.listdir(dir) if os.path.isfile(os.path.join(dir, file))]
        files.sort()
        return files[-1]
    except:
        pass

def get_next_save_filename():
    recent = get_recent_save_filename()
    if not recent:
        return '001'
    return '%03d' % (int(recent) + 1)

class SavegameAlly(object):
    standard_attacks = []
    spin_attacks = []

    def __init__(self, character):
        self.id = character.id
        self.level = character.level
        self.xp = character.xp
        self.votes = character.votes
        self.max_votes = character.max_votes
        self.max_spin = character.max_spin
        self.spin = character.spin
        self.cunning = character.cunning
        self.charisma = character.charisma
        self.wit = character.wit
        self.flair = character.flair
        self.speed = character.speed
        self.standard_attacks = []
        for attack in character.standard_attacks:
            self.standard_attacks.append(attack.id)
        self.spin_attacks = []
        for attack in character.spin_attacks:
            self.spin_attacks.append(attack.id)

    def restore(self, character):
        character.id = self.id
        character.level = self.level
        character.xp = self.xp
        character.votes = self.votes
        character.max_votes = self.max_votes
        character.max_spin = self.max_spin
        character.spin = self.spin
        character.cunning = self.cunning
        character.charisma = self.charisma
        character.wit = self.wit
        character.flair = self.flair
        character.speed = self.speed
        for attack_id in self.standard_attacks:
            has_attack = False
            for a in character.standard_attacks:
                if a.id == attack_id:
                    has_attack = True
            if not has_attack:
                character.standard_attacks.append(game_data.attacks[attack_id])
        for attack_id in self.spin_attacks:
            has_attack = False
            for a in character.spin_attacks:
                if a.id == attack_id:
                    has_attack = True
            if not has_attack:
                character.spin_attacks.append(game_data.attacks[attack_id])

class Savegame(object):
    item_attacks = []
    quest_items = []

    def __init__(self, game, trigger):
        self.trigger = trigger
        self.money = game.money
        self.item_attacks = []
        for ia in game.player.item_attacks:
            for i in range(ia.quantity):
                self.item_attacks.append(ia.attack.id)

        self.quest_items = []
        for item in game.quest_items:
            self.quest_items.append(item.id)

        self.allies = []
        for ally in game.allies:
            self.allies.append(SavegameAlly(ally))

    def restore(self, game):
        game.money = self.money
        for item_attack in self.item_attacks:
            game.player.add_item_attack(game_data.attacks[item_attack])
        for item_id in self.quest_items:
            game.quest_items.append(game_data.quest_items[item_id])
        for ally in self.allies:
            if ally.id == 'Player':
                character = game.player
            else:
                character = Character(ally.id, ally.level, game.player.item_attacks, False)
                game.allies.append(character)
            ally.restore(character)
        game.world.run_script(None, self.trigger)
            
class Game(bacon.Game):
    def __init__(self):
        self.music = None

        self.player = Character('Player', 1, [], False)
        self.allies = [self.player]
        self.quest_items = []
        self.quest_flags = set()
        self.quest_vars = {}
        self.money = 0
        self.map_worlds = {}
        self.time = 0

        self.world = None
        self.world_stack = []

    def save(self, trigger):
        savegame = Savegame(self, trigger)
        save_dir = get_save_dir()
        path = os.path.join(save_dir, get_next_save_filename())
        try:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            pickle.dump(savegame, open(path, 'w'))
            print 'Saved game to "%s"' % path
            return True
        except:
            logging.error('Error saving game to "%s"' % path)
            return False

    def load(self):
        # Assume no state has been set yet, no need to reset
        try:
            save_dir = get_save_dir()
            path = os.path.join(save_dir, get_recent_save_filename())
            savegame = pickle.load(open(path, 'r'))
        except:
            logging.error('Failed to load savegame "%s"' % path)
            return False

        savegame.restore(self)
        return True

    def push_world(self, world):
        self.world_stack.append(self.world)
        self.world = world
        world.start()

    def pop_world(self):
        self.world = self.world_stack.pop()

    def goto_map(self, map_id):
        if map_id == 'title':
            world = TitleWorld(map_id)
        elif map_id == 'end':
            world = EndWorld(map_id)
        elif map_id in self.map_worlds:
            world = self.map_worlds[map_id]
        else:
            world = MapWorld(map_id)
        self.map_worlds[map_id] = world
        self.world = world
        self.world.run_script(None, map_id)
        del self.world_stack[:]

    def play_music(self, file):
        sound = bacon.Sound(file, stream=True)
        self.music = bacon.Voice(sound)
        self.music.play()

    def on_tick(self):
        self.time += bacon.timestep

        bacon.clear(0, 0, 0, 1)
        self.world.update()
        self.world.draw()

        debug.draw()

    def on_key(self, key, pressed):
        if pressed:
            self.world.on_key_pressed(key)
            debug.on_key_pressed(key)
        else:
            self.world.on_key_released(key)

    def get_ally(self, id):
        for ally in self.allies:
            if ally.id == id:
                return ally
        return None

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

def ai_get_health_benefit(attack):
    # Get min health benefit
    if attack.target_type != 'AllFriendly' and attack.target_type != 'None':
        return 0

    h = max(0, -attack.base_damage_max)
    for effect in attack.effects:
        if effect.attribute == 'votes' and effect.function == 'add_permanent':
            h += effect.value

    return h

def ai_is_revive_attack(attack):
    for effect in attack.effects:
        if effect.function == 'revive':
            return True
    return False

def ai_is_summon_attack(attack):
    for effect in attack.effects:
        if effect.function == 'call_friends':
            return True
    return False

def main():
    parser = optparse.OptionParser()
    parser.add_option('--import-ods')
    parser.add_option('--debug', action='store_true')
    options, args = parser.parse_args()
    
    debug.enabled = options.debug

    global game_data
    if options.import_ods:
        import odsimport
        combat_db = odsimport.import_ods(os.path.join(options.import_ods, 'Combat.ods'))
        quest_db = odsimport.import_ods(os.path.join(options.import_ods, 'Quest.ods'))
        level_db = odsimport.import_ods(os.path.join(options.import_ods, 'Levels.ods'))
        game_data = GameData()
        
        game_data.quest_items = parse_table(quest_db['Items'], dict(id = 'ID',
            name = 'Name',
            description = 'Description',), index_unique=True)

        game_data.effects = parse_table(combat_db['Effects'], dict(id = 'ID',
            abbrv = 'Abbrev',
            apply_to_source = 'Apply To Source',
            function = 'Function',
            rounds_min = 'Number Rounds Base',
            rounds_max = 'Number Rounds Max',
            attribute = 'Attribute Effected',
            value = 'Value',), index_unique=True, cls=Effect)

        game_data.attacks = parse_table(combat_db['Attacks'], dict(id = 'ID',
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
            weight = 'AI Weight',), index_unique=True)

        for attack in game_data.attacks.values():
            attack.target_count = int(attack.target_count)
            attack.effects = convert_idlist_to_objlist(attack.effects, game_data.effects)
            attack.spin_cost = attack.spin_cost if attack.spin_cost else 0
            attack.weight = attack.weight if attack.weight else 1
            attack.health_benefit = ai_get_health_benefit(attack)
            attack.is_revive = ai_is_revive_attack(attack)
            attack.is_summon = ai_is_summon_attack(attack)

        game_data.standard_attacks = parse_table(combat_db['StandardAttacks'], dict(group = 'AttackGroup',
            attack = 'Attack',), index_multi=True)

        for attacks in game_data.standard_attacks.values():
            for i, row in enumerate(attacks):
                attacks[i] = game_data.attacks[row.attack]

        game_data.characters = parse_table(combat_db['Characters'], dict(id = 'ID',
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
            weaknesses = 'Weaknesses',), index_multi=True)

        # Parse characters
        for characters in game_data.characters.values():
            for character in characters:
                character.immunities = convert_idlist_to_objlist(character.immunities, game_data.attacks)
                character.resistance = convert_idlist_to_objlist(character.resistance, game_data.attacks)
                character.weaknesses = convert_idlist_to_objlist(character.weaknesses, game_data.attacks)
                attacks = game_data.standard_attacks[character.attack_group]
                character.spin_attacks = [attack for attack in attacks if attack.spin_cost]
                character.standard_attacks = [attack for attack in attacks if not attack.spin_cost]
                
        game_data.encounters = parse_table(combat_db['Encounters'], dict(id = 'ID',
            name = 'Name',
            monster1 = 'Monster 1',
            monster1_lvl = 'Monster 1 Lvl',
            monster2 = 'Monster 2',
            monster2_lvl = 'Monster 2 Lvl',
            monster3 = 'Monster 3',
            monster3_lvl = 'Monster 3 Lvl',
            monster4 = 'Monster 4',
            monster4_lvl = 'Monster 4 Lvl',
            item_attacks = 'Attack Items',
            bribe_cost = 'Bribe Cost',
            xp = 'XP',
            money = 'Money',
            item_attack_drops = 'Attack Drops',), index_unique=True)

        for encounter in game_data.encounters.values():
            encounter.item_attacks = [ItemAttack(attack, 1) for attack in convert_idlist_to_objlist(encounter.item_attacks, game_data.attacks)]
            attack_drops = convert_idlist_to_objlist(encounter.item_attack_drops, game_data.attacks)
            encounter.item_attack_drops = []
            for attack in attack_drops:
                add_attack_to_itemattack_list(encounter.item_attack_drops, attack)

        game_data.script = parse_table(quest_db['Script'], dict(trigger = 'Trigger',
            action = 'Action',
            param = 'Param',
            dialog = 'Dialog',), index_multi=True)

        game_data.levels = parse_table(level_db['Levels'], dict(level = 'Level',
            xp = 'XP',
            votes = 'Votes',
            spin = 'Spin',
            skill_points = 'Skill Points',))

        game_data.shops = parse_table(quest_db['Shops'], dict(shop_id = 'ID',
            item_attack = 'Attack Item',
            price = 'Price',), index_multi=True)
        for shop in game_data.shops.values():
            for ware in shop:
                ware.item_attack = game_data.attacks[ware.item_attack]

        pickle.dump(game_data, open_res('res/game_data.bin', 'wb'))
    else:
        game_data = pickle.load(open_res('res/game_data.bin', 'rb'))

    global game_sprites
    game_sprites = load_sprites('res/sprites.tsx')
    start_game(args)

def start_game(args):
    global game
    game = Game()

    game.goto_map('title')
    if args:
        for arg in args:
            game.world.run_script(None, arg) 
    else:
        game.world.run_script(None, 'START')
    game.play_music('res/wwing.ogg')

    bacon.run(game)

import traceback
try:
    main()
except:
    traceback.print_exc()
